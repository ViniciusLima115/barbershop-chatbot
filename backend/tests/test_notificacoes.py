from datetime import datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.notificacao import Notificacao
from app.repositories import notificacao_repository as repo
from app.services.notificacao_inapp_service import (
    criar_notificacao_confirmado,
    criar_notificacao_novo_agendamento,
    processar_pendentes_confirmacao,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _criar_agendamento(db_session, dados_base, *, hora_inicio=None, status="pendente"):
    barbearia = dados_base["barbearia"]
    barbeiro = dados_base["barbeiro"]
    servico = dados_base["servico"]
    inicio = hora_inicio or dados_base["amanha"]
    fim = inicio + timedelta(minutes=servico.duracao_minutos)

    from app.models.cliente import Cliente
    cliente = Cliente(telefone="11999999999", nome="Teste", barbearia_id=barbearia.id)
    db_session.add(cliente)
    db_session.flush()

    ag = Agendamento(
        cliente_id=cliente.id,
        profissional_id=barbeiro.id,
        servico_id=servico.id,
        estabelecimento_id=barbearia.id,
        cliente_nome="Teste",
        cliente_telefone="11999999999",
        data=inicio.date(),
        hora_inicio=inicio.time(),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status=status,
    )
    db_session.add(ag)
    db_session.commit()
    db_session.refresh(ag)
    return ag


# ── testes do repositório ─────────────────────────────────────────────────────

def test_criar_notificacao_basica(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    notif = repo.criar(
        db_session,
        estabelecimento_id=barbearia.id,
        tipo="novo_agendamento",
        titulo="Novo agendamento",
        corpo="Teste · Corte · 01/01 10:00",
    )
    db_session.commit()
    assert notif.id is not None
    assert notif.lida is False
    assert notif.estabelecimento_id == barbearia.id


def test_listar_apenas_nao_lidas(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="A")
    notif_lida = repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="B")
    notif_lida.lida = True
    db_session.commit()

    todas = repo.listar(db_session, estabelecimento_id=barbearia.id)
    nao_lidas = repo.listar(db_session, estabelecimento_id=barbearia.id, apenas_nao_lidas=True)
    assert len(todas) == 2
    assert len(nao_lidas) == 1
    assert nao_lidas[0].titulo == "A"


def test_isolamento_tenant(db_session, dados_base):
    from app.models.estabelecimento import Estabelecimento as Est
    outro = Est(nome="Outro", endereco="Rua 2")
    db_session.add(outro)
    db_session.commit()

    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="Minha")
    repo.criar(db_session, estabelecimento_id=outro.id, tipo="novo_agendamento", titulo="Outra")
    db_session.commit()

    minhas = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(minhas) == 1
    assert minhas[0].titulo == "Minha"


def test_existe_pendente_confirmacao_idempotente(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base)
    assert repo.existe_pendente_confirmacao(db_session, agendamento_id=ag.id) is False
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, agendamento_id=ag.id, tipo="pendente_confirmacao", titulo="Confirmar")
    db_session.commit()
    assert repo.existe_pendente_confirmacao(db_session, agendamento_id=ag.id) is True


def test_marcar_todas_lidas(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="A")
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="B")
    db_session.commit()

    count = repo.marcar_todas_lidas(db_session, estabelecimento_id=barbearia.id)
    db_session.commit()
    assert count == 2
    nao_lidas = repo.listar(db_session, estabelecimento_id=barbearia.id, apenas_nao_lidas=True)
    assert len(nao_lidas) == 0


# ── testes do serviço ─────────────────────────────────────────────────────────

def test_criar_notificacao_novo_agendamento(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base)
    criar_notificacao_novo_agendamento(db_session, ag)

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(notifs) == 1
    assert notifs[0].tipo == "novo_agendamento"
    assert notifs[0].agendamento_id == ag.id


def test_criar_notificacao_confirmado(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base, status="confirmado")
    criar_notificacao_confirmado(db_session, ag)

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(notifs) == 1
    assert notifs[0].tipo == "agendamento_confirmado"


def test_processar_pendentes_apenas_horario_passado(db_session, dados_base):
    futuro = _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() + timedelta(hours=2))
    passado = _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2))

    count = processar_pendentes_confirmacao(db_session)
    assert count == 1

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    tipos = [n.tipo for n in notifs]
    assert "pendente_confirmacao" in tipos
    assert all(n.agendamento_id == passado.id for n in notifs if n.tipo == "pendente_confirmacao")


def test_processar_pendentes_idempotente(db_session, dados_base):
    _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2))

    count1 = processar_pendentes_confirmacao(db_session)
    count2 = processar_pendentes_confirmacao(db_session)
    assert count1 == 1
    assert count2 == 0  # segunda execução não duplica


def test_processar_pendentes_ignora_status_invalido(db_session, dados_base):
    _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2), status="cancelado")
    count = processar_pendentes_confirmacao(db_session)
    assert count == 0


# ── testes de endpoint via HTTP ───────────────────────────────────────────────

def test_get_notificacoes_vazio(client, tenant_headers):
    res = client.get("/notificacoes/", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_get_notificacoes_retorna_do_tenant(client, db_session, dados_base, tenant_headers):
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="Minha notif")
    db_session.commit()

    res = client.get("/notificacoes/", headers=tenant_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "Minha notif"
    assert data[0]["lida"] is False


def test_marcar_lida_endpoint(client, db_session, dados_base, tenant_headers):
    notif = repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="X")
    db_session.commit()

    res = client.patch(f"/notificacoes/{notif.id}/lida", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json()["lida"] is True


def test_marcar_todas_lidas_endpoint(client, db_session, dados_base, tenant_headers):
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="A")
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="B")
    db_session.commit()

    res = client.post("/notificacoes/marcar-todas-lidas", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json()["marcadas"] == 2


def test_confirmar_presenca_compareceu(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)

    res = client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": True},
        headers=tenant_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "compareceu"

    db_session.refresh(ag)
    assert ag.status == "compareceu"
    assert ag.compareceu_em is not None


def test_confirmar_presenca_no_show(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)

    res = client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": False},
        headers=tenant_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "no_show"


def test_confirmar_presenca_marca_notificacao_lida(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)
    repo.criar(
        db_session,
        estabelecimento_id=dados_base["barbearia"].id,
        agendamento_id=ag.id,
        tipo="pendente_confirmacao",
        titulo="Confirmar presença",
    )
    db_session.commit()

    client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": True},
        headers=tenant_headers,
    )

    nao_lidas = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id, apenas_nao_lidas=True)
    assert len(nao_lidas) == 0
