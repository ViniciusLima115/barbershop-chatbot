import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.models.payment_oauth_state import PaymentOAuthState
from app.repositories import notificacao_repository as notificacao_repo
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value, mask_secret
from app.services.payments.provider_factory import get_payment_provider


logger = logging.getLogger(__name__)

STATE_TTL_MINUTES = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "mercado_pago":
        return PAYMENT_PROVIDER_MERCADO_PAGO
    return normalized


def _notify_account_event(
    db: Session,
    *,
    establishment_id: int,
    title: str,
    body: str | None = None,
) -> None:
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=establishment_id,
            tipo="conta_pagamento_desconectada",
            titulo=title,
            corpo=body,
        )
    except Exception:
        logger.exception(
            "Falha ao criar notificacao de conta de pagamento (establishment_id=%s)",
            establishment_id,
        )


def start_connect_flow(
    db: Session,
    *,
    establishment_id: int,
    user_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> str:
    normalized_provider = _normalize_provider(provider)
    provider_impl = get_payment_provider(normalized_provider)

    oauth_state = secrets.token_urlsafe(48)
    expires_at = _utcnow() + timedelta(minutes=STATE_TTL_MINUTES)
    state_row = PaymentOAuthState(
        provider=normalized_provider,
        establishment_id=establishment_id,
        user_sub=user_sub,
        state=oauth_state,
        expires_at=expires_at,
    )
    db.add(state_row)
    db.commit()

    logger.info(
        "Fluxo OAuth iniciado (provider=%s, establishment_id=%s, state=%s)",
        normalized_provider,
        establishment_id,
        mask_secret(oauth_state, head=8, tail=6),
    )

    return provider_impl.build_connect_url(state=oauth_state)


def _consume_state(
    db: Session,
    *,
    provider: str,
    state: str,
) -> PaymentOAuthState:
    now = _utcnow()
    row = (
        db.query(PaymentOAuthState)
        .filter(
            PaymentOAuthState.provider == provider,
            PaymentOAuthState.state == state,
            PaymentOAuthState.consumed_at.is_(None),
        )
        .first()
    )
    if not row:
        raise ValueError("State OAuth invalido.")
    if row.expires_at < now:
        row.consumed_at = now
        db.commit()
        raise ValueError("State OAuth expirado.")
    row.consumed_at = now
    db.flush()
    return row


def get_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    normalized_provider = _normalize_provider(provider)
    return (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == establishment_id,
            PaymentAccount.provider == normalized_provider,
        )
        .first()
    )


def get_active_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    row = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=provider,
    )
    if not row:
        return None
    if row.status != "active":
        return None
    return row


def get_decrypted_access_token(payment_account: PaymentAccount) -> str:
    token = decrypt_sensitive_value(payment_account.access_token_encrypted)
    if not token:
        raise ValueError("Conta de pagamento sem access token valido.")
    return token


def get_masked_admin_credentials(payment_account: PaymentAccount) -> dict[str, str | None]:
    return {
        "client_id_masked": mask_secret(decrypt_sensitive_value(payment_account.client_id_encrypted)),
        "client_secret_masked": mask_secret(decrypt_sensitive_value(payment_account.client_secret_encrypted)),
        "access_token_masked": mask_secret(decrypt_sensitive_value(payment_account.access_token_encrypted)),
        "public_key_masked": mask_secret(decrypt_sensitive_value(payment_account.public_key_encrypted)),
    }


