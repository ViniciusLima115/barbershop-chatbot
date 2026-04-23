from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PaymentStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "refunded",
    "expired",
]


class MercadoPagoConnectResponse(BaseModel):
    authorization_url: str
    state_ttl_minutes: int = 15


class PaymentAccountStatusResponse(BaseModel):
    connected: bool
    provider: str
    status: str
    establishment_id: int
    external_account_email_masked: str | None = None
    external_user_id_masked: str | None = None
    last_sync_at: datetime | None = None
    token_expires_at: datetime | None = None
    checkout_hold_minutes: int = 10


class PaymentAccountSettingsUpdate(BaseModel):
    checkout_hold_minutes: int | None = None
    status: str | None = None


class AdminPaymentAccountUpsert(BaseModel):
    provider: str = "mercadopago"
    account_name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None
    public_key: str | None = None
    status: Literal["active", "inactive", "error"] = "active"
    internal_notes: str | None = None
    checkout_hold_minutes: int = Field(default=10, ge=5, le=60)


class AdminPaymentAccountStatusUpdate(BaseModel):
    status: Literal["active", "inactive", "error", "revoked"]


class AdminPaymentAccountResponse(BaseModel):
    id: int
    establishment_id: int
    provider: str
    account_name: str | None = None
    status: str
    client_id_masked: str | None = None
    client_secret_masked: str | None = None
    access_token_masked: str | None = None
    public_key_masked: str | None = None
    internal_notes: str | None = None
    checkout_hold_minutes: int = 10
    created_by_admin_id: str | None = None
    updated_by_admin_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminPaymentEstablishmentResponse(BaseModel):
    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    payment_account_status: str = "not_configured"
    payment_account_name: str | None = None
    payment_account_id: int | None = None


class CheckoutResponse(BaseModel):
    payment_id: int
    booking_id: int
    external_reference: str
    preference_id: str
    checkout_url: str
    amount: float
    payment_status: PaymentStatus
    booking_status: str
    expires_at: datetime | None = None


class PaymentDetailsResponse(BaseModel):
    id: int
    booking_id: int
    establishment_id: int | None = None
    provider: str
    amount: float
    status: PaymentStatus
    payment_method: str | None = None
    external_reference: str
    external_payment_id: str | None = None
    external_preference_id: str | None = None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    expires_at: datetime | None = None


class BookingPaymentStatusResponse(BaseModel):
    booking_id: int
    booking_status: str
    payment_required: bool
    payment_status: PaymentStatus
    payment_amount: float | None = None
    payment_type: str | None = None
    payment_id: int | None = None


class AdminPaymentsListResponse(BaseModel):
    items: list[PaymentDetailsResponse]
