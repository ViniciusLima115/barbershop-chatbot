import os
import re
import logging

import requests
from fastapi import APIRouter, Query, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.barbearia import Barbearia
from app.services.chatbot_service import responder_mensagem
from app.services.public_booking_service import (
    deve_responder_com_link,
    montar_mensagem_link_agendamento_por_id,
)
from app.services.webhook_payload_service import (
    extrair_dados_mensagem as parse_extrair_dados_mensagem,
    extrair_instance_key as parse_extrair_instance_key,
    normalizar_whatsapp as parse_normalizar_whatsapp,
    resolver_tenant_id as parse_resolver_tenant_id,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFY_TOKEN = "barbearia_token_123"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


def _resposta_publica_link(db: Session, tenant_id: int, texto: str):
    try:
        barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    except Exception:
        return None

    if not barbearia:
        return None
    if not deve_responder_com_link(texto):
        return None

    return {
        "tipo": "link_agendamento",
        "resposta": montar_mensagem_link_agendamento_por_id(barbearia.nome, barbearia.id),
    }


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)

    return {"status": "error"}


@router.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.json()
        telefone, texto, value = _extrair_dados_mensagem(body)

        if not telefone or not texto:
            return {"status": "ignored"}

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        whatsapp_number = value.get("metadata", {}).get("display_phone_number") or phone_number_id
        instance_key = _extrair_instance_key(body, value)

        db = SessionLocal()
        try:
            tenant_id = _resolver_tenant_id(
                db,
                instance_key=instance_key,
                whatsapp_number=whatsapp_number,
            )
            if tenant_id is None:
                logger.info("Webhook ignorado: tenant_id nao resolvido.")
                return {"status": "ignored"}

            resposta = _resposta_publica_link(db, tenant_id, texto)
            if not resposta:
                resposta = responder_mensagem(db, telefone, texto, tenant_id=tenant_id)
        finally:
            db.close()

        texto_resposta = resposta.get("resposta", "") if isinstance(resposta, dict) else str(resposta)
        enviar_resposta_whatsapp(telefone, texto_resposta, phone_number_id=phone_number_id)

    except Exception:
        logger.exception("Erro ao processar webhook do WhatsApp!")

    return {"status": "ok"}


def _extrair_dados_mensagem(body: dict) -> tuple[str | None, str | None, dict]:
    return parse_extrair_dados_mensagem(body)


def _extrair_instance_key(body: dict, value: dict) -> str | None:
    return parse_extrair_instance_key(body, value)


def _normalizar_whatsapp(valor: str | None) -> str | None:
    return parse_normalizar_whatsapp(valor)


def _resolver_tenant_id(
    db: Session,
    instance_key: str | None = None,
    whatsapp_number: str | None = None,
) -> int | None:
    return parse_resolver_tenant_id(
        db,
        instance_key=instance_key,
        whatsapp_number=whatsapp_number,
    )


def enviar_resposta_whatsapp(telefone, texto, phone_number_id: str | None = None):
    telefone = re.sub(r"\D", "", str(telefone))
    current_phone_number_id = phone_number_id or PHONE_NUMBER_ID

    if not current_phone_number_id:
        logger.warning("Nao foi possivel enviar mensagem: PHONE_NUMBER_ID ausente.")
        return

    if not WHATSAPP_TOKEN:
        logger.warning("Nao foi possivel enviar mensagem: WHATSAPP_TOKEN ausente.")
        return

    url = f"https://graph.facebook.com/v22.0/{current_phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto},
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=8)
        if response.status_code >= 300:
            logger.warning(
                "Falha ao enviar mensagem para Meta API. status=%s body=%s",
                response.status_code,
                response.text,
            )
    except Exception:
        logger.exception("Erro de rede ao enviar mensagem para Meta API.")
