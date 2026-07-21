import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests
from sqlalchemy.orm import Session

from app.models.estabelecimento import Estabelecimento
from app.models.reminder_job import ReminderJob
from app.services.payments.crypto import decrypt_sensitive_value
from app.time_utils import utcnow_naive


MEGAAPI_SEND_URL = os.getenv("MEGAAPI_SEND_URL")
MEGAAPI_SEND_TIMEOUT_SECONDS = max(3, min(int(os.getenv("MEGAAPI_SEND_TIMEOUT_SECONDS", "8")), 20))


def _validated_megaapi_url() -> str | None:
    value = (MEGAAPI_SEND_URL or "").strip()
    if not value:
        return None
    if os.getenv("APP_ENV", "development").strip().lower() not in {"prod", "production"}:
        return value
    parsed = urlsplit(value)
    allowed_hosts = {
        item.strip().lower()
        for item in os.getenv("MEGAAPI_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed_hosts:
        return None
    return value


def _messaging_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if not token:
        return None
    if token.startswith(("v2:", "gAAAA")):
        return decrypt_sensitive_value(token)
    if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}:
        return None
    return token


def _normalizar_telefone(telefone: str) -> str:
    digits = re.sub(r"\D", "", telefone or "")
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits


def enviar_mensagem_whatsapp(
    barbearia: Estabelecimento,
    telefone: str,
    mensagem: str,
) -> bool:
    send_url = _validated_megaapi_url()
    if not send_url:
        return False

    payload = {
        "instance_key": barbearia.mega_instance_key,
        "to": _normalizar_telefone(telefone),
        "message": mensagem,
    }
    headers = {"Content-Type": "application/json"}
    token = _messaging_token(barbearia.mega_token)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(
            send_url,
            json=payload,
            headers=headers,
            timeout=MEGAAPI_SEND_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        return response.status_code < 300
    except Exception:
        return False


def montar_mensagem_confirmacao(
    nome_barbearia: str,
    cliente_nome: str,
    servico_nome: str,
    inicio: datetime,
) -> str:
    return (
        f"Oi, {cliente_nome}. Seu agendamento na {nome_barbearia} foi confirmado.\n"
        f"Servico: {servico_nome}\n"
        f"Data: {inicio.strftime('%d/%m/%Y')}\n"
        f"Horario: {inicio.strftime('%H:%M')}"
    )


def _montar_mensagem_lembrete(
    nome_barbearia: str,
    cliente_nome: str,
    servico_nome: str,
    inicio: datetime,
    horas_antes: int,
) -> str:
    return (
        f"Lembrete da {nome_barbearia}: faltam {horas_antes}h para seu horario.\n"
        f"Cliente: {cliente_nome}\n"
        f"Servico: {servico_nome}\n"
        f"Data: {inicio.strftime('%d/%m/%Y')} às {inicio.strftime('%H:%M')}"
    )


def agendar_lembretes_agendamento(
    db: Session,
    *,
    tenant_id: int,
    agendamento_id: int,
    cliente_nome: str,
    cliente_telefone: str,
    nome_barbearia: str,
    servico_nome: str,
    inicio: datetime,
) -> int:
    total = 0
    for tipo, horas in (("reminder_24h", 24), ("reminder_2h", 2)):
        enviar_em = inicio - timedelta(hours=horas)
        if enviar_em <= datetime.now(timezone.utc).replace(tzinfo=None):
            continue

        reminder = ReminderJob(
            estabelecimento_id=tenant_id,
            agendamento_id=agendamento_id,
            tipo=tipo,
            canal="whatsapp",
            destinatario=_normalizar_telefone(cliente_telefone),
            mensagem=_montar_mensagem_lembrete(
                nome_barbearia=nome_barbearia,
                cliente_nome=cliente_nome,
                servico_nome=servico_nome,
                inicio=inicio,
                horas_antes=horas,
            ),
            enviar_em=enviar_em,
            status="pendente",
        )
        db.add(reminder)
        total += 1

    return total


def processar_lembretes_pendentes(db: Session, limite: int = 100) -> dict[str, int]:
    agora = utcnow_naive()
    pendentes = (
        db.query(ReminderJob)
        .filter(
            ReminderJob.status == "pendente",
            ReminderJob.enviar_em <= agora,
        )
        .order_by(ReminderJob.enviar_em.asc(), ReminderJob.id.asc())
        .limit(limite)
        .all()
    )

    enviados = 0
    falhas = 0

    for job in pendentes:
        barbearia = db.query(Estabelecimento).filter(Estabelecimento.id == job.tenant_id).first()
        if not barbearia:
            job.status = "falha"
            job.ultimo_erro = "tenant_nao_encontrado"
            job.tentativas += 1
            falhas += 1
            continue

        # Plano Gratis nao tem notificacoes WhatsApp
        plano = (barbearia.plano or "gratis").lower()
        if plano == "gratis":
            job.status = "nao_aplicavel"
            job.ultimo_erro = "plano_gratis_sem_whatsapp"
            continue

        ok = enviar_mensagem_whatsapp(barbearia, job.destinatario, job.mensagem)
        job.tentativas += 1
        if ok:
            job.status = "enviado"
            job.enviado_em = utcnow_naive()
            enviados += 1
        else:
            job.status = "falha"
            job.ultimo_erro = "falha_envio_whatsapp"
            falhas += 1

    if pendentes:
        db.commit()

    return {"processados": len(pendentes), "enviados": enviados, "falhas": falhas}
