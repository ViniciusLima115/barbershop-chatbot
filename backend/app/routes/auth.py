import secrets
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.models.token_blacklist import TokenBlacklist
from app.routes.deps import get_current_claims
from app.schemas.auth import AdminCheckRequest, AdminCheckResponse, LoginRequest, LoginResponse
from app.security import TokenClaims, create_access_token, verificar_senha

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "vhtech_")
ADMIN_SENHA = os.getenv("ADMIN_SENHA", "@dinizvascaino")


@router.post("/admin-check", response_model=AdminCheckResponse)
def admin_check(payload: AdminCheckRequest):
    is_admin_user = secrets.compare_digest(payload.usuario, ADMIN_USUARIO)
    is_admin_pass = secrets.compare_digest(payload.senha, ADMIN_SENHA)
    return AdminCheckResponse(is_admin=is_admin_user and is_admin_pass)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = payload.usuario.strip().lower()
    senha = payload.senha

    is_admin_user = secrets.compare_digest(usuario, ADMIN_USUARIO)
    is_admin_pass = secrets.compare_digest(senha, ADMIN_SENHA)
    if is_admin_user and is_admin_pass:
        token = create_access_token(
            sub=usuario,
            tenant_id=None,
            is_admin=True,
        )
        return LoginResponse(
            is_admin=True,
            tenant_id=None,
            tenant_name="Administrador",
            plano="premium",
            access_token=token,
            token_type="bearer",
        )

    barbearia = db.query(Barbearia).filter(Barbearia.login == usuario).first()
    if not barbearia or not barbearia.senha:
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    if not verificar_senha(senha, barbearia.senha):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    token = create_access_token(
        sub=usuario,
        tenant_id=barbearia.id,
        is_admin=False,
    )
    return LoginResponse(
        is_admin=False,
        tenant_id=barbearia.id,
        tenant_name=barbearia.nome,
        plano=(barbearia.plano or "basico").lower(),
        access_token=token,
        token_type="bearer",
    )


@router.post("/logout", status_code=200)
def logout(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    if claims.jti:
        expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc).replace(tzinfo=None)  # UTC naive, consistent with utcnow()
        blacklisted = TokenBlacklist(jti=claims.jti, expires_at=expires_at)
        db.merge(blacklisted)  # merge to avoid error if jti already exists
        db.commit()
    return {"detail": "Logout realizado com sucesso."}
