import os
import re

from sqlalchemy.orm import Session

from app.repositories.conversa_repository import ConversaRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.webhook_event_repository import WebhookEventRepository
from app.services.notificacao_service import enviar_mensagem_whatsapp
from app.services.webhook_payload_service import (
    extrair_dados_mensagem,
    extrair_instance_key,
)


PROVIDER_META_WEBHOOK = "meta-webhook"
_BOOKING_BASE = os.getenv("BOOKING_PUBLIC_BASE_URL", "https://app.virtualbarber.shop")


def _normalizar_telefone(telefone: str) -> str:
    digits = re.sub(r"\D", "", telefone or "")
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits


def montar_mensagem_saudacao(nome_barbearia: str, barbearia_id: int) -> str:
    return (
        f"Ola 👋 Seja bem-vindo a {nome_barbearia}!\n"
        "Clique aqui para agendar:\n"
        f"{_BOOKING_BASE.rstrip('/')}/agendar/{barbearia_id}"
    )


def processar_webhook_saudacao(
    db: Session,
    payload: dict,
    *,
    provider: str = PROVIDER_META_WEBHOOK,
) -> dict:
    telefone, texto, value = extrair_dados_mensagem(payload)
    if not telefone or not texto:
        return {"status": "ignored", "reason": "sem_mensagem_texto"}

    phone_number_id = value.get("metadata", {}).get("phone_number_id") if isinstance(value, dict) else None
    whatsapp_number = (
        value.get("metadata", {}).get("display_phone_number")
        if isinstance(value, dict)
        else None
    ) or phone_number_id or payload.get("whatsapp_number")

    instance_key = extrair_instance_key(payload, value if isinstance(value, dict) else {})
    tenant_repo = TenantRepository(db)
    barbearia = tenant_repo.resolve_by_instance_or_whatsapp(
        instance_key=instance_key,
        whatsapp_number=whatsapp_number,
    )
    if not barbearia:
        return {"status": "ignored", "reason": "tenant_nao_resolvido"}

    evento_repo = WebhookEventRepository(db)
    event_id = evento_repo.extract_event_id(payload)
    if not evento_repo.register_event_once(provider=provider, event_id=event_id, tenant_id=barbearia.id):
        return {"status": "ignored", "reason": "evento_duplicado"}

    telefone_normalizado = _normalizar_telefone(telefone)
    conversa_repo = ConversaRepository(db)
    conversa_ativa = conversa_repo.get_active(
        tenant_id=barbearia.id,
        telefone=telefone_normalizado,
    )

    contexto = {
        "ultima_mensagem_cliente": texto,
        "ultimo_event_id": event_id,
    }
    if conversa_ativa:
        conversa_repo.upsert(
            tenant_id=barbearia.id,
            telefone=telefone_normalizado,
            estado="ativa",
            contexto=contexto,
            ativa=True,
        )
        return {
            "status": "ok",
            "tenant_id": barbearia.id,
            "event_id": event_id,
            "saudacao_enviada": False,
        }

    mensagem = montar_mensagem_saudacao(barbearia.nome, barbearia.id)
    envio_ok = enviar_mensagem_whatsapp(barbearia, telefone_normalizado, mensagem)
    conversa_repo.upsert(
        tenant_id=barbearia.id,
        telefone=telefone_normalizado,
        estado="saudacao_enviada",
        contexto={**contexto, "mensagem_enviada": mensagem},
        ativa=True,
    )

    return {
        "status": "ok",
        "tenant_id": barbearia.id,
        "event_id": event_id,
        "saudacao_enviada": True,
        "envio_ok": envio_ok,
        "mensagem": mensagem,
    }
