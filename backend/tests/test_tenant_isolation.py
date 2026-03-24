"""
Testes de isolamento de tenant: garante que um tenant não acessa dados de outro.
"""
import pytest
from app.models.barbearia import Barbearia
from app.models.barbeiro import Barbeiro
from app.models.servico import Servico
from app.models.agendamento import Agendamento
from app.security import hash_senha
from datetime import datetime, timedelta


@pytest.fixture
def dois_tenants(db_session):
    t1 = Barbearia(nome="Tenant Um", login="tenant.um", senha=hash_senha("senha1"), endereco="Rua 1")
    t2 = Barbearia(nome="Tenant Dois", login="tenant.dois", senha=hash_senha("senha2"), endereco="Rua 2")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    b1 = Barbeiro(nome="Barbeiro T1", barbearia_id=t1.id)
    b2 = Barbeiro(nome="Barbeiro T2", barbearia_id=t2.id)
    s1 = Servico(nome="Corte T1", duracao_minutos=30, preco=40.0, barbearia_id=t1.id)
    db_session.add_all([b1, b2, s1])
    db_session.commit()
    db_session.refresh(b1)
    db_session.refresh(b2)
    db_session.refresh(s1)

    return {"t1": t1, "t2": t2, "b1": b1, "b2": b2, "s1": s1}


def test_tenant_nao_ve_agenda_do_outro(client, dois_tenants, make_tenant_headers):
    t1 = dois_tenants["t1"]
    t2 = dois_tenants["t2"]

    headers_t1 = make_tenant_headers(tenant_id=t1.id)
    headers_t2_errado = {
        "Authorization": headers_t1["Authorization"],  # token de t1
        "X-Barbearia-Id": str(t2.id),  # mas tentando acessar t2
    }
    resp = client.get("/agendamentos/", headers=headers_t2_errado)
    assert resp.status_code == 403


def test_tenant_nao_ve_clientes_do_outro(client, dois_tenants, make_tenant_headers):
    t1 = dois_tenants["t1"]
    t2 = dois_tenants["t2"]

    headers_t1_acessando_t2 = {
        "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
        "X-Barbearia-Id": str(t2.id),
    }
    resp = client.get("/clientes/", headers=headers_t1_acessando_t2)
    assert resp.status_code == 403


def test_tenant_nao_ve_servicos_do_outro(client, dois_tenants, make_tenant_headers):
    t1 = dois_tenants["t1"]
    t2 = dois_tenants["t2"]

    headers_t1_acessando_t2 = {
        "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
        "X-Barbearia-Id": str(t2.id),
    }
    resp = client.get("/servicos/", headers=headers_t1_acessando_t2)
    assert resp.status_code == 403


def test_tenant_nao_cria_agendamento_em_outro_tenant(client, dois_tenants, make_tenant_headers):
    t1 = dois_tenants["t1"]
    t2 = dois_tenants["t2"]

    headers_t1_acessando_t2 = {
        "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
        "X-Barbearia-Id": str(t2.id),
    }
    payload = {
        "cliente_nome": "Intruso",
        "cliente_telefone": "5511999990000",
        "barbeiro_id": dois_tenants["b2"].id,
        "servico_id": dois_tenants["s1"].id,
        "data_hora_inicio": (datetime.now() + timedelta(days=1)).isoformat(),
    }
    resp = client.post("/agendamentos/", json=payload, headers=headers_t1_acessando_t2)
    assert resp.status_code == 403


def test_endpoint_admin_bloqueia_tenant(client, make_tenant_headers, dois_tenants):
    t1 = dois_tenants["t1"]
    headers_tenant = make_tenant_headers(tenant_id=t1.id)
    # Tenants não devem acessar lista de barbearias (endpoint admin)
    resp = client.get("/barbearias/", headers=headers_tenant)
    assert resp.status_code == 403
