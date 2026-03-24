import logging
import os
import secrets as _secrets
import time
from uuid import uuid4

import jwt as pyjwt

from passlib.context import CryptContext
from pydantic import BaseModel

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(plain: str) -> str:
    return _pwd_context.hash(plain)


def verificar_senha(plain: str, hashed: str) -> bool:
    """
    Verifica senha suportando transição: aceita bcrypt ($2b$) ou plaintext legado.
    O fallback plaintext é removido após rodar migrate_senhas.py em produção.
    """
    if hashed and hashed.startswith("$2b$"):
        return _pwd_context.verify(plain, hashed)
    # Fallback para senhas ainda não migradas (plaintext)
    logging.warning("verificar_senha: senha plaintext detectada — conta ainda não migrada para bcrypt.")
    return _secrets.compare_digest(plain, hashed or "")


JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "480"))


class TokenClaims(BaseModel):
    sub: str
    tenant_id: int | None = None
    is_admin: bool = False
    jti: str | None = None  # None in old tokens (without jti)
    iat: int
    exp: int


def create_access_token(
    sub: str,
    tenant_id: int | None,
    is_admin: bool,
    expires_minutes: int | None = None,
) -> str:
    now = int(time.time())
    ttl = expires_minutes if expires_minutes is not None else JWT_EXPIRES_MINUTES
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "is_admin": is_admin,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + (ttl * 60),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError as exc:
        raise ValueError("Token expirado.") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ValueError("Token invalido.") from exc
    return TokenClaims(**payload)
