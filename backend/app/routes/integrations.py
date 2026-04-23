import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.deps import get_current_claims, tenant_id_from_header
from app.schemas.pagamentos import (
    MercadoPagoConnectResponse,
    PaymentAccountSettingsUpdate,
    PaymentAccountStatusResponse,
)
from app.security import TokenClaims
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.crypto import mask_secret
from app.services.payments.payment_account_service import (
    disconnect_payment_account,
    finalize_oauth_callback,
    get_payment_account,
    start_connect_flow,
    update_payment_account_settings,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _require_tenant_claims(claims: TokenClaims) -> int:
    if claims.is_admin or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Apenas estabelecimentos podem usar esta rota.")
    return claims.tenant_id


@router.post("/mercadopago/connect", response_model=MercadoPagoConnectResponse)
def connect_mercadopago(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    _require_tenant_claims(claims)
    raise HTTPException(
        status_code=403,
        detail="A conta Mercado Pago deste estabelecimento e configurada apenas pela administracao do sistema.",
    )


@router.get("/mercadopago/callback")
def callback_mercadopago(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if error:
        logger.warning("Callback Mercado Pago retornou erro: %s", error)
        return RedirectResponse(
            url=f"{frontend_url}/configuracoes?aba=pagamentos&mp_status=error&reason={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/configuracoes?aba=pagamentos&mp_status=error&reason=missing_params",
            status_code=302,
        )

    try:
        finalize_oauth_callback(
            db,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            state=state,
            code=code,
        )
    except ValueError as exc:
        logger.warning("Falha no callback Mercado Pago: %s", exc)
        return RedirectResponse(
            url=f"{frontend_url}/configuracoes?aba=pagamentos&mp_status=error&reason=callback_failed",
            status_code=302,
        )

    return RedirectResponse(
        url=f"{frontend_url}/configuracoes?aba=pagamentos&mp_status=connected",
        status_code=302,
    )


@router.get("/mercadopago/status", response_model=PaymentAccountStatusResponse)
def status_mercadopago(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    account = get_payment_account(
        db,
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        return PaymentAccountStatusResponse(
            connected=False,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            status="inactive",
            establishment_id=tenant_id,
        )
    return PaymentAccountStatusResponse(
        connected=account.status == "active",
        provider=account.provider,
        status=account.status,
        establishment_id=account.establishment_id,
        external_account_email_masked=None,
        external_user_id_masked=None,
        last_sync_at=account.last_sync_at,
        token_expires_at=account.token_expires_at,
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
    )


@router.post("/mercadopago/disconnect", response_model=PaymentAccountStatusResponse)
def disconnect_mercadopago(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=403,
        detail="A conta Mercado Pago deste estabelecimento e gerenciada apenas pela administracao do sistema.",
    )


@router.patch("/mercadopago/settings", response_model=PaymentAccountStatusResponse)
def update_mercadopago_settings(
    payload: PaymentAccountSettingsUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=403,
        detail="As configuracoes da conta Mercado Pago sao alteradas apenas pela administracao do sistema.",
    )
