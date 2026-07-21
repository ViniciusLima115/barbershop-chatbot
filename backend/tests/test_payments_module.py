from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from app.models.agendamento import Agendamento
from app.models.admin_audit_log import AdminAuditLog
from app.models.estabelecimento import Estabelecimento
from app.models.notificacao import Notificacao
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_integration import PaymentIntegration
from app.models.payment_oauth_state import PaymentOAuthState
from app.models.profissional import Profissional
from app.models.servico import Servico
from app.services.payments import payment_account_service, payment_integration_service, payment_service, webhook_service
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.crypto import (
    decrypt_json_payload,
    decrypt_secret,
    decrypt_sensitive_value,
    encrypt_secret,
    encrypt_sensitive_value,
    mask_secret,
)
from app.services.payments.providers.mercadopago import MercadoPagoProvider
from app.security import create_access_token


class DummyProvider:
    def __init__(self):
        self.webhook_calls = 0
        self.last_checkout_access_token: str | None = None
        self.checkout_access_tokens: list[str] = []
        self.checkout_idempotency_keys: list[str] = []
        self.get_payment_access_tokens: list[str] = []
        self.search_payment_access_tokens: list[str] = []
        self.search_payment_payloads: dict[str, dict | None] = {}

    def build_connect_url(self, *, state: str) -> str:
        return f"https://dummy.example/oauth?state={state}"

    def exchange_oauth_code(self, *, code: str):
        return {
            "access_token": "mp-access-token",
            "refresh_token": "mp-refresh-token",
            "public_key": "mp-public-key",
            "token_expires_at": datetime.utcnow() + timedelta(hours=1),
            "external_user_id": f"user-{code}",
            "external_account_email": "owner@example.com",
        }

    def create_checkout(
        self,
        *,
        access_token: str,
        idempotency_key: str,
        external_reference: str,
        title: str,
        description: str,
        amount: float,
        payer_email: str | None,
        payer_name: str | None,
        payer_phone: str | None,
        metadata: dict,
        notification_url: str,
        return_urls: dict[str, str] | None,
        expires_at: datetime | None,
    ):
        self.last_checkout_access_token = access_token
        self.checkout_access_tokens.append(access_token)
        self.checkout_idempotency_keys.append(idempotency_key)
        return {
            "preference_id": f"pref-{external_reference}",
            "checkout_url": f"https://www.mercadopago.com.br/checkout/{external_reference}",
            "raw": {
                "external_reference": external_reference,
                "amount": amount,
                "notification_url": notification_url,
                "return_urls": return_urls,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        }

    def get_payment(self, *, access_token: str, payment_id: str):
        self.webhook_calls += 1
        self.get_payment_access_tokens.append(access_token)
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": "",
            "payment_method_id": "pix",
        }

    def search_payment_by_external_reference(self, *, access_token: str, external_reference: str):
        self.search_payment_access_tokens.append(access_token)
        return self.search_payment_payloads.get(external_reference)

    def refund_payment(self, *, access_token: str, payment_id: str):
        return {"id": payment_id, "status": "refunded"}

    def validate_access_token(self, *, access_token: str):
        return {
            "valid": access_token != "invalid-token",
            "message": "Credencial Mercado Pago validada com sucesso." if access_token != "invalid-token" else "Credencial recusada pelo Mercado Pago.",
            "external_user_id": "mp-user-1" if access_token != "invalid-token" else None,
        }



def _patch_providers(monkeypatch: pytest.MonkeyPatch, provider: DummyProvider):
    monkeypatch.setattr(payment_account_service, "get_payment_provider", lambda _provider: provider)
    monkeypatch.setattr(payment_integration_service, "get_payment_provider", lambda _provider: provider)
    monkeypatch.setattr(payment_service, "get_payment_provider", lambda _provider: provider)
    monkeypatch.setattr(webhook_service, "get_payment_provider", lambda _provider: provider)



def _seed_tenant_bundle(db_session, *, tenant_name: str, require_advance_payment: bool):
    tenant = Estabelecimento(nome=tenant_name, endereco="Rua A, 1", plano="premium")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    profissional = Profissional(nome=f"Prof {tenant_name}", estabelecimento_id=tenant.id)
    servico = Servico(
        nome=f"Servico {tenant_name}",
        duracao_minutos=40,
        preco=100.0,
        estabelecimento_id=tenant.id,
        pagamento_adiantado_obrigatorio=require_advance_payment,
        advance_payment_type="full" if require_advance_payment else None,
    )
    db_session.add_all([profissional, servico])
    db_session.commit()
    db_session.refresh(profissional)
    db_session.refresh(servico)

    return tenant, profissional, servico



