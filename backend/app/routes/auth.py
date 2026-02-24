import secrets
from fastapi import APIRouter

from app.schemas.auth import AdminCheckRequest, AdminCheckResponse

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_USUARIO = "vhtech_"
ADMIN_SENHA = "@dinizvascaino"


@router.post("/admin-check", response_model=AdminCheckResponse)
def admin_check(payload: AdminCheckRequest):
    is_admin_user = secrets.compare_digest(payload.usuario, ADMIN_USUARIO)
    is_admin_pass = secrets.compare_digest(payload.senha, ADMIN_SENHA)
    return AdminCheckResponse(is_admin=is_admin_user and is_admin_pass)
