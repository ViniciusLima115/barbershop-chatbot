import base64
import json
import time
from datetime import date, timedelta

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

import app.routes.auth as auth_module
from app.main import _validate_runtime_config
from app.limiter import RATE_LIMIT_PAYMENT_STATUS, limiter
from app.models.barbearia import Barbearia
from app.models.token_blacklist import TokenBlacklist
from app.routes.deps import ADMIN_REAUTH_MAX_AGE_SECONDS, require_recent_admin
from app.security import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_SECRET,
    create_access_token,
    decode_access_token,
    hash_senha,
)
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value
from app.services.payments.providers.mercadopago import (
    _is_mercadopago_checkout_url,
    _is_public_https_url,
)
from app.services.session_service import purge_expired_revoked_tokens
from app.time_utils import utcnow_naive


@pytest.fixture(autouse=True)
def reset_rate_limiter_storage():
    limiter._storage = MemoryStorage()
    limiter._limiter = FixedWindowRateLimiter(limiter._storage)


def _public_booking_payload(dados_base, **overrides):
    payload = {
        "barbearia_id": dados_base["barbearia"].id,
        "cliente_nome": "Cliente Seguro",
        "cliente_telefone": "11999998888",
        "cliente_email": "cliente@example.com",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data": (date.today() + timedelta(days=2)).isoformat(),
        "hora_inicio": "10:00",
    }
    payload.update(overrides)
    return payload


def test_public_booking_rejects_client_controlled_price_and_status(client, dados_base):
    payload = _public_booking_payload(
        dados_base,
        preco=0.01,
        status="confirmado",
        payment_status="approved",
    )
    assert client.post("/public/agendamentos", json=payload).status_code == 422


def test_public_booking_cannot_bypass_required_payment(client, db_session, dados_base):
    servico = dados_base["servico"]
    servico.pagamento_adiantado_obrigatorio = True
    servico.advance_payment_type = "full"
    db_session.commit()

    response = client.post("/public/agendamentos", json=_public_booking_payload(dados_base))
    assert response.status_code == 409
    assert "pagamento adiantado" in response.json()["detail"].lower()


def test_public_booking_rejects_sql_injection_identifier(client, dados_base):
    payload = _public_booking_payload(dados_base)
    payload.pop("barbearia_id")
    payload["slug"] = "x' OR 1=1--"
    assert client.post("/public/agendamentos", json=payload).status_code == 422


def test_public_booking_rejects_html_in_customer_name(client, dados_base):
    payload = _public_booking_payload(dados_base, cliente_nome="<script>alert(1)</script>")
    assert client.post("/public/agendamentos", json=payload).status_code == 422


