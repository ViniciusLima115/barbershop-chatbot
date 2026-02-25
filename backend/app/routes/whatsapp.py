import os
import re

import requests
from fastapi import APIRouter, Query, Request

from app.database import SessionLocal
from app.services.chatbot_service import responder_mensagem

router = APIRouter()

VERIFY_TOKEN = "barbearia_token_123"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_DEFAULT_TENANT_ID = os.getenv("WHATSAPP_DEFAULT_TENANT_ID")
WHATSAPP_PHONE_TENANT_MAP = os.getenv("WHATSAPP_PHONE_TENANT_MAP", "")


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
    body = await request.json()

    try:
        print("WEBHOOK BODY:", body)

        entry = body.get("entry", [])
        if not entry:
            return {"status": "ignored"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "ignored"}

        value = changes[0].get("value", {})

        messages = value.get("messages")
        if not messages:
            return {"status": "ignored"}

        mensagem = messages[0]

        if mensagem.get("type") != "text":
            return {"status": "ignored"}

        telefone = mensagem.get("from")
        texto = mensagem.get("text", {}).get("body")

        if not telefone or not texto:
            return {"status": "ignored"}

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        tenant_id = _resolver_tenant_id(phone_number_id)
        if tenant_id is None:
            print("Webhook ignorado: tenant_id nao resolvido.")
            return {"status": "ignored"}

        db = SessionLocal()
        try:
            resposta = responder_mensagem(db, telefone, texto, tenant_id=tenant_id)
        finally:
            db.close()

        texto_resposta = resposta.get("resposta", "") if isinstance(resposta, dict) else str(resposta)
        enviar_resposta_whatsapp(telefone, texto_resposta, phone_number_id=phone_number_id)

    except Exception as e:
        print("Erro webhook:", e)

    return {"status": "ok"}


def _resolver_tenant_id(phone_number_id: str | None) -> int | None:
    if phone_number_id and WHATSAPP_PHONE_TENANT_MAP:
        for item in WHATSAPP_PHONE_TENANT_MAP.split(","):
            bruto = item.strip()
            if ":" not in bruto:
                continue
            numero_id, tenant = bruto.split(":", 1)
            if numero_id.strip() == str(phone_number_id).strip():
                try:
                    return int(tenant.strip())
                except ValueError:
                    return None

    if WHATSAPP_DEFAULT_TENANT_ID:
        try:
            return int(WHATSAPP_DEFAULT_TENANT_ID)
        except ValueError:
            return None

    return None


def enviar_resposta_whatsapp(telefone, texto, phone_number_id: str | None = None):
    telefone = re.sub(r"\D", "", str(telefone))
    current_phone_number_id = phone_number_id or PHONE_NUMBER_ID

    if not current_phone_number_id:
        print("Nao foi possivel enviar mensagem: PHONE_NUMBER_ID ausente.")
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

    response = requests.post(url, headers=headers, json=data)

    print("STATUS META:", response.status_code)
    print("RESPOSTA META:", response.text)
