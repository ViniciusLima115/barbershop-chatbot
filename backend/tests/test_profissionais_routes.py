import pytest

from app.models.estabelecimento import Estabelecimento
from app.models.profissional import Profissional


# ── helpers ───────────────────────────────────────────────────────────────────

def _criar_estabelecimento(db_session, plano="gratis"):
    est = Estabelecimento(nome="Barbearia Plano", endereco="Rua Plano", plano=plano)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def _headers(estabelecimento_id: int, make_tenant_headers):
    return make_tenant_headers(estabelecimento_id)


def _payload(nome="João"):
    return {"nome": nome, "ativo": True, "tempo_por_servico": None, "horarios_funcionamento": None}


# ── listar ────────────────────────────────────────────────────────────────────

def test_listar_profissionais_vazio(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session)
    resp = client.get("/profissionais/", headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 200
    assert resp.json() == []


def test_listar_profissionais_retorna_apenas_do_tenant(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "basico")
    outro = _criar_estabelecimento(db_session, "basico")

    p1 = Profissional(nome="Do Tenant", estabelecimento_id=est.id)
    p2 = Profissional(nome="Do Outro", estabelecimento_id=outro.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    resp = client.get("/profissionais/", headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 200
    nomes = [p["nome"] for p in resp.json()]
    assert "Do Tenant" in nomes
    assert "Do Outro" not in nomes


# ── criar ─────────────────────────────────────────────────────────────────────

def test_criar_profissional_plano_gratis(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "gratis")
    resp = client.post("/profissionais/", json=_payload("Carlos"), headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Carlos"


def test_criar_segundo_profissional_plano_gratis_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "gratis")
    p = Profissional(nome="Existente", estabelecimento_id=est.id)
    db_session.add(p)
    db_session.commit()

    resp = client.post("/profissionais/", json=_payload("Novo"), headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 403
    assert "upgrade" in resp.json()["detail"].lower()


def test_criar_profissional_plano_basico_permite_2(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "basico")
    client.post("/profissionais/", json=_payload("P1"), headers=_headers(est.id, make_tenant_headers))
    resp2 = client.post("/profissionais/", json=_payload("P2"), headers=_headers(est.id, make_tenant_headers))
    assert resp2.status_code == 200


def test_criar_terceiro_profissional_plano_basico_retorna_403(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "basico")
    for i in range(2):
        p = Profissional(nome=f"Existente {i}", estabelecimento_id=est.id)
        db_session.add(p)
    db_session.commit()

    resp = client.post("/profissionais/", json=_payload("Novo"), headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 403


def test_criar_profissional_plano_premium_permite_3(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "premium")
    for i in range(2):
        p = Profissional(nome=f"Existente {i}", estabelecimento_id=est.id)
        db_session.add(p)
    db_session.commit()

    resp = client.post("/profissionais/", json=_payload("Terceiro"), headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 200


def test_criar_quarto_profissional_plano_premium_retorna_400(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "premium")
    for i in range(3):
        p = Profissional(nome=f"Existente {i}", estabelecimento_id=est.id)
        db_session.add(p)
    db_session.commit()

    resp = client.post("/profissionais/", json=_payload("Quarto"), headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 400


# ── atualizar ─────────────────────────────────────────────────────────────────

def test_atualizar_profissional(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session, "basico")
    p = Profissional(nome="Antigo", estabelecimento_id=est.id, ativo=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    resp = client.put(
        f"/profissionais/{p.id}",
        json={"nome": "Novo Nome", "ativo": False, "tempo_por_servico": None, "horarios_funcionamento": None},
        headers=_headers(est.id, make_tenant_headers),
    )
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Novo Nome"
    assert resp.json()["ativo"] is False


def test_atualizar_profissional_inexistente_retorna_404(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session)
    resp = client.put(
        "/profissionais/99999",
        json={"nome": "X", "ativo": True, "tempo_por_servico": None, "horarios_funcionamento": None},
        headers=_headers(est.id, make_tenant_headers),
    )
    assert resp.status_code == 404


def test_atualizar_profissional_de_outro_tenant_retorna_404(client, db_session, make_tenant_headers):
    est1 = _criar_estabelecimento(db_session, "basico")
    est2 = _criar_estabelecimento(db_session, "basico")
    p = Profissional(nome="De Est2", estabelecimento_id=est2.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    resp = client.put(
        f"/profissionais/{p.id}",
        json={"nome": "Hack", "ativo": True, "tempo_por_servico": None, "horarios_funcionamento": None},
        headers=_headers(est1.id, make_tenant_headers),
    )
    assert resp.status_code == 404


# ── remover ───────────────────────────────────────────────────────────────────

def test_remover_profissional(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session)
    p = Profissional(nome="Para Remover", estabelecimento_id=est.id)
    db_session.add(p)
    db_session.commit()
    p_id = p.id

    resp = client.delete(f"/profissionais/{p_id}", headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 204

    db_session.expunge_all()
    assert db_session.query(Profissional).filter(Profissional.id == p_id).first() is None


def test_remover_profissional_inexistente_retorna_404(client, db_session, make_tenant_headers):
    est = _criar_estabelecimento(db_session)
    resp = client.delete("/profissionais/99999", headers=_headers(est.id, make_tenant_headers))
    assert resp.status_code == 404


def test_remover_profissional_de_outro_tenant_retorna_404(client, db_session, make_tenant_headers):
    est1 = _criar_estabelecimento(db_session)
    est2 = _criar_estabelecimento(db_session, "basico")
    p = Profissional(nome="De Est2", estabelecimento_id=est2.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    resp = client.delete(f"/profissionais/{p.id}", headers=_headers(est1.id, make_tenant_headers))
    assert resp.status_code == 404
