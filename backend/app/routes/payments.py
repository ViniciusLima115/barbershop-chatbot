import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.servico import Servico
from app.routes.deps import require_admin, tenant_id_from_header
from app.schemas.agendamento import AgendamentoCreate
from app.schemas.pagamentos import (
    AdminPaymentAccountResponse,
    AdminPaymentAccountStatusUpdate,
    AdminPaymentAccountUpsert,
    AdminPaymentEstablishmentResponse,
    AdminPaymentsListResponse,
    BookingPaymentStatusResponse,
    CheckoutResponse,
    PaymentAccountSettingsUpdate,
    PaymentAccountStatusResponse,
    PaymentDetailsResponse,
)
from app.services.agendamento_service import criar_agendamento
from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_NOT_REQUIRED,
)
from app.services.payments.crypto import mask_secret
from app.services.payments.payment_account_service import (
    get_masked_admin_credentials,
    get_payment_account,
    update_admin_payment_account_status,
    upsert_admin_payment_account,
    update_payment_account_settings,
)
from app.services.payments.payment_service import (
    apply_payment_snapshot_from_service,
    start_checkout_for_booking,
)
from app.services.payments.webhook_service import process_mercadopago_webhook


router = APIRouter(tags=["payments"])


def _serialize_payment(payment: Pagamento) -> PaymentDetailsResponse:
    return PaymentDetailsResponse(
        id=payment.id,
        booking_id=payment.agendamento_id,
        establishment_id=payment.estabelecimento_id,
        provider=payment.provider,
        amount=float(payment.amount or 0),
        status=payment.status,  # type: ignore[arg-type]
        payment_method=payment.payment_method,
        external_reference=payment.external_reference,
        external_payment_id=payment.provider_payment_id,
        external_preference_id=payment.preference_id,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        paid_at=payment.paid_at,
        expires_at=payment.expires_at,
    )


def _serialize_admin_payment_account(account: PaymentAccount) -> AdminPaymentAccountResponse:
    masked = get_masked_admin_credentials(account)
    return AdminPaymentAccountResponse(
        id=account.id,
        establishment_id=account.establishment_id,
        provider=account.provider,
        account_name=account.account_name,
        status=account.status,
        client_id_masked=masked["client_id_masked"],
        client_secret_masked=masked["client_secret_masked"],
        access_token_masked=masked["access_token_masked"],
        public_key_masked=masked["public_key_masked"],
        internal_notes=account.internal_notes,
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
        created_by_admin_id=account.created_by_admin_id,
        updated_by_admin_id=account.updated_by_admin_id,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _serialize_checkout(payment: Pagamento) -> CheckoutResponse:
    booking = payment.agendamento
    if not booking:
        raise HTTPException(status_code=500, detail="Pagamento sem agendamento associado.")
    return CheckoutResponse(
        payment_id=payment.id,
        booking_id=payment.agendamento_id,
        external_reference=payment.external_reference,
        preference_id=payment.preference_id or "",
        checkout_url=payment.checkout_url or "",
        amount=float(payment.amount or 0),
        payment_status=payment.status,  # type: ignore[arg-type]
        booking_status=booking.status,
        expires_at=payment.expires_at,
    )


def _get_establishment_or_404(db: Session, establishment_id: int) -> Estabelecimento:
    establishment = db.query(Estabelecimento).filter(Estabelecimento.id == establishment_id).first()
    if not establishment:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return establishment


@router.get("/admin/establishments", response_model=list[AdminPaymentEstablishmentResponse])
def admin_list_establishments_payment_status(
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Estabelecimento, PaymentAccount)
        .outerjoin(
            PaymentAccount,
            (PaymentAccount.establishment_id == Estabelecimento.id)
            & (PaymentAccount.provider == PAYMENT_PROVIDER_MERCADO_PAGO),
        )
        .order_by(Estabelecimento.criado_em.desc(), Estabelecimento.id.desc())
        .all()
    )
    items: list[AdminPaymentEstablishmentResponse] = []
    for establishment, account in rows:
        items.append(
            AdminPaymentEstablishmentResponse(
                id=establishment.id,
                nome=establishment.nome,
                slug=establishment.slug,
                login=establishment.login,
                payment_account_status=account.status if account else "not_configured",
                payment_account_name=account.account_name if account else None,
                payment_account_id=account.id if account else None,
            )
        )
    return items