def _create_active_payment_account(db_session, *, tenant_id: int, external_user_id: str = "mp-user-1"):
    account = PaymentAccount(
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        external_user_id=external_user_id,
        external_account_email="owner@example.com",
        access_token_encrypted=encrypt_sensitive_value("token-active") or "",
        refresh_token_encrypted=encrypt_sensitive_value("token-refresh"),
        public_key_encrypted=encrypt_sensitive_value("public-key"),
        status="active",
        checkout_hold_minutes=10,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account



def _tenant_headers(make_tenant_headers, tenant_id: int):
    return make_tenant_headers(tenant_id)


def _validate_integration(client, make_tenant_headers, tenant_id: int, environment: str = "production"):
    response = client.post(
        f"/admin/establishments/{tenant_id}/payment-integrations/mercado-pago/validate",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": environment},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    return response


def _mercadopago_signature(*, secret: str, data_id: str, request_id: str, ts: str | None = None) -> str:
    ts = ts or str(int(time.time()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _webhook_headers(data_id: str, *, request_id: str, secret: str = "test-mercadopago-webhook-secret") -> dict[str, str]:
    return {
        "x-request-id": request_id,
        "x-signature": _mercadopago_signature(secret=secret, data_id=data_id, request_id=request_id),
    }


def test_admin_creates_mercadopago_account_for_establishment(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin MP", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "account_name": "Conta Principal",
            "client_id": "client-id-admin",
            "client_secret": "client-secret-admin",
            "access_token": "access-token-admin",
            "public_key": "public-key-admin",
            "status": "active",
            "internal_notes": "Conta cadastrada pelo admin.",
            "checkout_hold_minutes": 15,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["account_name"] == "Conta Principal"
    assert body["access_token_masked"] == "ac***in"
    assert "access-token-admin" not in str(body)

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert "access-token-admin" not in account.access_token_encrypted
    assert decrypt_sensitive_value(account.access_token_encrypted) == "access-token-admin"
    assert decrypt_sensitive_value(account.client_secret_encrypted) == "client-secret-admin"

    integration = (
        db_session.query(PaymentIntegration)
        .filter(PaymentIntegration.establishment_id == tenant.id)
        .first()
    )
    assert integration is not None
    assert integration.environment == "production"
    assert integration.status == "active"
    assert integration.validation_status == "not_validated"
    assert integration.credentials_fingerprint
    assert "access-token-admin" not in integration.credentials_encrypted
    assert "public-key-admin" not in integration.credentials_encrypted
    assert "Conta cadastrada pelo admin." not in integration.credentials_encrypted
    stored_credentials = decrypt_json_payload(integration.credentials_encrypted)
    assert stored_credentials == {
        "access_token": "access-token-admin",
        "client_id": "client-id-admin",
        "client_secret": "client-secret-admin",
        "public_key": "public-key-admin",
        "notes": "Conta cadastrada pelo admin.",
    }
    assert integration.internal_notes is None


def test_admin_payment_integration_masks_webhook_secret(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin MP Webhook", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "environment": "sandbox",
            "account_name": "Conta Sandbox",
            "access_token": "sandbox-access-token",
            "webhook_secret": "sandbox-webhook-secret",
            "status": "pending_validation",
            "checkout_hold_minutes": 12,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "sandbox"
    assert body["status"] == "pending_validation"
    assert body["webhook_secret_masked"] == "sa***et"
    assert "sandbox-webhook-secret" not in str(body)

    integration = (
        db_session.query(PaymentIntegration)
        .filter(
            PaymentIntegration.establishment_id == tenant.id,
            PaymentIntegration.environment == "sandbox",
        )
        .first()
    )
    assert integration is not None
    assert "sandbox-webhook-secret" not in integration.credentials_encrypted
    stored_credentials = decrypt_json_payload(integration.credentials_encrypted)
    assert stored_credentials["access_token"] == "sandbox-access-token"
    assert stored_credentials["webhook_secret"] == "sandbox-webhook-secret"


def test_admin_rejects_duplicate_mercadopago_fingerprint_between_establishments(client, db_session, make_tenant_headers):
    tenant_a, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Fingerprint A", require_advance_payment=False)
    tenant_b, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Fingerprint B", require_advance_payment=False)

    payload = {
        "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
        "environment": "production",
        "access_token": "shared-access-token",
        "status": "active",
        "checkout_hold_minutes": 10,
    }

    first = client.post(
        f"/admin/establishments/{tenant_a.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json=payload,
    )
    second = client.post(
        f"/admin/establishments/{tenant_b.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={**payload, "client_id": "different-client-id"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert "ja esta vinculada" in second.json()["detail"]


def test_admin_payment_integrations_endpoint_returns_only_masked_status(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Integration List", require_advance_payment=False)
    saved = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "public_key": "APP_USR-public-key",
            "access_token": "APP_USR-access-token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "webhook_secret": "webhook-secret",
            "notes": "Notas privadas",
        },
    )
    assert saved.status_code == 200

    listed = client.get(
        f"/admin/establishments/{tenant.id}/payment-integrations",
        headers=make_tenant_headers(is_admin=True),
    )

    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    item = body[0]
    assert item["provider"] == PAYMENT_PROVIDER_MERCADO_PAGO
    assert item["environment"] == "production"
    assert item["status"] == "active"
    assert item["has_client_id"] is True
    assert item["has_client_secret"] is True
    assert item["access_token_masked"] == "AP***en"
    assert "APP_USR-access-token" not in str(body)
    assert "APP_USR-public-key" not in str(body)
    assert "client-secret" not in str(body)
    assert "webhook-secret" not in str(body)
    assert "credentials_encrypted" not in str(body)


def test_admin_payment_integration_permissions_cover_admin_tenant_client_and_anonymous(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Permission Matrix", require_advance_payment=False)
    customer_token = create_access_token(sub="cliente-final", tenant_id=None, is_admin=False, role="client")

    admin = client.get(
        f"/admin/establishments/{tenant.id}/payment-integrations",
        headers=make_tenant_headers(is_admin=True),
    )
    tenant_user = client.get(
        f"/admin/establishments/{tenant.id}/payment-integrations",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )
    final_customer = client.get(
        f"/admin/establishments/{tenant.id}/payment-integrations",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    anonymous = client.get(f"/admin/establishments/{tenant.id}/payment-integrations")

    assert admin.status_code == 200
    assert tenant_user.status_code == 403
    assert final_customer.status_code == 403
    assert anonymous.status_code == 401


def test_payment_secret_helpers_encrypt_decrypt_and_mask_values():
    value = "APP_USR-round-trip-token"

    encrypted = encrypt_secret(value)

    assert encrypted is not None
    assert encrypted != value
    assert value not in encrypted
    assert decrypt_secret(encrypted) == value
    assert mask_secret(value) == "AP***en"
    assert mask_secret("short") == "*****"


def test_admin_payment_credentials_audit_log_never_stores_secrets(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Audit MP", require_advance_payment=False)
    headers = {
        **make_tenant_headers(is_admin=True),
        "x-forwarded-for": "203.0.113.10",
        "user-agent": "pytest-admin-client",
    }

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=headers,
        json={
            "environment": "production",
            "public_key": "audit-public-key",
            "access_token": "audit-access-token",
            "client_id": "audit-client-id",
            "client_secret": "audit-client-secret",
            "webhook_secret": "audit-webhook-secret",
            "notes": "Observacao segura",
        },
    )

    assert response.status_code == 200
    log = (
        db_session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.establishment_id == tenant.id,
            AdminAuditLog.action == "payment_credentials_created",
        )
        .first()
    )
    assert log is not None
    assert log.admin_user_id == "admin"
    assert log.ip_address == "testclient"
    assert log.ip_address != headers["x-forwarded-for"]
    assert log.user_agent == "pytest-admin-client"
    assert log.audit_metadata["provider"] == PAYMENT_PROVIDER_MERCADO_PAGO
    assert log.audit_metadata["environment"] == "production"
    assert log.audit_metadata["status"] == "active"
    serialized_metadata = str(log.audit_metadata)
    assert "audit-access-token" not in serialized_metadata
    assert "audit-client-secret" not in serialized_metadata
    assert "audit-webhook-secret" not in serialized_metadata
    assert "credentials_encrypted" not in serialized_metadata
    assert "access_token" not in serialized_metadata
    assert "client_secret" not in serialized_metadata
    assert "webhook_secret" not in serialized_metadata


def test_payment_integration_service_logs_do_not_receive_plain_credentials(db_session, monkeypatch):
    captured_logs = []

    def capture_info(message, *args, **kwargs):
        captured_logs.append((message, args, kwargs))

    monkeypatch.setattr(payment_integration_service.logger, "info", capture_info)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Log Safety", require_advance_payment=False)

    integration = payment_integration_service.upsert_admin_payment_integration(
        db_session,
        establishment_id=tenant.id,
        admin_sub="admin-log",
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        environment="production",
        public_key="log-public-key",
        access_token="log-access-token-secret",
        client_id="log-client-id",
        client_secret="log-client-secret",
        webhook_secret="log-webhook-secret",
        internal_notes="log notes",
    )

    assert integration.id is not None
    assert captured_logs
    serialized_logs = str(captured_logs)
    assert "log-access-token-secret" not in serialized_logs
    assert "log-client-secret" not in serialized_logs
    assert "log-webhook-secret" not in serialized_logs
    assert "credentials_encrypted" not in serialized_logs


def test_admin_payment_validation_failure_is_audited(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Audit Validation", require_advance_payment=False)

    created = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "sandbox", "access_token": "invalid-token"},
    )
    assert created.status_code == 200

    validated = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago/validate",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "sandbox"},
    )

    assert validated.status_code == 200
    assert validated.json()["valid"] is False
    log = (
        db_session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.establishment_id == tenant.id,
            AdminAuditLog.action == "payment_credentials_validation_failed",
        )
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    assert log is not None
    assert log.audit_metadata["provider"] == PAYMENT_PROVIDER_MERCADO_PAGO
    assert log.audit_metadata["environment"] == "sandbox"
    assert log.audit_metadata["valid"] is False
    assert "invalid-token" not in str(log.audit_metadata)


def test_admin_payment_integration_rejects_unexpected_fields_and_query_credentials(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Validation Strict", require_advance_payment=False)
    headers = make_tenant_headers(is_admin=True)

    unexpected = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=headers,
        json={
            "environment": "production",
            "access_token": "strict-access-token",
            "unexpected": "x",
        },
    )
    query_secret = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago?access_token=leak",
        headers=headers,
        json={
            "environment": "production",
            "access_token": "strict-access-token",
        },
    )

    assert unexpected.status_code == 422
    assert query_secret.status_code == 400
    assert "URL" in query_secret.json()["detail"]


def test_admin_payment_integration_requires_https_in_production(client, db_session, make_tenant_headers, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant HTTPS", require_advance_payment=False)
    headers = make_tenant_headers(is_admin=True)

    rejected = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers={**headers, "x-forwarded-proto": "https"},
        json={"environment": "production", "access_token": "https-access-token"},
    )
    accepted = client.post(
        f"https://testserver/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=headers,
        json={"environment": "production", "access_token": "https-access-token"},
    )

    assert rejected.status_code == 400
    assert "HTTPS" in rejected.json()["detail"]
    assert accepted.status_code == 200


def test_super_admin_can_manage_payment_credentials(client, db_session):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Super Admin", require_advance_payment=False)
    token = create_access_token(sub="super", tenant_id=None, is_admin=False, role="super_admin")

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers={"Authorization": f"Bearer {token}"},
        json={"environment": "production", "access_token": "super-access-token"},
    )

    assert response.status_code == 200


def test_admin_payment_integration_patch_ignores_empty_and_requires_clear_flag(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Integration Patch", require_advance_payment=False)
    created = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "public_key": "patch-public-key-original",
            "access_token": "patch-access-token",
            "client_id": "patch-client-id-original",
            "client_secret": "client-secret-original",
            "webhook_secret": "webhook-secret-original",
            "notes": "Notas originais",
        },
    )
    assert created.status_code == 200

    updated_one_field = client.patch(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "public_key": "patch-public-key-updated",
        },
    )
    assert updated_one_field.status_code == 200
    assert "patch-public-key-updated" not in str(updated_one_field.json())
    integration = db_session.query(PaymentIntegration).filter(PaymentIntegration.establishment_id == tenant.id).first()
    assert integration is not None
    credentials = decrypt_json_payload(integration.credentials_encrypted)
    assert credentials["public_key"] == "patch-public-key-updated"
    assert credentials["access_token"] == "patch-access-token"
    assert credentials["client_id"] == "patch-client-id-original"
    assert credentials["client_secret"] == "client-secret-original"
    assert credentials["webhook_secret"] == "webhook-secret-original"
    assert credentials["notes"] == "Notas originais"

    ignored_empty = client.patch(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "client_secret": "",
            "webhook_secret": "",
        },
    )
    assert ignored_empty.status_code == 200
    db_session.refresh(integration)
    credentials = decrypt_json_payload(integration.credentials_encrypted)
    assert credentials["client_secret"] == "client-secret-original"
    assert credentials["webhook_secret"] == "webhook-secret-original"

    cleared = client.patch(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "clear_client_secret": True,
            "clear_webhook_secret": True,
        },
    )
    assert cleared.status_code == 200
    db_session.refresh(integration)
    credentials = decrypt_json_payload(integration.credentials_encrypted)
    assert "client_secret" not in credentials
    assert "webhook_secret" not in credentials
    assert credentials["access_token"] == "patch-access-token"


