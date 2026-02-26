import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.database import get_db
from app.models.barbearia import Barbearia
from app.models.webhook_event import WebhookEvent
from app.routes.whatsapp import _extrair_dados_mensagem, _extrair_instance_key, _resolver_tenant_id
from app.services.chatbot_service import responder_mensagem
from app.services.public_booking_service import (
    deve_responder_com_link,
    montar_mensagem_link_agendamento,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PROVIDER_MEGAAPI = "megaapi"

MEGAAPI_WEBHOOK_TOKEN = os.getenv("MEGAAPI_WEBHOOK_TOKEN")
MEGAAPI_WEBHOOK_SECRET = os.getenv("MEGAAPI_WEBHOOK_SECRET")
MEGAAPI_WEBHOOK_ALLOW_UNSIGNED = os.getenv("MEGAAPI_WEBHOOK_ALLOW_UNSIGNED", "false").lower() == "true"
MEGAAPI_WEBHOOK_MAX_SKEW_SECONDS = int(os.getenv("MEGAAPI_WEBHOOK_MAX_SKEW_SECONDS", "300"))


def _token_valido(headers: Headers) -> bool:
    if not MEGAAPI_WEBHOOK_TOKEN:
        return False

    token_recebido = (
        headers.get("x-webhook-token")
        or headers.get("x-megaapi-token")
        or headers.get("x-api-key")
    )
    auth = headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token_recebido = auth.split(" ", 1)[1].strip()

    return bool(token_recebido) and hmac.compare_digest(token_recebido, MEGAAPI_WEBHOOK_TOKEN)


def _assinatura_valida(raw_body: bytes, headers: Headers) -> bool:
    if not MEGAAPI_WEBHOOK_SECRET:
        return False

    assinatura = headers.get("x-mega-signature") or headers.get("x-signature")
    timestamp = headers.get("x-mega-timestamp") or headers.get("x-timestamp")

    if not assinatura or not timestamp:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    now = int(time.time())
    if abs(now - ts) > MEGAAPI_WEBHOOK_MAX_SKEW_SECONDS:
        return False

    assinatura_limpa = assinatura.strip()
    if "=" in assinatura_limpa:
        assinatura_limpa = assinatura_limpa.split("=", 1)[1]

    payload_assinado = f"{timestamp}.{raw_body.decode('utf-8')}"
    esperado = hmac.new(
        MEGAAPI_WEBHOOK_SECRET.encode("utf-8"),
        payload_assinado.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(assinatura_limpa, esperado)


def _validar_autenticacao_webhook(raw_body: bytes, headers: Headers) -> None:
    if _token_valido(headers):
        return
    if _assinatura_valida(raw_body, headers):
        return
    if MEGAAPI_WEBHOOK_ALLOW_UNSIGNED:
        return
    raise HTTPException(status_code=401, detail="Assinatura do webhook invalida.")


def _extrair_event_id(payload: dict, raw_body: bytes, value: dict) -> str:
    entry = payload.get("entry", [])
    mensagem_id = None
    if entry:
        try:
            mensagem_id = entry[0].get("changes", [])[0].get("value", {}).get("messages", [])[0].get("id")
        except Exception:
            mensagem_id = None

    candidatos = [
        payload.get("event_id"),
        payload.get("eventId"),
        payload.get("id"),
        payload.get("data", {}).get("id") if isinstance(payload.get("data"), dict) else None,
        payload.get("data", {}).get("event_id") if isinstance(payload.get("data"), dict) else None,
        payload.get("data", {}).get("eventId") if isinstance(payload.get("data"), dict) else None,
        payload.get("data", {}).get("key", {}).get("id") if isinstance(payload.get("data"), dict) else None,
        mensagem_id,
        value.get("messages", [{}])[0].get("id") if isinstance(value, dict) and value.get("messages") else None,
    ]

    for candidato in candidatos:
        if isinstance(candidato, str) and candidato.strip():
            return candidato.strip()

    return hashlib.sha256(raw_body).hexdigest()


def _registrar_evento(
    db: Session,
    provider: str,
    event_id: str,
    tenant_id: int | None,
) -> bool:
    evento = WebhookEvent(
        provider=provider,
        event_id=event_id,
        tenant_id=tenant_id,
    )
    db.add(evento)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


@router.post("/megaapi")
async def receive_megaapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    _validar_autenticacao_webhook(raw_body, request.headers)

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON invalido.")

    telefone, texto, value = _extrair_dados_mensagem(payload)
    if not telefone or not texto:
        return {"status": "ignored", "reason": "sem_mensagem_texto"}

    phone_number_id = value.get("metadata", {}).get("phone_number_id") if isinstance(value, dict) else None
    whatsapp_number = (
        value.get("metadata", {}).get("display_phone_number")
        if isinstance(value, dict)
        else None
    ) or phone_number_id or payload.get("whatsapp_number")

    instance_key = _extrair_instance_key(payload, value if isinstance(value, dict) else {})
    tenant_id = _resolver_tenant_id(
        db,
        instance_key=instance_key,
        whatsapp_number=whatsapp_number,
    )
    if tenant_id is None:
        return {"status": "ignored", "reason": "tenant_nao_resolvido"}

    event_id = _extrair_event_id(payload, raw_body, value if isinstance(value, dict) else {})
    if not _registrar_evento(db, PROVIDER_MEGAAPI, event_id, tenant_id):
        return {"status": "ignored", "reason": "evento_duplicado"}

    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        return {"status": "ignored", "reason": "tenant_nao_encontrado"}

    if barbearia.slug and deve_responder_com_link(texto):
        resposta = {
            "tipo": "link_agendamento",
            "resposta": montar_mensagem_link_agendamento(barbearia.nome, barbearia.slug),
        }
    else:
        resposta = responder_mensagem(db, telefone, texto, tenant_id=tenant_id)

    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "event_id": event_id,
        "resposta": resposta,
    }
