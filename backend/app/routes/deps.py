from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.security import TokenClaims, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenClaims:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao obrigatoria.",
        )

    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


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
        raise HTTPException(status_code=400, detail="X-Barbearia-Id obrigatorio.")
    try:
        tenant_id = int(x_barbearia_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Barbearia-Id invalido.") from exc

    if claims.is_admin or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant obrigatorio para este recurso.")
    if claims.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant do token difere do tenant da requisicao.")

    barbearia = db.query(Barbearia.id).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")

    return tenant_id


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