def test_admin_can_disable_payment_integration(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Disable Integration", require_advance_payment=False)
    created = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "production", "access_token": "disable-access-token"},
    )
    assert created.status_code == 200

    disabled = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago/disable",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "production"},
    )

    assert disabled.status_code == 200
    assert disabled.json()["status"] == "inactive"
    integration = db_session.query(PaymentIntegration).filter(PaymentIntegration.establishment_id == tenant.id).first()
    assert integration is not None
    assert integration.status == "inactive"
    audit = (
        db_session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.establishment_id == tenant.id,
            AdminAuditLog.action == "payment_credentials_disabled",
        )
        .first()
    )
    assert audit is not None


def test_admin_can_validate_mercadopago_integration(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Integration Validate", require_advance_payment=False)
    created = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "sandbox",
            "access_token": "valid-token",
        },
    )
    assert created.status_code == 200

    validated = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago/validate",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "sandbox"},
    )

    assert validated.status_code == 200
    body = validated.json()
    assert body["valid"] is True
    assert body["validation_status"] == "valid"
    assert "valid-token" not in str(body)
    integration = db_session.query(PaymentIntegration).filter(PaymentIntegration.establishment_id == tenant.id).first()
    assert integration is not None
    db_session.refresh(integration)
    assert integration.validation_status == "valid"
    assert integration.last_validated_at is not None


def test_admin_test_checkout_requires_production_confirmation(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Integration Test Checkout", require_advance_payment=False)
    created = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "access_token": "test-checkout-token",
        },
    )
    assert created.status_code == 200

    blocked = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago/test-checkout",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "production"},
    )
    allowed = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago/test-checkout",
        headers=make_tenant_headers(is_admin=True),
        json={"environment": "production", "confirm_production": True},
    )

    assert blocked.status_code == 400
    assert "confirm_production" in blocked.json()["detail"]
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "created"
    assert "test-checkout-token" not in str(allowed.json())