def _set_encrypted_if_provided(payment_account: PaymentAccount, field_name: str, value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    setattr(payment_account, field_name, encrypt_sensitive_value(cleaned) or "")
    return True


def upsert_admin_payment_account(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    account_name: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    public_key: str | None = None,
    status: str = "active",
    internal_notes: str | None = None,
    checkout_hold_minutes: int = 10,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)
    if normalized_provider != PAYMENT_PROVIDER_MERCADO_PAGO:
        raise ValueError("Provider de pagamento nao suportado.")
    if checkout_hold_minutes < 5 or checkout_hold_minutes > 60:
        raise ValueError("checkout_hold_minutes deve ficar entre 5 e 60 minutos.")

    normalized_status = (status or "active").strip().lower()
    if normalized_status not in {"active", "inactive", "error", "revoked"}:
        raise ValueError("Status de conta de pagamento invalido.")

    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    is_new = account is None
    if account is None:
        account = PaymentAccount(
            establishment_id=establishment_id,
            provider=normalized_provider,
            access_token_encrypted="",
            status="inactive",
            created_by_admin_id=admin_sub,
        )
        db.add(account)

    account.account_name = account_name.strip() if account_name and account_name.strip() else None
    account.internal_notes = internal_notes.strip() if internal_notes and internal_notes.strip() else None
    account.checkout_hold_minutes = checkout_hold_minutes
    account.updated_by_admin_id = admin_sub
    account.updated_at = _utcnow()

    token_changed = _set_encrypted_if_provided(account, "access_token_encrypted", access_token)
    _set_encrypted_if_provided(account, "client_id_encrypted", client_id)
    _set_encrypted_if_provided(account, "client_secret_encrypted", client_secret)
    _set_encrypted_if_provided(account, "public_key_encrypted", public_key)

    if normalized_status == "active" and not decrypt_sensitive_value(account.access_token_encrypted):
        raise ValueError("access_token e obrigatorio para ativar pagamentos online.")

    account.status = normalized_status
    if token_changed or is_new:
        account.last_sync_at = _utcnow()

    db.commit()
    db.refresh(account)

    logger.info(
        "Conta Mercado Pago administrada atualizada (establishment_id=%s, provider=%s, status=%s, admin=%s)",
        establishment_id,
        normalized_provider,
        account.status,
        mask_secret(admin_sub),
    )
    return account


def update_admin_payment_account_status(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    status: str,
) -> PaymentAccount:
    account = get_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        raise ValueError("Conta de pagamento nao configurada para este estabelecimento.")

    normalized_status = status.strip().lower()
    if normalized_status not in {"active", "inactive", "error", "revoked"}:
        raise ValueError("Status de conta de pagamento invalido.")
    if normalized_status == "active" and not decrypt_sensitive_value(account.access_token_encrypted):
        raise ValueError("access_token e obrigatorio para ativar pagamentos online.")

    account.status = normalized_status
    account.updated_by_admin_id = admin_sub
    account.updated_at = _utcnow()
    if normalized_status in {"inactive", "revoked", "error"}:
        _notify_account_event(
            db,
            establishment_id=account.establishment_id,
            title="Conta Mercado Pago requer atencao",
            body="A administracao alterou o status da conta de pagamento deste estabelecimento.",
        )
    db.commit()
    db.refresh(account)
    return account


def finalize_oauth_callback(
    db: Session,
    *,
    provider: str,
    state: str,
    code: str,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)
    provider_impl = get_payment_provider(normalized_provider)

    state_row = _consume_state(db, provider=normalized_provider, state=state)
    exchange = provider_impl.exchange_oauth_code(code=code)
    external_user_id = str(exchange.get("external_user_id") or "").strip() or None

    if external_user_id:
        existing_for_other = (
            db.query(PaymentAccount)
            .filter(
                PaymentAccount.provider == normalized_provider,
                PaymentAccount.external_user_id == external_user_id,
                PaymentAccount.establishment_id != state_row.establishment_id,
            )
            .first()
        )
        if existing_for_other:
            db.rollback()
            raise ValueError("Esta conta do Mercado Pago ja esta vinculada a outro estabelecimento.")

    payment_account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == state_row.establishment_id,
            PaymentAccount.provider == normalized_provider,
        )
        .first()
    )
    if not payment_account:
        payment_account = PaymentAccount(
            establishment_id=state_row.establishment_id,
            provider=normalized_provider,
            access_token_encrypted=encrypt_sensitive_value(str(exchange.get("access_token") or "")) or "",
        )
        db.add(payment_account)

    payment_account.external_user_id = external_user_id
    payment_account.external_account_email = exchange.get("external_account_email")
    payment_account.access_token_encrypted = encrypt_sensitive_value(str(exchange.get("access_token") or "")) or ""
    payment_account.refresh_token_encrypted = encrypt_sensitive_value(exchange.get("refresh_token"))
    payment_account.public_key_encrypted = encrypt_sensitive_value(exchange.get("public_key"))
    payment_account.token_expires_at = exchange.get("token_expires_at")
    payment_account.status = "active"
    payment_account.last_sync_at = _utcnow()
    payment_account.updated_at = _utcnow()

    db.commit()
    db.refresh(payment_account)

    logger.info(
        "Conta de pagamento conectada (provider=%s, establishment_id=%s, external_user_id=%s)",
        normalized_provider,
        payment_account.establishment_id,
        mask_secret(payment_account.external_user_id),
    )

    return payment_account


def disconnect_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    account = get_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        return None

    account.status = "revoked"
    account.updated_at = _utcnow()
    _notify_account_event(
        db,
        establishment_id=account.establishment_id,
        title="Conta Mercado Pago desconectada",
        body="Pagamentos online ficaram desabilitados ate reconectar a conta.",
    )
    db.commit()
    db.refresh(account)

    logger.info(
        "Conta de pagamento desconectada (provider=%s, establishment_id=%s)",
        account.provider,
        establishment_id,
    )

    return account


def update_payment_account_settings(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    checkout_hold_minutes: int | None = None,
    status: str | None = None,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)

    if checkout_hold_minutes is not None:
        if checkout_hold_minutes < 5 or checkout_hold_minutes > 60:
            raise ValueError("checkout_hold_minutes deve ficar entre 5 e 60 minutos.")

    normalized_status: str | None = None
    if status is not None:
        normalized_status = status.strip().lower()
        if normalized_status not in {"pending", "active", "inactive", "revoked", "error"}:
            raise ValueError("Status de conta de pagamento invalido.")

    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    if not account:
        if normalized_status == "active":
            raise ValueError("Conecte a conta do Mercado Pago antes de ativar os pagamentos.")
        account = PaymentAccount(
            establishment_id=establishment_id,
            provider=normalized_provider,
            access_token_encrypted="",
            status=normalized_status or "inactive",
            checkout_hold_minutes=checkout_hold_minutes or 10,
        )
        account.updated_at = _utcnow()
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    if checkout_hold_minutes is not None:
        account.checkout_hold_minutes = checkout_hold_minutes
    if normalized_status is not None:
        account.status = normalized_status
        if normalized_status in {"inactive", "revoked", "error"}:
            _notify_account_event(
                db,
                establishment_id=account.establishment_id,
                title="Conta Mercado Pago requer atencao",
                body="Revise a configuracao de pagamentos para manter o checkout online ativo.",
            )
    account.updated_at = _utcnow()

    db.commit()
    db.refresh(account)
    return account
