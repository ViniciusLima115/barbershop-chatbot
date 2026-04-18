from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_oauth_state import PaymentOAuthState
from app.models.profissional import Profissional
from app.models.servico import Servico
from app.services.payments import payment_account_service, payment_service, webhook_service
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value


class DummyProvider:
    def __init__(self):
        self.webhook_calls = 0

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
        external_reference: str,
        title: str,
        description: str,
        amount: float,
        payer_email: str | None,
        payer_name: str | None,
        payer_phone: str | None,
        metadata: dict,
        notification_url: str,
        expires_at: datetime | None,
    ):
        return {
            "preference_id": f"pref-{external_reference}",
            "checkout_url": f"https://dummy.example/checkout/{external_reference}",
            "raw": {
                "external_reference": external_reference,
                "amount": amount,
                "notification_url": notification_url,
            },
        }

    def get_payment(self, *, access_token: str, payment_id: str):
        self.webhook_calls += 1
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": "",
            "payment_method_id": "pix",
        }

    def refund_payment(self, *, access_token: str, payment_id: str):
        return {"id": payment_id, "status": "refunded"}



def _patch_providers(monkeypatch: pytest.MonkeyPatch, provider: DummyProvider):
    monkeypatch.setattr(payment_account_service, "get_payment_provider", lambda _provider: provider)
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
    assert body["access_token_masked"].startswith("access")
    assert "access-token-admin" not in str(body)

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert "access-token-admin" not in account.access_token_encrypted
    assert decrypt_sensitive_value(account.access_token_encrypted) == "access-token-admin"
    assert decrypt_sensitive_value(account.client_secret_encrypted) == "client-secret-admin"


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
    assert "Conta de pagamento ativa nao encontrada" in response.json()["detail"]



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

    provider.get_payment = lambda *, access_token, payment_id: {
        "id": payment_id,
        "status": "approved",
        "external_reference": payment.external_reference,
        "payment_method_id": "pix",
    }

    webhook_response = client.post(
        f"/webhooks/mercadopago?payment_id={payment.id}",
        json={"id": "evt-1", "data": {"id": "mp-100"}, "type": "payment"},
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "ok"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "approved"
    assert booking is not None
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"



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
        "payment_method_id": "pix",
    }

    first = client.post(
        f"/webhooks/mercadopago?payment_id={payment.id}",
        json={"id": "evt-idempotent", "data": {"id": "mp-idempotent"}, "type": "payment"},
    )
    second = client.post(
        f"/webhooks/mercadopago?payment_id={payment.id}",
        json={"id": "evt-idempotent", "data": {"id": "mp-idempotent"}, "type": "payment"},
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
    assert body["checkout_url"].startswith("https://dummy.example/checkout/")