def test_admin_edits_mercadopago_account_without_exposing_credentials(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin Edit", require_advance_payment=False)
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    response = client.patch(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "account_name": "Conta Atualizada",
            "access_token": "new-access-token",
            "status": "active",
            "internal_notes": "Credenciais trocadas.",
            "checkout_hold_minutes": 25,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_name"] == "Conta Atualizada"
    assert body["checkout_hold_minutes"] == 25
    assert "new-access-token" not in str(body)

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert decrypt_sensitive_value(account.access_token_encrypted) == "new-access-token"


def test_tenant_cannot_access_admin_payment_account_endpoints(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Bloqueado Admin", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "access_token": "tenant-should-not-save",
            "status": "active",
        },
    )

    assert response.status_code == 403

    integrations = client.get(
        f"/admin/establishments/{tenant.id}/payment-integrations",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )
    upsert = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
        json={"environment": "production", "access_token": "tenant-should-not-save"},
    )
    assert integrations.status_code == 403
    assert upsert.status_code == 403


def test_tenant_cannot_connect_or_disconnect_mercadopago_account(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Sem Connect", require_advance_payment=False)

    connect = client.post("/integrations/mercadopago/connect", headers=_tenant_headers(make_tenant_headers, tenant.id))
    disconnect = client.post("/integrations/mercadopago/disconnect", headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert connect.status_code == 403
    assert disconnect.status_code == 403



def test_connect_mercadopago_account_success(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant A", require_advance_payment=False)

    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant.id,
        user_sub="tenant-user",
        state="state-123",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    account = payment_account_service.finalize_oauth_callback(
        db_session,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        state="state-123",
        code="abc",
    )

    assert account.establishment_id == tenant.id
    assert account.status == "active"
    assert account.external_user_id == "user-abc"
    assert "mp-access-token" not in account.access_token_encrypted
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token"



def test_prevent_same_mercadopago_account_in_two_tenants(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant_a, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant A", require_advance_payment=False)
    tenant_b, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant B", require_advance_payment=False)

    account = PaymentAccount(
        establishment_id=tenant_a.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        external_user_id="user-shared",
        access_token_encrypted=encrypt_sensitive_value("token-1") or "",
        status="active",
    )
    db_session.add(account)
    db_session.commit()

    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant_b.id,
        user_sub="tenant-b-user",
        state="state-dup",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    provider.exchange_oauth_code = lambda *, code: {
        "access_token": "token-2",
        "refresh_token": "refresh-2",
        "public_key": "pk-2",
        "token_expires_at": datetime.utcnow() + timedelta(hours=1),
        "external_user_id": "user-shared",
        "external_account_email": "shared@example.com",
    }

    with pytest.raises(ValueError, match="ja esta vinculada a outro estabelecimento"):
        payment_account_service.finalize_oauth_callback(
            db_session,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            state="state-dup",
            code="dup",
        )



def test_update_settings_creates_placeholder_account_when_not_connected(db_session):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Settings", require_advance_payment=False)

    account = payment_account_service.update_payment_account_settings(
        db_session,
        establishment_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        checkout_hold_minutes=20,
    )

    assert account.establishment_id == tenant.id
    assert account.provider == PAYMENT_PROVIDER_MERCADO_PAGO
    assert account.status == "inactive"
    assert account.checkout_hold_minutes == 20
    assert account.access_token_encrypted == ""


def test_update_settings_cannot_activate_without_connected_account(db_session):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Activate", require_advance_payment=False)

    with pytest.raises(ValueError, match="Conecte a conta do Mercado Pago"):
        payment_account_service.update_payment_account_settings(
            db_session,
            establishment_id=tenant.id,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            status="active",
        )


def test_checkout_uses_active_payment_integration(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Integration Checkout",
        require_advance_payment=True,
    )

    configured = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "environment": "production",
            "account_name": "Conta Checkout",
            "access_token": "integration-checkout-token",
            "webhook_secret": "integration-webhook-secret",
            "status": "active",
            "checkout_hold_minutes": 18,
        },
    )
    assert configured.status_code == 200
    _validate_integration(client, make_tenant_headers, tenant.id)

    payload = {
        "telefone": "11999991000",
        "nome_cliente": "Cliente Integracao",
        "cliente_email": "cliente-integracao@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    created = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert created.status_code == 200
    assert provider.last_checkout_access_token == "integration-checkout-token"
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == created.json()["booking_id"]).first()
    assert payment is not None
    assert payment.payment_integration_id is not None
    notification_url = payment.raw_payload["notification_url"]
    assert "external_reference=" in notification_url
    assert "token=" not in notification_url
    assert "payment_id=" not in notification_url


def test_checkout_uses_each_establishment_own_credentials(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout A",
        require_advance_payment=True,
    )
    tenant_b, profissional_b, servico_b = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout B",
        require_advance_payment=True,
    )

    token_a = "APP_USR-token-barbearia-A-123456"
    token_b = "APP_USR-token-barbearia-B-abcdef"
    configured_a = client.post(
        f"/admin/establishments/{tenant_a.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "access_token": token_a,
            "public_key": "APP_USR-public-A-123456",
            "webhook_secret": "tenant-a-webhook-secret",
        },
    )
    configured_b = client.post(
        f"/admin/establishments/{tenant_b.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "access_token": token_b,
            "public_key": "APP_USR-public-B-abcdef",
            "webhook_secret": "tenant-b-webhook-secret",
        },
    )
    assert configured_a.status_code == 200
    assert configured_b.status_code == 200
    _validate_integration(client, make_tenant_headers, tenant_a.id)
    _validate_integration(client, make_tenant_headers, tenant_b.id)

    listed_b = client.get(
        f"/admin/establishments/{tenant_b.id}/payment-integrations",
        headers=make_tenant_headers(is_admin=True),
    )
    assert listed_b.status_code == 200
    assert token_a not in str(listed_b.json())
    assert token_b not in str(listed_b.json())

    payload_a = {
        "telefone": "11999991001",
        "nome_cliente": "Cliente Checkout A",
        "cliente_email": "cliente-a@example.com",
        "barbeiro_id": profissional_a.id,
        "servico_id": servico_a.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    payload_b = {
        "telefone": "11999991002",
        "nome_cliente": "Cliente Checkout B",
        "cliente_email": "cliente-b@example.com",
        "barbeiro_id": profissional_b.id,
        "servico_id": servico_b.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    created_a = client.post("/bookings", json=payload_a, headers=_tenant_headers(make_tenant_headers, tenant_a.id))
    created_b = client.post("/bookings", json=payload_b, headers=_tenant_headers(make_tenant_headers, tenant_b.id))

    assert created_a.status_code == 200
    assert created_b.status_code == 200
    assert provider.checkout_access_tokens == [token_a, token_b]
    payment_a = db_session.query(Pagamento).filter(Pagamento.agendamento_id == created_a.json()["booking_id"]).first()
    payment_b = db_session.query(Pagamento).filter(Pagamento.agendamento_id == created_b.json()["booking_id"]).first()
    assert payment_a is not None
    assert payment_b is not None
    assert payment_a.estabelecimento_id == tenant_a.id
    assert payment_b.estabelecimento_id == tenant_b.id
    integration_b = db_session.query(PaymentIntegration).filter(PaymentIntegration.establishment_id == tenant_b.id).first()
    assert integration_b is not None
    assert token_a not in integration_b.credentials_encrypted
    assert decrypt_json_payload(integration_b.credentials_encrypted)["access_token"] == token_b


def test_create_booking_without_advance_payment(client, db_session, make_tenant_headers):
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant No Payment",
        require_advance_payment=False,
    )

    payload = {
        "telefone": "11999990001",
        "nome_cliente": "Cliente Sem Pagamento",
        "cliente_email": "cliente1@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "status": "confirmado",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert response.status_code == 200
    body = response.json()
    assert body["payment_required"] is False
    assert body["payment_status"] == "not_required"



def test_create_booking_with_advance_payment_pending_checkout(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Advance",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload = {
        "telefone": "11999990002",
        "nome_cliente": "Cliente Adiantado",
        "cliente_email": "cliente2@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert response.status_code == 200
    body = response.json()
    assert body["payment_required"] is True
    assert body["checkout"]["payment_status"] == "pending"

    booking = db_session.query(Agendamento).filter(Agendamento.id == body["booking_id"]).first()
    assert booking is not None
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"

    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking.id).first()
    assert payment is not None
    assert payment.status == "pending"
    assert payment.checkout_url is not None


def test_block_checkout_when_admin_account_is_not_configured(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Sem Conta Admin",
        require_advance_payment=True,
    )

    payload = {
        "telefone": "11999990022",
        "nome_cliente": "Cliente Sem Conta",
        "cliente_email": "cliente22@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert response.status_code == 400
    assert "Este estabelecimento ainda nao possui pagamento online configurado" in response.json()["detail"]
    blocked = db_session.query(Agendamento).filter(Agendamento.barbearia_id == tenant.id).one()
    assert blocked.status == "failed"
    assert blocked.payment_status == "cancelled"
    assert blocked.payment_hold_expires_at is None


def test_block_checkout_without_webhook_secret_releases_slot(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "")
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Sem Assinatura Webhook",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)
    payload = {
        "telefone": "11999990023",
        "nome_cliente": "Cliente Sem Webhook",
        "cliente_email": "cliente23@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(
            hour=17, minute=0, second=0, microsecond=0
        ).isoformat(),
        "status": "pendente",
    }

    response = client.post(
        "/bookings",
        json=payload,
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )

    assert response.status_code == 400
    assert "assinatura de webhook" in response.json()["detail"]
    booking = db_session.query(Agendamento).filter(Agendamento.barbearia_id == tenant.id).one()
    assert booking.status == "failed"
    assert booking.payment_hold_expires_at is None



def test_confirm_payment_via_webhook(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990003",
        "nome_cliente": "Cliente Webhook",
        "cliente_email": "cliente3@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider_calls: list[tuple[str, str]] = []

    def fake_get_payment(*, access_token, payment_id):
        provider_calls.append((access_token, payment_id))
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": payment.external_reference,
            "transaction_amount": payment.amount,
            "currency_id": "BRL",
            "collector_id": "mp-user-1",
            "metadata": {
                "payment_id": payment.id,
                "booking_id": payment.agendamento_id,
                "establishment_id": payment.estabelecimento_id,
            },
            "payment_method_id": "pix",
        }

    provider.get_payment = fake_get_payment

    webhook_response = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-1", "data": {"id": "mp-100"}, "type": "payment"},
        headers=_webhook_headers("mp-100", request_id="req-mp-100"),
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "ok"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "approved"
    assert booking is not None
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"
    assert provider_calls == [("token-active", "mp-100")]


def test_public_status_syncs_payment_without_webhook(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Status Sync",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990103",
        "nome_cliente": "Cliente Sync",
        "cliente_email": "sync@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == creation.json()["booking_id"]).first()
    assert payment is not None
    provider.search_payment_payloads[payment.external_reference] = {
        "id": "mp-search-100",
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": payment.amount,
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
        "metadata": {
            "payment_id": payment.id,
            "booking_id": payment.agendamento_id,
            "establishment_id": payment.estabelecimento_id,
        },
        "payment_method_id": "pix",
    }

    response = client.get(f"/public/pagamentos/status?external_reference={payment.external_reference}")
    assert response.status_code == 200
    assert response.json()["pagamento_status"] == "approved"
    assert response.json()["agendamento_status"] == "confirmado"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == payment.agendamento_id).first()
    assert payment.status == "approved"
    assert payment.provider_payment_id == "mp-search-100"
    assert booking is not None
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"
    assert provider.search_payment_access_tokens == ["token-active"]


def test_checkout_expiration_is_capped_at_five_minutes(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Expiracao Pix",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990104",
        "nome_cliente": "Cliente Expiracao",
        "cliente_email": "expira@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    before = datetime.utcnow()
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == creation.json()["booking_id"]).first()
    assert payment is not None
    assert payment.expires_at is not None
    assert payment.expires_at - before <= timedelta(minutes=5, seconds=5)


def test_mercadopago_checkout_treats_naive_expiration_as_utc(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 201
        text = ""

        @staticmethod
        def json():
            return {
                "id": "preference-utc",
                "init_point": "https://www.mercadopago.com.br/checkout/test",
            }

    def fake_post(url, *, headers, json, timeout, allow_redirects):
        captured["url"] = url
        captured["payload"] = json
        captured["allow_redirects"] = allow_redirects
        return FakeResponse()

    monkeypatch.setattr("app.services.payments.providers.mercadopago.requests.post", fake_post)

    expires_at = datetime(2030, 7, 13, 23, 25, 31)
    MercadoPagoProvider().create_checkout(
        access_token="test-token",
        idempotency_key="test-checkout-expiration",
        external_reference="booking:14:test",
        title="Agendamento #14",
        description="Teste de expiracao",
        amount=1.0,
        payer_email="cliente@example.com",
        payer_name="Cliente",
        payer_phone=None,
        metadata={"booking_id": 14},
        notification_url="http://127.0.0.1:8000/webhooks/mercadopago",
        return_urls=None,
        expires_at=expires_at,
    )

    payload = captured["payload"]
    assert payload["date_of_expiration"] == "2030-07-13T23:25:31+00:00"
    assert payload["expiration_date_to"] == "2030-07-13T23:25:31+00:00"
    assert datetime.fromisoformat(payload["date_of_expiration"]).tzinfo == timezone.utc
    assert captured["allow_redirects"] is False


def test_webhook_without_mapped_payment_does_not_call_provider(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    response = client.post(
        "/webhooks/mercadopago?external_reference=fake-reference",
        json={"id": "evt-fake", "data": {"id": "mp-fake"}, "type": "payment"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "pagamento_nao_mapeado"
    assert provider.webhook_calls == 0


def test_webhook_validates_establishment_webhook_secret(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Secret",
        require_advance_payment=True,
    )
    configured = client.post(
        f"/admin/establishments/{tenant.id}/payment-integrations/mercado-pago",
        headers=make_tenant_headers(is_admin=True),
        json={
            "environment": "production",
            "access_token": "signed-webhook-token",
            "webhook_secret": "secret-webhook-hmac",
            "status": "active",
        },
    )
    assert configured.status_code == 200
    _validate_integration(client, make_tenant_headers, tenant.id)

    payload_booking = {
        "telefone": "11999990033",
        "nome_cliente": "Cliente Assinado",
        "cliente_email": "cliente33@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider.get_payment = lambda *, access_token, payment_id: {
        "id": payment_id,
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": payment.amount,
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
        "metadata": {
            "payment_id": payment.id,
            "booking_id": payment.agendamento_id,
            "establishment_id": payment.estabelecimento_id,
        },
        "payment_method_id": "pix",
    }

    bad = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-signed-bad", "data": {"id": "mp-signed-bad"}, "type": "payment"},
        headers={"x-request-id": "req-bad", "x-signature": "ts=1700000000,v1=assinatura-invalida"},
    )
    assert bad.status_code == 401
    assert provider.webhook_calls == 0

    valid_payment_id = "mp-signed-good"
    good = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-signed-good", "data": {"id": valid_payment_id}, "type": "payment"},
        headers={
            "x-request-id": "req-good",
            "x-signature": _mercadopago_signature(
                secret="secret-webhook-hmac",
                data_id=valid_payment_id,
                request_id="req-good",
            ),
        },
    )
    assert good.status_code == 200
    assert good.json()["status"] == "ok"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "approved"
    assert booking is not None
    assert booking.status == "confirmado"


def test_webhook_rejects_approved_payment_with_wrong_amount(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Amount",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990034",
        "nome_cliente": "Cliente Valor Divergente",
        "cliente_email": "cliente34@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=13, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider.get_payment = lambda *, access_token, payment_id: {
        "id": payment_id,
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": payment.amount + 1,
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
        "metadata": {
            "payment_id": payment.id,
            "booking_id": payment.agendamento_id,
            "establishment_id": payment.estabelecimento_id,
        },
        "payment_method_id": "pix",
    }

    response = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-wrong-amount", "data": {"id": "mp-wrong-amount"}, "type": "payment"},
        headers=_webhook_headers("mp-wrong-amount", request_id="req-wrong-amount"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["reason"] == "valor_pagamento_divergente"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "pending"
    assert booking is not None
    assert booking.status == "pending_payment"



def test_block_frontend_confirmation_without_webhook(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Block Confirm",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990004",
        "nome_cliente": "Cliente Bloqueio",
        "cliente_email": "cliente4@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking = db_session.query(Agendamento).filter(Agendamento.id == creation.json()["booking_id"]).first()
    assert booking is not None

    response = client.post(f"/agendamentos/{booking.confirmation_token}/confirmar")
    assert response.status_code == 400
    assert "Pagamento nao aprovado" in response.json()["detail"]



def test_expire_pending_payment_booking_and_release_slot(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Expire",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    booking = Agendamento(
        cliente_id=1,
        profissional_id=profissional.id,
        servico_id=servico.id,
        estabelecimento_id=tenant.id,
        cliente_nome="Cliente Expira",
        cliente_telefone="11999990005",
        data_hora_inicio=datetime.utcnow() + timedelta(days=1),
        data_hora_fim=datetime.utcnow() + timedelta(days=1, minutes=40),
        status="pending_payment",
        pagamento_adiantado_exigido=True,
        payment_required_snapshot=True,
        payment_status="pending",
        payment_type_snapshot="full",
        payment_amount_snapshot=100.0,
        payment_hold_expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    payment = Pagamento(
        agendamento_id=booking.id,
        estabelecimento_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        idempotency_key="idempotency-expire-1",
        external_reference=f"booking:{booking.id}:expire",
        amount=100.0,
        status="pending",
    )
    db_session.add(payment)
    db_session.commit()

    expired = payment_service.expire_pending_bookings_and_payments(db_session, limit=10)
    assert expired == 1

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert booking.status == "expired"
    assert booking.payment_status == "expired"
    assert payment.status == "expired"



def test_block_slot_conflict_while_pending_payment_hold_active(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Conflict",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    inicio = (datetime.utcnow() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    payload_1 = {
        "telefone": "11999990006",
        "nome_cliente": "Cliente A",
        "cliente_email": "cliente6@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "pendente",
    }
    payload_2 = {
        "telefone": "11999990007",
        "nome_cliente": "Cliente B",
        "cliente_email": "cliente7@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "pendente",
    }

    first = client.post("/bookings", json=payload_1, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert first.status_code == 200

    second = client.post("/bookings", json=payload_2, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert second.status_code == 400
    assert "Horário indisponível" in second.json()["detail"]



def test_tenant_isolation_for_payment_reads(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Isolado A",
        require_advance_payment=True,
    )
    tenant_b, _, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Isolado B",
        require_advance_payment=False,
    )

    _create_active_payment_account(db_session, tenant_id=tenant_a.id)

    payload = {
        "telefone": "11999990008",
        "nome_cliente": "Cliente Tenant A",
        "cliente_email": "cliente8@example.com",
        "barbeiro_id": profissional_a.id,
        "servico_id": servico_a.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    created = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant_a.id))
    assert created.status_code == 200
    payment_id = created.json()["checkout"]["payment_id"]

    forbidden = client.get(f"/payments/{payment_id}", headers=_tenant_headers(make_tenant_headers, tenant_b.id))
    assert forbidden.status_code == 404



def test_encrypt_and_persist_payment_credentials(db_session):
    encrypted = encrypt_sensitive_value("secret-token")
    assert encrypted is not None
    assert "secret-token" not in encrypted

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Crypto", require_advance_payment=False)
    account = PaymentAccount(
        establishment_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        access_token_encrypted=encrypted,
        status="active",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    assert decrypt_sensitive_value(account.access_token_encrypted) == "secret-token"



def test_webhook_is_idempotent(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Idempotencia",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990009",
        "nome_cliente": "Cliente Idempotente",
        "cliente_email": "cliente9@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider.get_payment = lambda *, access_token, payment_id: {
        "id": payment_id,
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": payment.amount,
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
        "metadata": {
            "payment_id": payment.id,
            "booking_id": payment.agendamento_id,
            "establishment_id": payment.estabelecimento_id,
        },
        "payment_method_id": "pix",
    }

    first = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-idempotent", "data": {"id": "mp-idempotent"}, "type": "payment"},
        headers=_webhook_headers("mp-idempotent", request_id="req-idempotent"),
    )
    second = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"id": "evt-idempotent", "data": {"id": "mp-idempotent"}, "type": "payment"},
        headers=_webhook_headers("mp-idempotent", request_id="req-idempotent"),
    )

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert second.json()["reason"] == "evento_duplicado"



def test_checkout_pending_endpoint_creates_pending_payment(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout Endpoint",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990010",
        "nome_cliente": "Cliente Checkout",
        "cliente_email": "cliente10@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200
    booking_id = creation.json()["booking_id"]

    checkout = client.post(
        f"/bookings/{booking_id}/checkout",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert body["payment_status"] == "pending"
    assert body["checkout_url"].startswith("https://www.mercadopago.com.br/checkout/")


def _create_pending_payment_for_security_test(
    client,
    db_session,
    make_tenant_headers,
    monkeypatch,
    provider,
    *,
    tenant_name: str,
):
    _patch_providers(monkeypatch, provider)
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name=tenant_name,
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)
    creation = client.post(
        "/bookings",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
        json={
            "telefone": "11999887766",
            "nome_cliente": "Cliente Seguranca",
            "cliente_email": "security@example.com",
            "barbeiro_id": profissional.id,
            "servico_id": servico.id,
            "data_hora_inicio": (datetime.utcnow() + timedelta(days=2)).replace(
                hour=10, minute=0, second=0, microsecond=0
            ).isoformat(),
            "status": "pendente",
        },
    )
    assert creation.status_code == 200
    payment = db_session.query(Pagamento).filter(
        Pagamento.agendamento_id == creation.json()["booking_id"]
    ).first()
    assert payment is not None
    return tenant, profissional, servico, payment


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("reference", "external_reference_divergente"),
        ("currency", "moeda_pagamento_divergente"),
        ("currency_missing", "moeda_pagamento_ausente"),
        ("payment_id_missing", "provider_payment_id_ausente"),
        ("collector", "conta_recebedora_divergente"),
        ("collector_missing", "conta_recebedora_ausente"),
        ("tenant", "establishment_id_divergente"),
    ],
)
def test_provider_payment_binding_rejects_cross_context_payload(case, expected_reason):
    payment = Pagamento(
        id=17,
        agendamento_id=44,
        estabelecimento_id=3,
        external_reference="pay_secure_reference",
        amount=Decimal("12.50"),
        currency="BRL",
        status="pending",
    )
    payload = {
        "id": "mp-17",
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": "12.50",
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
        "metadata": {
            "payment_id": payment.id,
            "booking_id": payment.agendamento_id,
            "establishment_id": payment.estabelecimento_id,
        },
    }
    if case == "reference":
        payload["external_reference"] = "pay_other_reference"
    elif case == "currency":
        payload["currency_id"] = "USD"
    elif case == "currency_missing":
        payload.pop("currency_id")
    elif case == "payment_id_missing":
        payload.pop("id")
    elif case == "collector":
        payload["collector_id"] = "another-account"
    elif case == "collector_missing":
        payload.pop("collector_id")
    elif case == "tenant":
        payload["metadata"]["establishment_id"] = 999

    valid, reason = webhook_service._validate_provider_payload_for_payment(
        payment,
        payload,
        expected_account_id="mp-user-1",
    )
    assert valid is False
    assert reason == expected_reason


def test_mapped_mercadopago_webhook_requires_signature(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    _, _, _, payment = _create_pending_payment_for_security_test(
        client,
        db_session,
        make_tenant_headers,
        monkeypatch,
        provider,
        tenant_name="Tenant Unsigned Webhook",
    )
    response = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"type": "payment", "data": {"id": "mp-unsigned"}},
    )
    assert response.status_code == 401
    assert provider.webhook_calls == 0


def test_mercadopago_webhook_rejects_stale_signature(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    _, _, _, payment = _create_pending_payment_for_security_test(
        client,
        db_session,
        make_tenant_headers,
        monkeypatch,
        provider,
        tenant_name="Tenant Stale Webhook",
    )
    payment_id = "mp-stale"
    request_id = "req-stale"
    response = client.post(
        f"/webhooks/mercadopago?external_reference={payment.external_reference}",
        json={"type": "payment", "data": {"id": payment_id}},
        headers={
            "x-request-id": request_id,
            "x-signature": _mercadopago_signature(
                secret="test-mercadopago-webhook-secret",
                data_id=payment_id,
                request_id=request_id,
                ts=str(int(time.time()) - 1000),
            ),
        },
    )
    assert response.status_code == 401
    assert provider.webhook_calls == 0


def test_mercadopago_webhook_rejects_query_body_payment_mismatch(client):
    response = client.post(
        "/webhooks/mercadopago?data.id=mp-query",
        json={"type": "payment", "data": {"id": "mp-body"}},
    )
    assert response.status_code == 400


def test_failed_provider_lookup_can_retry_same_signed_event(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    _, _, _, payment = _create_pending_payment_for_security_test(
        client,
        db_session,
        make_tenant_headers,
        monkeypatch,
        provider,
        tenant_name="Tenant Retry Webhook",
    )
    attempts = 0

    def flaky_get_payment(*, access_token, payment_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("provider timeout")
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": payment.external_reference,
            "transaction_amount": payment.amount,
            "currency_id": "BRL",
            "collector_id": "mp-user-1",
            "metadata": {
                "payment_id": payment.id,
                "booking_id": payment.agendamento_id,
                "establishment_id": payment.estabelecimento_id,
            },
        }

    provider.get_payment = flaky_get_payment
    payment_id = "mp-retry-event"
    headers = _webhook_headers(payment_id, request_id="req-retry-event")
    url = f"/webhooks/mercadopago?external_reference={payment.external_reference}"
    payload = {"type": "payment", "data": {"id": payment_id}}

    assert client.post(url, json=payload, headers=headers).status_code == 503
    second = client.post(url, json=payload, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "ok"
    assert attempts == 2


def test_approved_payment_does_not_regress_to_pending(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    _, _, _, payment = _create_pending_payment_for_security_test(
        client,
        db_session,
        make_tenant_headers,
        monkeypatch,
        provider,
        tenant_name="Tenant Payment State",
    )
    approved = {
        "id": "mp-state",
        "status": "approved",
        "external_reference": payment.external_reference,
        "transaction_amount": payment.amount,
        "currency_id": "BRL",
        "collector_id": "mp-user-1",
    }
    payment_service.apply_payment_update_from_provider(
        db_session,
        payment=payment,
        provider_payload=approved,
    )
    payment_service.apply_payment_update_from_provider(
        db_session,
        payment=payment,
        provider_payload={**approved, "status": "pending"},
    )
    db_session.refresh(payment)
    assert payment.status == "approved"
    assert payment.agendamento.status == "confirmado"


def test_repeated_terminal_status_does_not_duplicate_notifications(
    client, db_session, make_tenant_headers, monkeypatch
):
    provider = DummyProvider()
    tenant, _, _, payment = _create_pending_payment_for_security_test(
        client,
        db_session,
        make_tenant_headers,
        monkeypatch,
        provider,
        tenant_name="Tenant Evento Terminal Idempotente",
    )
    provider_payload = {"id": "mp-terminal-1", "status": "rejected"}

    payment_service.apply_payment_update_from_provider(
        db_session,
        payment=payment,
        provider_payload=provider_payload,
    )
    payment_service.apply_payment_update_from_provider(
        db_session,
        payment=payment,
        provider_payload=provider_payload,
    )

    count = (
        db_session.query(Notificacao)
        .filter(
            Notificacao.estabelecimento_id == tenant.id,
            Notificacao.agendamento_id == payment.agendamento_id,
            Notificacao.tipo == "pagamento_falhou",
        )
        .count()
    )
    assert count == 1


def test_public_checkout_retry_reuses_same_idempotency_key(
    client, db_session, monkeypatch
):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout Retry",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)
    attempted_keys = []
    original_create = provider.create_checkout

    def flaky_checkout(**kwargs):
        attempted_keys.append(kwargs["idempotency_key"])
        if len(attempted_keys) == 1:
            raise TimeoutError("unknown checkout result")
        return original_create(**kwargs)

    provider.create_checkout = flaky_checkout
    payload = {
        "estabelecimento_id": tenant.id,
        "cliente_nome": "Cliente Retry",
        "cliente_telefone": "11999112233",
        "cliente_email": "retry@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data": (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
        "hora_inicio": "10:00",
    }
    url = "/public/agendamentos/pagamento/iniciar"
    assert client.post(url, json=payload).status_code == 400
    second = client.post(url, json=payload)
    assert second.status_code == 200
    assert len(attempted_keys) == 2
    assert attempted_keys[0] == attempted_keys[1]


def test_repeated_public_checkout_returns_existing_preference(
    client, db_session, monkeypatch
):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout Duplicate",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)
    payload = {
        "estabelecimento_id": tenant.id,
        "cliente_nome": "Cliente Duplicate",
        "cliente_telefone": "11999445566",
        "cliente_email": "duplicate@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data": (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
        "hora_inicio": "11:00",
    }
    url = "/public/agendamentos/pagamento/iniciar"
    first = client.post(url, json=payload)
    second = client.post(url, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["external_reference"] == second.json()["external_reference"]
    assert len(provider.checkout_idempotency_keys) == 1


def test_mercadopago_provider_sends_idempotency_header(monkeypatch):
    captured = {}

    class Response:
        status_code = 201

        @staticmethod
        def json():
            return {"id": "pref-secure", "init_point": "https://mercadopago.com/checkout"}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.services.payments.providers.mercadopago.requests.post", fake_post)
    provider = MercadoPagoProvider()
    provider.create_checkout(
        access_token="access-token",
        idempotency_key="logical-operation-key",
        external_reference="pay_reference",
        title="Servico",
        description="Agendamento",
        amount=10.0,
        payer_email=None,
        payer_name=None,
        payer_phone=None,
        metadata={"booking_id": 1},
        notification_url="https://api.example.com/webhooks/mercadopago",
        return_urls=None,
        expires_at=None,
    )
    assert captured["headers"]["X-Idempotency-Key"] == "logical-operation-key"


def test_mercadopago_oauth_url_uses_only_documented_parameters(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "marketplace-client")
    monkeypatch.setenv("MERCADOPAGO_REDIRECT_URI", "https://app.example.com/integrations/mercadopago/callback")
    provider = MercadoPagoProvider()

    query = parse_qs(urlsplit(provider.build_connect_url(state="opaque-state")).query)

    assert query == {
        "client_id": ["marketplace-client"],
        "response_type": ["code"],
        "state": ["opaque-state"],
        "redirect_uri": ["https://app.example.com/integrations/mercadopago/callback"],
    }
    assert "platform_id" not in query


def test_mercadopago_checkout_adds_valid_marketplace_fee(monkeypatch):
    captured = {}

    class Response:
        status_code = 201

        @staticmethod
        def json():
            return {"id": "pref-marketplace", "init_point": "https://mercadopago.com/checkout"}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setenv("MERCADOPAGO_MARKETPLACE_FEE", "1.25")
    monkeypatch.setattr("app.services.payments.providers.mercadopago.requests.post", fake_post)
    provider = MercadoPagoProvider()
    provider.create_checkout(
        access_token="access-token",
        idempotency_key="marketplace-operation",
        external_reference="marketplace-reference",
        title="Servico",
        description="Agendamento",
        amount=10.0,
        payer_email=None,
        payer_name=None,
        payer_phone=None,
        metadata={"booking_id": 1},
        notification_url="https://api.example.com/webhooks/mercadopago",
        return_urls=None,
        expires_at=None,
    )

    assert captured["json"]["marketplace_fee"] == 1.25


@pytest.mark.parametrize("fee", ["invalid", "0", "10", "11", "-1"])
def test_mercadopago_checkout_rejects_unsafe_marketplace_fee(monkeypatch, fee):
    monkeypatch.setenv("MERCADOPAGO_MARKETPLACE_FEE", fee)
    provider = MercadoPagoProvider()

    with pytest.raises(ValueError, match="marketplace"):
        provider.create_checkout(
            access_token="access-token",
            idempotency_key="marketplace-operation",
            external_reference="marketplace-reference",
            title="Servico",
            description="Agendamento",
            amount=10.0,
            payer_email=None,
            payer_name=None,
            payer_phone=None,
            metadata={"booking_id": 1},
            notification_url="https://api.example.com/webhooks/mercadopago",
            return_urls=None,
            expires_at=None,
        )

