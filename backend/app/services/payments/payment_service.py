import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import urlencode

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.pagamento import Pagamento
from app.models.servico import Servico
from app.repositories import notificacao_repository as notificacao_repo
from app.services.payments.constants import (
    BOOKING_STATUS_CANCELLED,
    BOOKING_STATUS_CONFIRMED,
    BOOKING_STATUS_EXPIRED,
    BOOKING_STATUS_FAILED,
    BOOKING_STATUS_PENDING_PAYMENT,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_NOT_REQUIRED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_REJECTED,
)
from app.services.payments.payment_account_service import (
    get_active_payment_account,
    get_decrypted_access_token,
)
from app.services.payments.provider_factory import get_payment_provider


logger = logging.getLogger(__name__)

PAYMENT_FINAL_STATUSES = {
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_REJECTED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_EXPIRED,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "mercado_pago":
        return PAYMENT_PROVIDER_MERCADO_PAGO
    return normalized


def normalize_payment_status(raw_status: str | None) -> str:
    status = (raw_status or "").strip().lower()
    if status == "approved":
        return PAYMENT_STATUS_APPROVED
    if status in {"rejected"}:
        return PAYMENT_STATUS_REJECTED
    if status in {"cancelled", "charged_back"}:
        return PAYMENT_STATUS_CANCELLED
    if status in {"refunded"}:
        return PAYMENT_STATUS_REFUNDED
    if status in {"expired"}:
        return PAYMENT_STATUS_EXPIRED
    return PAYMENT_STATUS_PENDING


def validate_service_advance_payment_config(servico: Servico) -> tuple[bool, str | None, float | None]:
    require = bool(getattr(servico, "pagamento_adiantado_obrigatorio", False))
    if not require:
        return False, None, None

    payment_type = (getattr(servico, "advance_payment_type", "") or "full").strip().lower()
    if payment_type not in {"full", "signal"}:
        raise ValueError("Tipo de pagamento adiantado invalido. Use 'full' ou 'signal'.")

    service_price = float(servico.preco or 0)
    if payment_type == "full":
        if service_price <= 0:
            raise ValueError("Servico com pagamento adiantado deve possuir preco maior que zero.")
        return True, payment_type, round(service_price, 2)

    signal_amount = getattr(servico, "advance_payment_amount", None)
    if signal_amount is None:
        raise ValueError("Informe o valor do sinal para este servico.")
    signal_value = round(float(signal_amount), 2)
    if signal_value <= 0:
        raise ValueError("O valor do sinal deve ser maior que zero.")
    if service_price > 0 and signal_value > service_price:
        raise ValueError("O valor do sinal nao pode ser maior que o preco do servico.")
    return True, payment_type, signal_value


def apply_payment_snapshot_from_service(booking: Agendamento, servico: Servico) -> None:
    required, payment_type, amount = validate_service_advance_payment_config(servico)
    booking.payment_required_snapshot = required
    booking.payment_type_snapshot = payment_type
    booking.payment_amount_snapshot = amount
    booking.pagamento_adiantado_exigido = required
    if required:
        booking.payment_status = PAYMENT_STATUS_PENDING
        booking.status = BOOKING_STATUS_PENDING_PAYMENT
    else:
        booking.payment_status = PAYMENT_STATUS_NOT_REQUIRED


def build_checkout_notification_url(payment_id: int) -> str:
    base = os.getenv("BACKEND_PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    query: dict[str, str] = {"payment_id": str(payment_id)}
    webhook_token = os.getenv("MERCADOPAGO_WEBHOOK_TOKEN", "").strip()
    if webhook_token:
        query["token"] = webhook_token
    return f"{base}/webhooks/mercadopago?{urlencode(query)}"


def _booking_conflict_filter(now: datetime):
    return or_(
        Agendamento.status.in_(["pendente", "confirmado", "reagendamento_solicitado"]),
        and_(
            Agendamento.status == BOOKING_STATUS_PENDING_PAYMENT,
            or_(
                Agendamento.payment_hold_expires_at.is_(None),
                Agendamento.payment_hold_expires_at > now,
            ),
        ),
    )


def booking_conflict_query(
    db: Session,
    *,
    establishment_id: int,
    profissional_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_booking_id: int | None = None,
):
    query = (
        db.query(Agendamento)
        .filter(
            Agendamento.estabelecimento_id == establishment_id,
            Agendamento.profissional_id == profissional_id,
            Agendamento.data_hora_inicio < end_at,
            Agendamento.data_hora_fim > start_at,
            _booking_conflict_filter(_utcnow()),
        )
    )
    if exclude_booking_id is not None:
        query = query.filter(Agendamento.id != exclude_booking_id)
    return query


def _notify_payment_event(
    db: Session,
    *,
    booking: Agendamento,
    notif_type: str,
    title: str,
    body: str | None = None,
) -> None:
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=booking.estabelecimento_id,
            agendamento_id=booking.id,
            tipo=notif_type,
            titulo=title,
            corpo=body,
        )
    except Exception:
        logger.exception("Falha ao criar notificacao de pagamento para agendamento %s", booking.id)


def _build_external_reference(booking_id: int) -> str:
    short = str(uuid4())[:12]
    return f"booking:{booking_id}:{short}"


def start_checkout_for_booking(
    db: Session,
    *,
    booking: Agendamento,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    payer_name: str | None = None,
    payer_email: str | None = None,
    payer_phone: str | None = None,
) -> Pagamento:
    normalized_provider = normalize_provider(provider)
    if not booking.payment_required_snapshot:
        raise ValueError("Este agendamento nao exige pagamento adiantado.")
    if booking.estabelecimento_id is None:
        raise ValueError("Agendamento sem estabelecimento associado.")

    account = get_active_payment_account(
        db,
        establishment_id=booking.estabelecimento_id,
        provider=normalized_provider,
    )
    if not account:
        raise ValueError("Conta de pagamento ativa nao encontrada para o estabelecimento.")

    now = _utcnow()
    hold_minutes = max(5, min(int(account.checkout_hold_minutes or 10), 60))
    expires_at = now + timedelta(minutes=hold_minutes)

    existing_payment = (
        db.query(Pagamento)
        .filter(Pagamento.agendamento_id == booking.id)
        .first()
    )
    if (
        existing_payment
        and existing_payment.status == PAYMENT_STATUS_PENDING
        and existing_payment.expires_at
        and existing_payment.expires_at > now
        and existing_payment.checkout_url
    ):
        booking.status = BOOKING_STATUS_PENDING_PAYMENT
        booking.payment_status = PAYMENT_STATUS_PENDING
        booking.payment_hold_expires_at = existing_payment.expires_at
        db.commit()
        db.refresh(existing_payment)
        return existing_payment

    if existing_payment and existing_payment.status == PAYMENT_STATUS_PENDING:
        existing_payment.status = PAYMENT_STATUS_EXPIRED
        existing_payment.external_status = PAYMENT_STATUS_EXPIRED

    amount = float(booking.payment_amount_snapshot or 0)
    if amount <= 0:
        raise ValueError("Valor de pagamento invalido no snapshot do agendamento.")

    payment = existing_payment or Pagamento(
        agendamento_id=booking.id,
        estabelecimento_id=booking.estabelecimento_id,
        payment_account_id=account.id,
        provider=normalized_provider,
        amount=amount,
        status=PAYMENT_STATUS_PENDING,
        currency="BRL",
        platform_fee_amount=0.0,
        expires_at=expires_at,
    )
    if existing_payment is None:
        db.add(payment)

    payment.payment_account_id = account.id
    payment.provider = normalized_provider
    payment.amount = amount
    payment.status = PAYMENT_STATUS_PENDING
    payment.currency = "BRL"
    payment.expires_at = expires_at
    payment.external_reference = payment.external_reference or _build_external_reference(booking.id)

    booking.status = BOOKING_STATUS_PENDING_PAYMENT
    booking.payment_status = PAYMENT_STATUS_PENDING
    booking.payment_hold_expires_at = expires_at

    db.flush()

    provider_impl = get_payment_provider(normalized_provider)
    access_token = get_decrypted_access_token(account)
    title = f"Agendamento #{booking.id}"
    description = f"Pagamento adiantado do servico {booking.servico.nome if booking.servico else ''}".strip()

    try:
        checkout = provider_impl.create_checkout(
            access_token=access_token,
            external_reference=payment.external_reference,
            title=title,
            description=description,
            amount=amount,
            payer_email=payer_email,
            payer_name=payer_name,
            payer_phone=payer_phone,
            metadata={
                "booking_id": booking.id,
                "establishment_id": booking.estabelecimento_id,
                "payment_id": payment.id,
                "provider": normalized_provider,
            },
            notification_url=build_checkout_notification_url(payment.id),
            expires_at=expires_at,
        )
    except Exception:
        payment.status = PAYMENT_STATUS_REJECTED
        payment.external_status = "checkout_creation_failed"
        booking.payment_status = PAYMENT_STATUS_REJECTED
        booking.status = BOOKING_STATUS_FAILED
        booking.payment_hold_expires_at = None
        db.commit()
        raise

    payment.preference_id = checkout["preference_id"]
    payment.checkout_url = checkout["checkout_url"]
    payment.raw_payload = checkout["raw"]
    payment.external_status = PAYMENT_STATUS_PENDING
    booking.provider_preference_id = payment.preference_id
    booking.provider_checkout_reference = payment.external_reference

    db.commit()
    db.refresh(payment)
    return payment


def apply_payment_update_from_provider(
    db: Session,
    *,
    payment: Pagamento,
    provider_payload: dict,
) -> Pagamento:
    now = _utcnow()
    mapped_status = normalize_payment_status(provider_payload.get("status"))
    previous_status = payment.status

    provider_payment_id = provider_payload.get("id")
    if provider_payment_id:
        payment.provider_payment_id = str(provider_payment_id)
    merchant_order = provider_payload.get("order", {}).get("id")
    if merchant_order:
        payment.external_merchant_order_id = str(merchant_order)
    payment.payment_method = (
        provider_payload.get("payment_method_id")
        or provider_payload.get("payment_type_id")
        or payment.payment_method
    )
    payment.external_status = str(provider_payload.get("status") or "")
    payment.raw_payload = provider_payload
    payment.status = mapped_status

    booking = payment.agendamento
    if booking:
        booking.payment_status = mapped_status
        if mapped_status == PAYMENT_STATUS_APPROVED:
            payment.paid_at = now
            booking.status = BOOKING_STATUS_CONFIRMED
            booking.payment_hold_expires_at = None
            if previous_status != PAYMENT_STATUS_APPROVED:
                _notify_payment_event(
                    db,
                    booking=booking,
                    notif_type="pagamento_aprovado",
                    title="Pagamento aprovado",
                    body=f"Pagamento do agendamento #{booking.id} foi aprovado.",
                )
        elif mapped_status == PAYMENT_STATUS_EXPIRED:
            booking.status = BOOKING_STATUS_EXPIRED
            booking.payment_hold_expires_at = None
            _notify_payment_event(
                db,
                booking=booking,
                notif_type="pagamento_expirado",
                title="Pagamento expirado",
                body=f"O pagamento do agendamento #{booking.id} expirou.",
            )
        elif mapped_status in {PAYMENT_STATUS_REJECTED, PAYMENT_STATUS_CANCELLED, PAYMENT_STATUS_REFUNDED}:
            booking.status = BOOKING_STATUS_CANCELLED
            booking.payment_hold_expires_at = None
            _notify_payment_event(
                db,
                booking=booking,
                notif_type="pagamento_falhou",
                title="Pagamento nao concluido",
                body=f"O pagamento do agendamento #{booking.id} nao foi concluido.",
            )
        else:
            booking.status = BOOKING_STATUS_PENDING_PAYMENT

    db.commit()
    db.refresh(payment)
    return payment


def expire_pending_bookings_and_payments(db: Session, *, limit: int = 200) -> int:
    now = _utcnow()
    pendentes = (
        db.query(Agendamento)
        .filter(
            Agendamento.status == BOOKING_STATUS_PENDING_PAYMENT,
            Agendamento.payment_status == PAYMENT_STATUS_PENDING,
            Agendamento.payment_hold_expires_at.is_not(None),
            Agendamento.payment_hold_expires_at <= now,
        )
        .order_by(Agendamento.payment_hold_expires_at.asc())
        .limit(limit)
        .all()
    )
    if not pendentes:
        return 0

    count = 0
    for booking in pendentes:
        booking.status = BOOKING_STATUS_EXPIRED
        booking.payment_status = PAYMENT_STATUS_EXPIRED
        booking.payment_hold_expires_at = None

        payment = (
            db.query(Pagamento)
            .filter(
                Pagamento.agendamento_id == booking.id,
                Pagamento.status == PAYMENT_STATUS_PENDING,
            )
            .first()
        )
        if payment:
            payment.status = PAYMENT_STATUS_EXPIRED
            payment.external_status = PAYMENT_STATUS_EXPIRED

        _notify_payment_event(
            db,
            booking=booking,
            notif_type="pagamento_expirado",
            title="Pagamento expirado",
            body=f"O pagamento do agendamento #{booking.id} expirou e o horario foi liberado.",
        )
        count += 1

    db.commit()
    logger.info("Expiracao de pagamentos pendentes concluida: %s agendamentos expirados.", count)
    return count
