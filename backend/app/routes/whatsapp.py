from fastapi import APIRouter, Request,Query
from app.database import SessionLocal
from app.services.chatbot_service import responder_mensagem
import requests
import os
import re

router = APIRouter()

VERIFY_TOKEN = "barbearia_token_123"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


# ✅ Verificação do webhook (Meta exige isso)

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)

    return {"status": "error"}


# ✅ Receber mensagens
@router.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    try:
        # DEBUG TEMPORÁRIO (ajuda a ver exatamente o que a Meta envia)
        print("WEBHOOK BODY:", body)

        entry = body.get("entry", [])
        if not entry:
            return {"status": "ignored"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "ignored"}

        value = changes[0].get("value", {})

        # ✅ Ignora eventos que não são mensagens (status, delivery, etc)
        messages = value.get("messages")
        if not messages:
            return {"status": "ignored"}

        mensagem = messages[0]

        # ✅ Só processa texto por enquanto
        if mensagem.get("type") != "text":
            return {"status": "ignored"}

        telefone = mensagem.get("from")
        texto = mensagem.get("text", {}).get("body")

        if not telefone or not texto:
            return {"status": "ignored"}

        db = SessionLocal()

        resposta = responder_mensagem(db, telefone, texto)

        # responder_mensagem pode retornar string ou dict
        if isinstance(resposta, dict):
            texto_resposta = resposta.get("resposta", "")
        else:
            texto_resposta = str(resposta)

        enviar_resposta_whatsapp(telefone, texto_resposta)

    except Exception as e:
        print("Erro webhook:", e)

    return {"status": "ok"}

def enviar_resposta_whatsapp(telefone, texto):

    # Normaliza telefone (remove +, espaços, parênteses e traços)
    telefone = re.sub(r"\D", "", str(telefone))

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto}
    }
    

    response = requests.post(url, headers=headers, json=data)

    print("STATUS META:", response.status_code)
    print("RESPOSTA META:", response.text)