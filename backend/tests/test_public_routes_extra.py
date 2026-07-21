"""Testes adicionais para rotas públicas — cobre paths de erro e endpoints não testados."""
from datetime import date, datetime, timedelta

import pytest

from app.models.estabelecimento import Estabelecimento
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.servico import Servico


# ── helpers ───────────────────────────────────────────────────────────────────

def _barbearia(db_session, slug="pub-extra", nome="Pub Extra"):
    b = Estabelecimento(nome=nome, slug=slug, endereco="Rua Extra")
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def _barbeiro(db_session, estabelecimento_id, nome="Barber", ativo=True):
    b = Barbeiro(nome=nome, estabelecimento_id=estabelecimento_id, ativo=ativo)
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


def _servico(db_session, estabelecimento_id, nome="Corte", duracao=30, preco=40.0):
    s = Servico(nome=nome, duracao_minutos=duracao, preco=preco, estabelecimento_id=estabelecimento_id)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def _data_futura(days=3) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ── GET /public/estabelecimento/{slug} — error paths ─────────────────────────

def test_lookup_barbearia_slug_invalido_retorna_404(client):
    resp = client.get("/public/estabelecimento/slug-inexistente-xyz")
    assert resp.status_code == 404


def test_lookup_barbearia_slug_sem_params_retorna_200(client, db_session):
    b = _barbearia(db_session, "sem-params")
    resp = client.get(f"/public/estabelecimento/{b.slug}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "sem-params"


# ── GET /public/estabelecimento-id/{estabelecimento_id} ──────────────────────

def test_lookup_barbearia_por_id_retorna_200(client, db_session):
    b = _barbearia(db_session, "por-id-1", "Por Id")
    resp = client.get(f"/public/estabelecimento-id/{b.id}")
    assert resp.status_code == 200
    assert resp.json()["estabelecimento_id"] == b.id


def test_lookup_barbearia_por_id_invalido_retorna_404(client):
    resp = client.get("/public/estabelecimento-id/999999")
    assert resp.status_code == 404


def test_lookup_barbearia_por_id_com_data_e_params(client, db_session):
    b = _barbearia(db_session, "por-id-2", "Com Params")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id)
    resp = client.get(
        f"/public/estabelecimento-id/{b.id}",
        params={"barbeiro_id": barb.id, "servico_id": serv.id, "data": _data_futura()},
    )
    assert resp.status_code == 200


# ── GET /public/{estabelecimento_id}/cliente ───────────────────────────────────────

def test_lookup_cliente_nao_permite_enumerar_cadastro_existente(client, db_session):
    b = _barbearia(db_session, "cliente-lookup")
    c = Cliente(telefone="11999990001", nome="Joana", estabelecimento_id=b.id)
    db_session.add(c)
    db_session.commit()

    resp = client.get(f"/public/{b.id}/cliente", params={"telefone": "11999990001"})
    assert resp.status_code == 404


def test_lookup_cliente_retorna_404_quando_nao_existe(client, db_session):
    b = _barbearia(db_session, "cliente-vazio")
    resp = client.get(f"/public/{b.id}/cliente", params={"telefone": "99999999999"})
    assert resp.status_code == 404


# ── POST /public/agendamentos — error paths ───────────────────────────────────

def test_agendamento_barbearia_invalida_retorna_400_ou_422(monkeypatch, client, db_session):
    import app.services.public_booking_service as svc
    monkeypatch.setattr(svc, "enviar_mensagem_whatsapp", lambda *a, **kw: True)

    resp = client.post(
        "/public/agendamentos",
        json={
            "estabelecimento_id": 999999,
            "cliente_nome": "Teste",
            "cliente_telefone": "11999990002",
            "barbeiro_id": 1,
            "servico_id": 1,
            "data": _data_futura(),
            "hora_inicio": "10:00",
        },
    )
    assert resp.status_code in (400, 404, 422)


def test_agendamento_sem_campos_obrigatorios_retorna_422(client):
    resp = client.post("/public/agendamentos", json={"estabelecimento_id": 1})
    assert resp.status_code == 422


def test_agendamento_horario_bloqueado_por_conflito_retorna_400(monkeypatch, client, db_session):
    import app.services.public_booking_service as svc
    monkeypatch.setattr(svc, "enviar_mensagem_whatsapp", lambda *a, **kw: True)

    b = _barbearia(db_session, "conflito-test")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id, duracao=30)
    data = _data_futura(days=5)

    payload = {
        "estabelecimento_id": b.id,
        "cliente_nome": "Primeiro",
        "cliente_telefone": "11999990010",
        "barbeiro_id": barb.id,
        "servico_id": serv.id,
        "data": data,
        "hora_inicio": "10:00",
    }
    resp1 = client.post("/public/agendamentos", json=payload)
    assert resp1.status_code == 200

    payload["cliente_nome"] = "Segundo"
    payload["cliente_telefone"] = "11999990011"
    resp2 = client.post("/public/agendamentos", json=payload)
    assert resp2.status_code == 400


# ── GET /public/horarios-disponiveis — additional paths ───────────────────────

def test_horarios_com_barbeiro_retorna_200(client, db_session):
    b = _barbearia(db_session, "horarios-com-barb")
    barb = _barbeiro(db_session, b.id)
    serv = _servico(db_session, b.id)
    resp = client.get(
        "/public/horarios-disponiveis",
        params={"estabelecimento_id": b.id, "barbeiro_id": barb.id, "servico_id": serv.id, "data": _data_futura()},
    )
    assert resp.status_code == 200


def test_horarios_barbearia_invalida_retorna_400_ou_422(client):
    resp = client.get(
        "/public/horarios-disponiveis",
        params={"estabelecimento_id": 999999, "servico_id": 1, "data": "2030-01-01"},
    )
    assert resp.status_code in (400, 404, 422)
