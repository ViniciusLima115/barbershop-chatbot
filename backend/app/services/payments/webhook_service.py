import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pagamento import Pagamento
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.payment_account_service import (
    get_active_payment_account,
    get_decrypted_access_token,
)
from app.services.payments.payment_service import apply_payment_update_from_provider
from app.services.payments.provider_factory import get_payment_provider


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _extract_provider_payment_id(payload: dict, payment_id_query: str | None) -> str | None:
    if payment_id_query:
        return str(payment_id_query)
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data.get("id"))
    if payload.get("id"):
        return str(payload.get("id"))
    return None


def _extract_external_event_id(payload: dict, provider_payment_id: str | None, webhook_id: str | None) -> str:
    if webhook_id:
        return str(webhook_id)
    if payload.get("id"):
        return str(payload.get("id"))
    if provider_payment_id:
        return f"payment:{provider_payment_id}"
    return f"event:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()}"


def _create_event(
    db: Session,
    *,
    provider: str,
    external_event_id: str,
    external_topic: str | None,
    payload: dict,
    signature_valid: bool | None,
    establishment_id: int | None = None,
    payment_id: int | None = None,
) -> tuple[PaymentWebhookEvent, bool]:
    event = PaymentWebhookEvent(
        provider=provider,
        establishment_id=establishment_id,
        payment_id=payment_id,
        external_event_id=external_event_id,
        external_topic=external_topic,
        signature_valid=signature_valid,
        payload=payload,
        processing_status="pending",
        received_at=_utcnow(),
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, False
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(PaymentWebhookEvent)
            .filter(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.external_event_id == external_event_id,
            )
            .first()
        )
        if existing:
            return existing, True
        raise


def validate_basic_hmac_signature(*, raw_body: bytes, provided_signature: str | None, secret: str | None) -> bool | None:
    if not secret:
        return None
    if not provided_signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = provided_signature.strip()
    if received.startswith("sha256="):
        received = received.split("=", 1)[1]
    if "v1=" in received:
        # Formato ts=...,v1=...
        parts = dict(
            item.split("=", 1)
            for item in received.split(",")
            if "=" in item
        )
        received = parts.get("v1", "")
    return hmac.compare_digest(received, expected)


def process_mercadopago_webhook(
    db: Session,
    *,
    payload: dict,
    raw_body: bytes,
    local_payment_id: int | None,
    provider_payment_id_query: str | None,
    webhook_id: str | None,
    topic: str | None,
    signature_header: str | None,
    signature_secret: str | None,
) -> dict:
    provider_payment_id = _extract_provider_payment_id(payload, provider_payment_id_query)
    external_event_id = _extract_external_event_id(payload, provider_payment_id, webhook_id)
    signature_valid = validate_basic_hmac_signature(
        raw_body=raw_body,
        provided_signature=signature_header,
        secret=signature_secret,
    )

    initial_event, is_duplicate = _create_event(
        db,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        external_event_id=external_event_id,
        external_topic=topic or str(payload.get("type") or ""),
        payload=payload,
        signature_valid=signature_valid,
    )
    if is_duplicate:
        return {"status": "ignored", "reason": "evento_duplicado", "event_id": initial_event.external_event_id}

    if signature_valid is False:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Assinatura invalida."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "ignored", "reason": "assinatura_invalida", "event_id": initial_event.external_event_id}

    payment = None
    if local_payment_id is not None:
        payment = db.query(Pagamento).filter(Pagamento.id == local_payment_id).first()

    if payment is None and provider_payment_id:
        payment = (
            db.query(Pagamento)
            .filter(Pagamento.provider_payment_id == str(provider_payment_id))
            .first()
        )

    if payment is None and isinstance(payload.get("external_reference"), str):
        payment = (
            db.query(Pagamento)
            .filter(Pagamento.external_reference == payload["external_reference"])
            .first()
        )

    if payment is None:
        initial_event.processing_status = "ignored"
        initial_event.error_message = "Pagamento nao mapeado."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "ignored", "reason": "pagamento_nao_mapeado", "event_id": initial_event.external_event_id}

    initial_event.payment_id = payment.id
    initial_event.establishment_id = payment.estabelecimento_id
    db.commit()

    account = get_active_payment_account(
        db,
        establishment_id=payment.estabelecimento_id or 0,
        provider=payment.provider,
    )
    if not account:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Conta de pagamento ativa nao encontrada."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "conta_pagamento_inativa", "event_id": initial_event.external_event_id}

    if not provider_payment_id and payment.provider_payment_id:
        provider_payment_id = payment.provider_payment_id
    if not provider_payment_id:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Webhook sem payment_id."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "sem_payment_id", "event_id": initial_event.external_event_id}

    provider_impl = get_payment_provider(payment.provider)
    access_token = get_decrypted_access_token(account)
    provider_payload = provider_impl.get_payment(
        access_token=access_token,
        payment_id=str(provider_payment_id),
    )

    external_reference = str(provider_payload.get("external_reference") or "").strip()
    if external_reference and payment.external_reference and external_reference != payment.external_reference:
        initial_event.processing_status = "failed"
        initial_event.error_message = "External reference divergente."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "external_reference_divergente", "event_id": initial_event.external_event_id}

    updated_payment = apply_payment_update_from_provider(
        db,
        payment=payment,
        provider_payload=provider_payload,
    )

    initial_event.processing_status = "processed"
    initial_event.processed_at = _utcnow()
    db.commit()

    return {
        "status": "ok",
        "event_id": initial_event.external_event_id,
        "payment_id": updated_payment.id,
        "payment_status": updated_payment.status,
        "booking_id": updated_payment.agendamento_id,
        "booking_status": updated_payment.agendamento.status if updated_payment.agendamento else None,
    }
