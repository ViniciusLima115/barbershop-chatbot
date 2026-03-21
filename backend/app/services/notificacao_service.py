import os
import re
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import Session

from app.models.barbearia import Barbearia
from app.models.reminder_job import ReminderJob


MEGAAPI_SEND_URL = os.getenv("MEGAAPI_SEND_URL")
MEGAAPI_SEND_TIMEOUT_SECONDS = int(os.getenv("MEGAAPI_SEND_TIMEOUT_SECONDS", "8"))


def _normalizar_telefone(telefone: str) -> str:
    digits = re.sub(r"\D", "", telefone or "")
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits


def enviar_mensagem_whatsapp(
    barbearia: Barbearia,
    telefone: str,
    mensagem: str,
) -> bool:
    if not MEGAAPI_SEND_URL:
        return False

    payload = {
        "instance_key": barbearia.mega_instance_key,
        "to": _normalizar_telefone(telefone),
        "message": mensagem,
    }
    headers = {"Content-Type": "application/json"}
    if barbearia.mega_token:
        headers["Authorization"] = f"Bearer {barbearia.mega_token}"

    try:
        response = requests.post(
            MEGAAPI_SEND_URL,
            json=payload,
            headers=headers,
            timeout=MEGAAPI_SEND_TIMEOUT_SECONDS,
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
            tenant_id=tenant_id,
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
    agora = datetime.utcnow()
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
        barbearia = db.query(Barbearia).filter(Barbearia.id == job.tenant_id).first()
        if not barbearia:
            job.status = "falha"
            job.ultimo_erro = "tenant_nao_encontrado"
            job.tentativas += 1
            falhas += 1
            continue

        ok = enviar_mensagem_whatsapp(barbearia, job.destinatario, job.mensagem)
        job.tentativas += 1
        if ok:
            job.status = "enviado"
            job.enviado_em = datetime.utcnow()
            enviados += 1
        else:
            job.status = "falha"
            job.ultimo_erro = "falha_envio_whatsapp"
            falhas += 1

    if pendentes:
        db.commit()

    return {"processados": len(pendentes), "enviados": enviados, "falhas": falhas}
