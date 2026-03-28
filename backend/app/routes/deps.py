from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.models.estabelecimento import Estabelecimento
from app.models.token_blacklist import TokenBlacklist
from app.security import TokenClaims, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> TokenClaims:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao obrigatoria.",
        )

    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Check blacklist only if token has jti (old tokens without jti are accepted)
    if claims.jti:
        na_blacklist = db.query(TokenBlacklist).filter(TokenBlacklist.jti == claims.jti).first()
        if na_blacklist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revogado.",
            )

    return claims


def require_admin(claims: TokenClaims = Depends(get_current_claims)) -> TokenClaims:
    if not claims.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao admin.")
    return claims


def tenant_id_from_header(
    x_barbearia_id: Annotated[str | None, Header(alias="X-Barbearia-Id")] = None,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> int:
    if not x_barbearia_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id obrigatorio.")
    try:
        tenant_id = int(x_barbearia_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-Id invalido.") from exc

    if claims.is_admin or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant obrigatorio para este recurso.")
    if claims.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant do token difere do tenant da requisicao.")

    barbearia = db.query(Barbearia.id).filter(Barbearia.id == tenant_id).first()
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
    barbearia = db.query(Barbearia.plano).filter(Barbearia.id == tenant_id).first()
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
    barbearia = db.query(Barbearia.plano).filter(Barbearia.id == tenant_id).first()
    plano = (barbearia.plano or "gratis").lower() if barbearia else "gratis"
    if plano not in ("basico", "premium"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponivel apenas para os planos Basico e Premium.",
        )
    return tenant_id