@pytest.mark.parametrize("password", ["curta", "á" * 40])
def test_admin_cannot_create_account_with_unsafe_bcrypt_password(client, make_tenant_headers, password):
    response = client.post(
        "/estabelecimentos/",
        headers=make_tenant_headers(is_admin=True),
        json={
            "nome": "Conta Segura",
            "login": "conta.segura",
            "senha": password,
            "plano": "basico",
            "status_manual": "ativo",
            "vencimento_em": "2027-12-31",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("status_manual", "expires_delta"),
    [("inativo", 30), ("ativo", -1)],
)
def test_inactive_or_expired_tenant_cannot_login(client, db_session, status_manual, expires_delta):
    tenant = Barbearia(
        nome="Tenant Bloqueado",
        login=f"tenant.{status_manual}.{expires_delta}",
        senha=hash_senha("senha-segura"),
        status_manual=status_manual,
        vencimento_em=date.today() + timedelta(days=expires_delta),
    )
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"usuario": tenant.login, "senha": "senha-segura"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario ou senha invalidos."


def test_auth_version_revokes_existing_tenant_session(client, db_session):
    tenant = Barbearia(
        nome="Tenant Revogacao",
        login="tenant.revogacao",
        senha=hash_senha("senha-segura"),
        status_manual="ativo",
        vencimento_em=date.today() + timedelta(days=30),
    )
    db_session.add(tenant)
    db_session.commit()
    login = client.post(
        "/auth/login",
        json={"usuario": tenant.login, "senha": "senha-segura"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    tenant.auth_version += 1
    db_session.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_session_cookie_has_browser_security_flags(client, monkeypatch):
    monkeypatch.setattr(auth_module, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setenv("AUTH_EXPOSE_BEARER_TOKEN", "false")
    response = client.post(
        "/auth/login",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert response.json()["access_token"] is None


def test_cookie_authenticated_write_requires_allowed_origin_in_production(client, monkeypatch):
    login = client.post(
        "/auth/login",
        json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
    )
    assert login.status_code == 200
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")

    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers={"Origin": "https://app.example.com"}).status_code == 200


def test_jwt_rejects_wrong_audience():
    claims = decode_access_token(create_access_token("user", 1, False)).model_dump()
    claims["aud"] = "untrusted-client"
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(ValueError, match="Token invalido"):
        decode_access_token(token)


def test_jwt_rejects_missing_jti():
    claims = decode_access_token(create_access_token("user", 1, False)).model_dump()
    claims.pop("jti")
    claims["iss"] = JWT_ISSUER
    claims["aud"] = JWT_AUDIENCE
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(ValueError, match="Token invalido"):
        decode_access_token(token)


def test_jwt_rejects_missing_session_version():
    claims = decode_access_token(create_access_token("user", 1, False)).model_dump()
    claims.pop("session_version")
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(ValueError, match="Token invalido"):
        decode_access_token(token)


def test_sensitive_admin_operation_requires_recent_authentication():
    claims = decode_access_token(create_access_token("admin", None, True))
    claims.auth_time = int(time.time()) - ADMIN_REAUTH_MAX_AGE_SECONDS - 1

    with pytest.raises(HTTPException) as caught:
        require_recent_admin(claims)

    assert getattr(caught.value, "status_code", None) == 401


def test_expired_revoked_tokens_are_purged(db_session):
    now = utcnow_naive()
    db_session.add_all(
        [
            TokenBlacklist(jti="expired-token", expires_at=now - timedelta(seconds=1)),
            TokenBlacklist(jti="active-token", expires_at=now + timedelta(hours=1)),
        ]
    )
    db_session.commit()

    assert purge_expired_revoked_tokens(db_session) == 1
    assert db_session.get(TokenBlacklist, "expired-token") is None
    assert db_session.get(TokenBlacklist, "active-token") is not None


def test_production_requires_shared_rate_limit_storage(monkeypatch):
    production_config = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://db.example.com/hagendei",
        "JWT_SECRET": "j" * 32,
        "ENCRYPTION_KEY": "e" * 32,
        "PAYMENT_CREDENTIALS_PEPPER": "p" * 32,
        "ADMIN_USUARIO": "admin",
        "ADMIN_SENHA_HASH": "$2b$12$dI.TvYUhHvRnBQ4CcZi7OOFteIkzQrHjEaUuB.Tfu2BytzzIutqG6",
        "ALLOWED_HOSTS": "app.example.com",
        "CORS_ALLOWED_ORIGINS": "https://app.example.com",
        "TRUSTED_PROXY_IPS": "10.0.0.1",
        "INTERNAL_REMINDER_TOKEN": "i" * 32,
        "WHATSAPP_VERIFY_TOKEN": "verify-token",
        "WHATSAPP_APP_SECRET": "w" * 32,
        "FRONTEND_URL": "https://app.example.com",
        "BACKEND_PUBLIC_BASE_URL": "https://api.example.com",
        "BOOKING_PUBLIC_BASE_URL": "https://app.example.com",
        "RATE_LIMIT_STORAGE_URI": "memory://",
        "AUTH_EXPOSE_BEARER_TOKEN": "false",
        "SESSION_COOKIE_SECURE": "true",
        "DOCS_ENABLED": "false",
        "WHATSAPP_ALLOW_UNSIGNED_WEBHOOKS": "false",
        "MEGAAPI_WEBHOOK_ALLOW_UNSIGNED": "false",
    }
    for name, value in production_config.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match="Redis"):
        _validate_runtime_config()

    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "rediss://redis.example.com/0")
    _validate_runtime_config()


def test_meta_webhook_rejects_unsigned_payload(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_ALLOW_UNSIGNED_WEBHOOKS", "false")
    assert client.post("/whatsapp/webhook", json={}).status_code == 401


def test_meta_webhook_rejects_oversized_payload(client):
    response = client.post(
        "/whatsapp/webhook",
        content=b"{}",
        headers={"Content-Length": "65537"},
    )
    assert response.status_code == 413


def test_payment_status_endpoint_is_rate_limited(client):
    request_limit = int(RATE_LIMIT_PAYMENT_STATUS.split("/", 1)[0])
    for index in range(request_limit):
        response = client.get(
            "/public/pagamentos/status",
            params={"external_reference": f"unknown-payment-{index}"},
        )
        assert response.status_code == 404

    blocked = client.get(
        "/public/pagamentos/status",
        params={"external_reference": "unknown-payment-blocked"},
    )
    assert blocked.status_code == 429


def test_refund_operation_is_not_exposed(client, make_tenant_headers):
    headers = make_tenant_headers(is_admin=True)
    first = client.post("/admin/payments/1/refund", headers=headers, json={"amount": 1})
    second = client.post("/admin/payments/1/refund", headers=headers, json={"amount": 1})
    assert first.status_code in {404, 405}
    assert second.status_code == first.status_code


def test_credential_ciphertext_is_randomized_and_tamper_evident():
    first = encrypt_sensitive_value("credential-secret")
    second = encrypt_sensitive_value("credential-secret")
    assert first and second and first != second

    version, key_id, encoded = first.split(":", 2)
    raw = bytearray(base64.urlsafe_b64decode(encoded))
    raw[-1] ^= 1
    tampered = f"{version}:{key_id}:{base64.urlsafe_b64encode(raw).decode('ascii')}"
    with pytest.raises(ValueError, match="descriptografar"):
        decrypt_sensitive_value(tampered)


def test_legacy_ciphertext_can_be_decrypted_during_key_rotation(monkeypatch):
    old_key = b"o" * 32
    new_key = b"n" * 32
    legacy = Fernet(base64.urlsafe_b64encode(old_key)).encrypt(b"legacy-secret").decode("ascii")
    monkeypatch.setenv("ENCRYPTION_KEY", base64.urlsafe_b64encode(new_key).decode("ascii"))
    monkeypatch.setenv("ENCRYPTION_KEY_ID", "new")
    monkeypatch.setenv(
        "ENCRYPTION_KEYRING",
        json.dumps({"old": base64.urlsafe_b64encode(old_key).decode("ascii")}),
    )
    assert decrypt_sensitive_value(legacy) == "legacy-secret"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/webhook",
        "https://localhost/webhook",
        "https://127.0.0.1/webhook",
        "https://10.0.0.8/webhook",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/webhook",
    ],
)
def test_payment_callback_rejects_non_public_urls(url):
    assert _is_public_https_url(url) is False


def test_payment_callback_accepts_public_https_url():
    assert _is_public_https_url("https://api.example.com/webhooks/mercadopago") is True


@pytest.mark.parametrize(
    "url",
    [
        "http://www.mercadopago.com.br/checkout",
        "https://mercadopago.com.br.evil.example/checkout",
        "https://evil.example/checkout",
        "https://user@mercadopago.com.br/checkout",
        "https://mercadopago.com.br:444/checkout",
    ],
)
def test_untrusted_mercadopago_checkout_redirect_is_rejected(url):
    assert _is_mercadopago_checkout_url(url) is False


def test_official_mercadopago_checkout_redirect_is_accepted():
    assert _is_mercadopago_checkout_url("https://www.mercadopago.com.br/checkout/v1/redirect") is True
