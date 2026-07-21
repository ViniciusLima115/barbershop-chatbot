import logging
import os
import re

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.estabelecimento import Estabelecimento
from app.services.chatbot_service import responder_mensagem
from app.services.public_booking_service import deve_responder_com_link, montar_mensagem_link_agendamento_por_id
from app.services.webhook_payload_service import (
    extrair_dados_mensagem as parse_extrair_dados_mensagem,
    extrair_instance_key as parse_extrair_instance_key,
    normalizar_whatsapp as parse_normalizar_whatsapp,
    resolver_tenant_id as parse_resolver_tenant_id,
)
from app.services.webhook_security import read_and_verify_meta_webhook, verify_meta_challenge

router = APIRouter()
logger = logging.getLogger(__name__)


def _resposta_publica_link(db: Session, tenant_id: int, texto: str):
    try:
        estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    except Exception:
        return None
    if not estabelecimento or not deve_responder_com_link(texto):
        return None
    return {
        "tipo": "link_agendamento",
        "resposta": montar_mensagem_link_agendamento_por_id(estabelecimento.nome, estabelecimento.id),
    }


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    return verify_meta_challenge(
        mode=hub_mode,
        provided_token=hub_verify_token,
        challenge=hub_challenge,
    )


@router.post("/webhook")
async def receive_message(request: Request):
    body = await read_and_verify_meta_webhook(request)
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
            return {"status": "ignored"}
        resposta = _resposta_publica_link(db, tenant_id, texto)
        if not resposta:
            resposta = responder_mensagem(db, telefone, texto, tenant_id=tenant_id)
    except Exception as exc:
        logger.exception("Falha ao processar webhook Meta.")
        raise HTTPException(status_code=500, detail="Falha temporaria ao processar webhook.") from exc
    finally:
        db.close()

    texto_resposta = resposta.get("resposta", "") if isinstance(resposta, dict) else str(resposta)
    enviar_resposta_whatsapp(telefone, texto_resposta, phone_number_id=phone_number_id)
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
    telefone_normalizado = re.sub(r"\D", "", str(telefone))
    current_phone_number_id = str(phone_number_id or os.getenv("PHONE_NUMBER_ID", "")).strip()
    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    if not current_phone_number_id or not current_phone_number_id.isdigit():
        logger.warning("Envio Meta ignorado: PHONE_NUMBER_ID ausente ou invalido.")
        return
    if not token:
        logger.warning("Envio Meta ignorado: WHATSAPP_TOKEN ausente.")
        return

    response = requests.post(
        f"https://graph.facebook.com/v22.0/{current_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "to": telefone_normalizado,
            "type": "text",
            "text": {"body": str(texto)[:4096]},
        },
        timeout=8,
        allow_redirects=False,
    )
    if response.status_code >= 300:
        logger.warning("Falha ao enviar mensagem para Meta API (status=%s).", response.status_code)
