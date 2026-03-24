import base64
import hashlib
import hmac
import json
import logging
import os
import secrets as _secrets
import time

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
    iat: int
    exp: int


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _assinar(mensagem: str) -> str:
    assinatura = hmac.new(
        JWT_SECRET.encode("utf-8"),
        mensagem.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(assinatura)


def _encode(payload: dict) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    mensagem = f"{header_b64}.{payload_b64}"
    assinatura = _assinar(mensagem)
    return f"{mensagem}.{assinatura}"


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
        "iat": now,
        "exp": now + (ttl * 60),
    }
    return _encode(payload)


def decode_access_token(token: str) -> TokenClaims:
    partes = token.split(".")
    if len(partes) != 3:
        raise ValueError("Token invalido.")

    header_b64, payload_b64, assinatura_recebida = partes
    mensagem = f"{header_b64}.{payload_b64}"
    assinatura_esperada = _assinar(mensagem)
    if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
        raise ValueError("Token invalido.")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Token invalido.") from exc

    if header.get("alg") != JWT_ALGORITHM:
        raise ValueError("Algoritmo de token invalido.")

    claims = TokenClaims(**payload)
    if claims.exp <= int(time.time()):
        raise ValueError("Token expirado.")
    return claims
