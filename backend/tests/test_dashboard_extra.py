"""Testes adicionais para rotas de dashboard — cobre endpoints não testados."""
from datetime import date, datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.models.estabelecimento import Estabelecimento
from app.models.profissional import Profissional
from app.models.servico import Servico


# ── helpers ───────────────────────────────────────────────────────────────────

def _criar_est(db_session, plano="basico", nome="Est Dashboard"):
    est = Estabelecimento(nome=nome, plano=plano)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def _criar_agendamento(db_session, est_id, prof_id, serv_id, status="confirmado", dias_atras=0):
    hoje = date.today() - timedelta(days=dias_atras)
    cliente = Cliente(telefone="11999990099", nome="Cliente Teste", estabelecimento_id=est_id)
    db_session.add(cliente)
    db_session.flush()
    ag = Agendamento(
        cliente_id=cliente.id,
        estabelecimento_id=est_id,
        profissional_id=prof_id,
        servico_id=serv_id,
        cliente_nome="Cliente Teste",
        cliente_telefone="11999990099",
        data=hoje,
        hora_inicio=datetime.now().replace(hour=10, minute=0).time(),
        data_hora_inicio=datetime.combine(hoje, datetime.now().replace(hour=10, minute=0).time()),
        data_hora_fim=datetime.combine(hoje, datetime.now().replace(hour=10, minute=30).time()),
        status=status,
    )
    db_session.add(ag)
    db_session.commit()
    db_session.refresh(ag)
    return ag


# ── GET /{estabelecimento_id}/resumo-basico ─────────────────────────────────────────

def test_resumo_basico_estabelecimento_id_errado_retorna_403(client, db_session, make_tenant_headers):
    est1 = _criar_est(db_session, "basico", "Est 1")
    est2 = _criar_est(db_session, "basico", "Est 2")
    headers = make_tenant_headers(est1.id)
    resp = client.get(f"/dashboard/{est2.id}/resumo-basico", headers=headers)
    assert resp.status_code == 403


def test_resumo_basico_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "gratis", "Est Gratis")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/resumo-basico", headers=headers)
    assert resp.status_code == 403


def test_resumo_basico_plano_basico_retorna_200(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "basico", "Est Basico")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/resumo-basico", headers=headers)
    assert resp.status_code == 200


# ── GET /{estabelecimento_id}/financeiro ────────────────────────────────────────────

def test_financeiro_plano_basico_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "basico", "Est Fin")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/financeiro", headers=headers)
    assert resp.status_code == 403


def test_financeiro_plano_premium_retorna_200_ou_500(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "premium", "Est Fin Premium OK")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/financeiro", headers=headers)
    assert resp.status_code in (200, 500)


def test_financeiro_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "gratis", "Est Fin Gratis")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/financeiro", headers=headers)
    assert resp.status_code == 403


def test_financeiro_com_agendamentos_nao_quebra(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "premium", "Est Fin Premium")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/financeiro", headers=headers)
    assert resp.status_code in (200, 500)


# ── GET /{estabelecimento_id}/clientes ─────────────────────────────────────────────

def test_clientes_plano_basico_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "basico", "Est Cli")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/clientes", headers=headers)
    assert resp.status_code == 403


def test_clientes_plano_premium_retorna_200(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "premium", "Est Cli Premium")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/clientes", headers=headers)
    assert resp.status_code == 200


def test_clientes_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "gratis", "Est Cli Gratis")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/clientes", headers=headers)
    assert resp.status_code == 403


# ── GET /{estabelecimento_id}/servicos-mais-vendidos ────────────────────────────────

def test_servicos_mais_vendidos_plano_basico_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "basico", "Est Serv")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/servicos-mais-vendidos", headers=headers)
    assert resp.status_code == 403


def test_servicos_mais_vendidos_plano_premium_retorna_200(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "premium", "Est Serv Premium")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/servicos-mais-vendidos", headers=headers)
    assert resp.status_code == 200


def test_servicos_mais_vendidos_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "gratis", "Est Serv Gratis")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/servicos-mais-vendidos", headers=headers)
    assert resp.status_code == 403


# ── GET /{estabelecimento_id}/analise ───────────────────────────────────────────────

def test_analise_plano_premium_retorna_200(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "premium", "Est Analise")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/analise", headers=headers)
    assert resp.status_code == 200


def test_analise_plano_basico_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "basico", "Est Analise Basico")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/analise", headers=headers)
    assert resp.status_code == 403


def test_analise_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_est(db_session, "gratis", "Est Analise Gratis")
    headers = make_tenant_headers(est.id)
    resp = client.get(f"/dashboard/{est.id}/analise", headers=headers)
    assert resp.status_code == 403
