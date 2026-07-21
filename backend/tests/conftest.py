from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("PAYMENT_CREDENTIALS_PEPPER", "test-payment-fingerprint-pepper-at-least-32-bytes")
os.environ.setdefault("MERCADOPAGO_WEBHOOK_SECRET", "test-mercadopago-webhook-secret")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-whatsapp-verify-token")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-whatsapp-app-secret")
os.environ.setdefault("WHATSAPP_ALLOW_UNSIGNED_WEBHOOKS", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-with-at-least-32-bytes")
os.environ.setdefault("ADMIN_USUARIO", "test-admin")
os.environ.setdefault("ADMIN_SENHA", "test-admin-password")
os.environ.setdefault("ADMIN_SENHA_HASH", "")

from app.database import Base, get_db
from app.models import Estabelecimento, Profissional, Servico
from app.models.token_blacklist import TokenBlacklist  # registers in SQLite metadata
from app.routes import agenda, agendamentos, chatbot, barbeiros, clientes, servicos, whatsapp, auth, webhooks, public, internal, webhook, estabelecimentos, profissionais, estabelecimento_funcionamento, configuracoes, dashboard, notificacoes, integrations, payments
from app.models.notificacao import Notificacao  # garante criação da tabela no SQLite
from app.security import create_access_token
from app.limiter import limiter


@pytest.fixture(autouse=True)
def isolate_rate_limiter():
    limiter._storage = MemoryStorage()
    limiter._limiter = FixedWindowRateLimiter(limiter._storage)


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(session_factory):
    import app.database as _db_module
    original_session_local = _db_module.SessionLocal
    _db_module.SessionLocal = session_factory

    test_app = FastAPI()
    test_app.include_router(agendamentos.router)
    test_app.include_router(agenda.router)
    test_app.include_router(chatbot.router)
    test_app.include_router(barbeiros.router)
    test_app.include_router(clientes.router)
    test_app.include_router(servicos.router)
    test_app.include_router(whatsapp.router, prefix="/whatsapp")
    test_app.include_router(webhooks.router)
    test_app.include_router(webhook.router)
    test_app.include_router(public.router)
    test_app.include_router(internal.router)
    test_app.include_router(auth.router)
    test_app.include_router(estabelecimentos.router)
    test_app.include_router(profissionais.router)
    test_app.include_router(estabelecimento_funcionamento.router)
    test_app.include_router(configuracoes.router)
    test_app.include_router(dashboard.router)
    test_app.include_router(notificacoes.router)
    test_app.include_router(integrations.router)
    test_app.include_router(payments.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    yield test_app

    _db_module.SessionLocal = original_session_local


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dados_base(db_session):
    barbearia = Estabelecimento(nome="Barbearia Teste", endereco="Rua Teste, 123")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Profissional(nome="Joao", barbearia_id=barbearia.id)
    servico = Servico(
        nome="corte social",
        duracao_minutos=40,
        preco=40.0,
        barbearia_id=barbearia.id,
    )
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    return {
        "barbearia": barbearia,
        "barbeiro": barbeiro,
        "servico": servico,
        "agora": datetime.now(),
        "amanha": datetime.now() + timedelta(days=1),
    }


@pytest.fixture
def make_tenant_headers(db_session):
    def _make(
        tenant_id: int | None = None,
        *,
        include_tenant_header: bool = True,
        is_admin: bool = False,
    ) -> dict[str, str]:
        if is_admin:
            from app.models.admin_mfa import AdminMfaSetting

            setting = db_session.get(AdminMfaSetting, "admin")
            if not setting:
                db_session.add(AdminMfaSetting(admin_username="admin", enabled=True, session_version=0))
                db_session.commit()
            token = create_access_token(sub="admin", tenant_id=None, is_admin=True)
            return {"Authorization": f"Bearer {token}"}

        if tenant_id is None:
            raise ValueError("tenant_id obrigatorio para gerar header de tenant.")

        token = create_access_token(
            sub=f"tenant-{tenant_id}",
            tenant_id=tenant_id,
            is_admin=False,
        )
        headers = {"Authorization": f"Bearer {token}"}
        if include_tenant_header:
            headers["X-Barbearia-Id"] = str(tenant_id)
        return headers

    return _make


@pytest.fixture
def tenant_headers(dados_base, make_tenant_headers):
    return make_tenant_headers(dados_base["barbearia"].id)
