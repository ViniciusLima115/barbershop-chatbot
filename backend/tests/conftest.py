from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, get_db
from app.models import Barbearia, Barbeiro, Servico
from app.routes import agenda, agendamentos, chatbot, barbeiros, clientes, servicos, whatsapp, barbearias, auth, webhooks
from app.security import create_access_token


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
    test_app = FastAPI()
    test_app.include_router(agendamentos.router)
    test_app.include_router(agenda.router)
    test_app.include_router(chatbot.router)
    test_app.include_router(barbeiros.router)
    test_app.include_router(clientes.router)
    test_app.include_router(barbearias.router)
    test_app.include_router(servicos.router)
    test_app.include_router(whatsapp.router, prefix="/whatsapp")
    test_app.include_router(webhooks.router)
    test_app.include_router(auth.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dados_base(db_session):
    barbearia = Barbearia(nome="Barbearia Teste", endereco="Rua Teste, 123")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(nome="Joao", barbearia_id=barbearia.id)
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
def make_tenant_headers():
    def _make(
        tenant_id: int | None = None,
        *,
        include_tenant_header: bool = True,
        is_admin: bool = False,
    ) -> dict[str, str]:
        if is_admin:
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
