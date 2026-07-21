import os
import time
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.models.admin_mfa import AdminMfaSetting
from app.models.token_blacklist import TokenBlacklist
from app.security import SESSION_COOKIE_NAME, TokenClaims, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)
ADMIN_ROLES = {"admin", "super_admin"}
MFA_SETUP_ROLE = "mfa_setup"
BUSINESS_TIMEZONE = ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/Sao_Paulo"))
ADMIN_REAUTH_MAX_AGE_SECONDS = max(
    60,
    min(int(os.getenv("ADMIN_REAUTH_MAX_AGE_SECONDS", "900")), 3600),
)


def has_admin_access(claims: TokenClaims) -> bool:
    return claims.is_admin or (claims.role or "").lower() in ADMIN_ROLES


def tenant_account_is_active(estabelecimento: Estabelecimento) -> bool:
    if (estabelecimento.status_manual or "ativo").strip().lower() != "ativo":
        return False
    today = datetime.now(BUSINESS_TIMEZONE).date()
    if estabelecimento.trial_ativo and estabelecimento.trial_fim_em:
        return estabelecimento.trial_fim_em >= today
    return not estabelecimento.vencimento_em or estabelecimento.vencimento_em >= today


def get_current_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> TokenClaims:
    bearer_token = None
    if credentials and credentials.scheme.lower() == "bearer":
        bearer_token = credentials.credentials
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    token = bearer_token or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao obrigatoria.",
        )

    try:
        claims = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    na_blacklist = db.query(TokenBlacklist).filter(TokenBlacklist.jti == claims.jti).first()
    if na_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revogado.",
        )

    if cookie_token and not bearer_token and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env in {"prod", "production"}:
            origin = request.headers.get("origin", "").rstrip("/")
            allowed = {
                item.strip().rstrip("/")
                for item in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
                if item.strip()
            }
            if not origin or origin not in allowed:
                raise HTTPException(status_code=403, detail="Origem da requisicao nao autorizada.")

    if claims.tenant_id is not None:
        estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
        if (
            not estabelecimento
            or not tenant_account_is_active(estabelecimento)
            or int(estabelecimento.auth_version or 0) != claims.session_version
        ):
            raise HTTPException(status_code=401, detail="Sessao revogada.")
    elif claims.is_admin:
        setting = db.get(AdminMfaSetting, claims.sub.strip().lower())
        if (
            not setting
            or not setting.enabled
            or int(setting.session_version or 0) != claims.session_version
        ):
            raise HTTPException(status_code=401, detail="MFA obrigatorio para o acesso administrativo.")
    elif (claims.role or "").lower() == MFA_SETUP_ROLE:
        setting = db.get(AdminMfaSetting, claims.sub.strip().lower())
        if setting and int(setting.session_version or 0) != claims.session_version:
            raise HTTPException(status_code=401, detail="Sessao revogada.")

    return claims


def require_admin(claims: TokenClaims = Depends(get_current_claims)) -> TokenClaims:
    if not has_admin_access(claims):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao admin.")
    return claims


def require_recent_admin(claims: TokenClaims = Depends(require_admin)) -> TokenClaims:
    authenticated_at = claims.auth_time or claims.iat
    if int(time.time()) - authenticated_at > ADMIN_REAUTH_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reautenticacao obrigatoria para esta operacao sensivel.",
        )
    return claims


def require_admin_mfa_setup(claims: TokenClaims = Depends(get_current_claims)) -> TokenClaims:
    if not claims.is_admin and (claims.role or "").lower() != MFA_SETUP_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao superadmin.")
    authenticated_at = claims.auth_time or claims.iat
    if int(time.time()) - authenticated_at > ADMIN_REAUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reautenticacao obrigatoria.")
    return claims


def tenant_id_from_header(
    x_estabelecimento_id: Annotated[str | None, Header(alias="X-Estabelecimento-Id")] = None,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> int:
    if not x_estabelecimento_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id obrigatorio.")
    try:
        tenant_id = int(x_estabelecimento_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-Id invalido.") from exc

    if has_admin_access(claims) or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant obrigatorio para este recurso.")
    if claims.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant do token difere do tenant da requisicao.")

    barbearia = db.query(Estabelecimento.id).filter(Estabelecimento.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

    return tenant_id


def get_current_estabelecimento(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> Estabelecimento:
    est = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return est


# Manter alias antigo para código legado
get_current_barbearia = get_current_estabelecimento


def verificar_plano_premium(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> int:
    barbearia = db.query(Estabelecimento.plano).filter(Estabelecimento.id == tenant_id).first()
    if not barbearia or barbearia.plano != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponivel apenas para o plano Premium.",
        )
    return tenant_id


def verificar_plano_minimo_basico(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> int:
    """Permite acesso para planos 'basico' e 'premium'. Bloqueia 'gratis'."""
    barbearia = db.query(Estabelecimento.plano).filter(Estabelecimento.id == tenant_id).first()
    plano = (barbearia.plano or "gratis").lower() if barbearia else "gratis"
    if plano not in ("basico", "premium"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponivel apenas para os planos Basico e Premium.",
        )
    return tenant_id