@router.get("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_get_establishment_payment_account(
    establishment_id: int,
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        raise HTTPException(status_code=404, detail="Conta de pagamento nao configurada.")
    return _serialize_admin_payment_account(account)


@router.post("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_create_establishment_payment_account(
    establishment_id: int,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    try:
        account = upsert_admin_payment_account(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            account_name=payload.account_name,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            public_key=payload.public_key,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_admin_payment_account(account)


@router.patch("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account(
    establishment_id: int,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    try:
        account = upsert_admin_payment_account(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            account_name=payload.account_name,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            public_key=payload.public_key,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_admin_payment_account(account)


@router.patch("/admin/establishments/{establishment_id}/payment-account/status", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account_status(
    establishment_id: int,
    payload: AdminPaymentAccountStatusUpdate,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    try:
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            status=payload.status,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_admin_payment_account(account)


@router.delete("/admin/establishments/{establishment_id}/payment-account", status_code=204)
def admin_remove_establishment_payment_account(
    establishment_id: int,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    try:
        update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            status="revoked",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@router.post("/bookings")
def create_booking_with_optional_checkout(
    payload: AgendamentoCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        created = criar_agendamento(db, payload, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    booking = db.query(Agendamento).filter(Agendamento.id == created["id"]).first()
    if not booking:
        raise HTTPException(status_code=500, detail="Falha ao localizar agendamento criado.")
    servico = db.query(Servico).filter(Servico.id == booking.servico_id).first()
    if not servico:
        raise HTTPException(status_code=500, detail="Servico do agendamento nao encontrado.")

    try:
        apply_payment_snapshot_from_service(booking, servico)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(booking)

    if not booking.payment_required_snapshot:
        return {
            "booking_id": booking.id,
            "booking_status": booking.status,
            "payment_required": False,
            "payment_status": PAYMENT_STATUS_NOT_REQUIRED,
        }

    try:
        payment = start_checkout_for_booking(
            db,
            booking=booking,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            payer_name=booking.cliente_nome,
            payer_email=booking.cliente_email,
            payer_phone=booking.cliente_telefone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "booking_id": booking.id,
        "booking_status": booking.status,
        "payment_required": True,
        "checkout": _serialize_checkout(payment).model_dump(),
    }


@router.post("/bookings/{booking_id}/checkout", response_model=CheckoutResponse)
def create_or_reuse_booking_checkout(
    booking_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Agendamento)
        .filter(
            Agendamento.id == booking_id,
            Agendamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento nao encontrado.")

    if not booking.payment_required_snapshot:
        servico = db.query(Servico).filter(Servico.id == booking.servico_id).first()
        if servico:
            apply_payment_snapshot_from_service(booking, servico)
            db.commit()
            db.refresh(booking)

    if not booking.payment_required_snapshot:
        raise HTTPException(status_code=400, detail="Este agendamento nao exige pagamento adiantado.")

    try:
        payment = start_checkout_for_booking(
            db,
            booking=booking,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            payer_name=booking.cliente_nome,
            payer_email=booking.cliente_email,
            payer_phone=booking.cliente_telefone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_checkout(payment)


@router.get("/payments/{payment_id}", response_model=PaymentDetailsResponse)
def get_payment_by_id(
    payment_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.id == payment_id,
            Pagamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    return _serialize_payment(payment)


@router.get("/bookings/{booking_id}/payment-status", response_model=BookingPaymentStatusResponse)
def get_booking_payment_status(
    booking_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Agendamento)
        .filter(
            Agendamento.id == booking_id,
            Agendamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento nao encontrado.")

    payment = db.query(Pagamento).filter(Pagamento.agendamento_id == booking.id).first()
    return BookingPaymentStatusResponse(
        booking_id=booking.id,
        booking_status=booking.status,
        payment_required=bool(booking.payment_required_snapshot),
        payment_status=booking.payment_status,  # type: ignore[arg-type]
        payment_amount=booking.payment_amount_snapshot,
        payment_type=booking.payment_type_snapshot,
        payment_id=payment.id if payment else None,
    )


@router.post("/webhooks/mercadopago")
async def webhook_mercadopago(
    request: Request,
    topic: str | None = Query(default=None),
    webhook_id: str | None = Query(default=None, alias="id"),
    provider_payment_id: str | None = Query(default=None, alias="data.id"),
    payment_id: int | None = Query(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    expected_token = os.getenv("MERCADOPAGO_WEBHOOK_TOKEN", "").strip()
    if expected_token and token != expected_token:
        raise HTTPException(status_code=401, detail="Webhook token invalido.")

    raw_body = await request.body()
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    signature_header = request.headers.get("x-signature") or request.headers.get("x-hub-signature")
    signature_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip() or None

    try:
        return process_mercadopago_webhook(
            db,
            payload=payload,
            raw_body=raw_body,
            local_payment_id=payment_id,
            provider_payment_id_query=provider_payment_id,
            webhook_id=webhook_id,
            topic=topic,
            signature_header=signature_header,
            signature_secret=signature_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/payments", response_model=AdminPaymentsListResponse)
def admin_list_payments(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payments = (
        db.query(Pagamento)
        .filter(Pagamento.estabelecimento_id == tenant_id)
        .order_by(Pagamento.created_at.desc())
        .limit(200)
        .all()
    )
    return AdminPaymentsListResponse(items=[_serialize_payment(item) for item in payments])


@router.get("/admin/payments/{payment_id}", response_model=PaymentDetailsResponse)
def admin_get_payment(
    payment_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.id == payment_id,
            Pagamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    return _serialize_payment(payment)


@router.get("/admin/payment-account", response_model=PaymentAccountStatusResponse)
def admin_get_payment_account(
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=400,
        detail="Use /admin/establishments/{id}/payment-account para consultar a conta de pagamento.",
    )


@router.patch("/admin/payment-account/settings", response_model=PaymentAccountStatusResponse)
def admin_update_payment_account_settings(
    payload: PaymentAccountSettingsUpdate,
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=400,
        detail="Use /admin/establishments/{id}/payment-account para alterar a conta de pagamento.",
    )
