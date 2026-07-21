"""
Testes do endpoint GET /dashboard/{id}/analise
"""
from datetime import date, datetime, time, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.models.estabelecimento import Estabelecimento
from app.models.profissional import Profissional
from app.models.servico import Servico


DIA_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@pytest.fixture
def dados_analise(db_session):
    hoje = date.today()
    agora = datetime.now()
    inicio_mes = hoje.replace(day=1)

    est_a = Estabelecimento(nome="Est A", plano="premium")
    est_b = Estabelecimento(nome="Est B", plano="premium")
    est_c = Estabelecimento(nome="Est C Vazio", plano="premium")
    db_session.add_all([est_a, est_b, est_c])
    db_session.commit()
    db_session.refresh(est_a)
    db_session.refresh(est_b)
    db_session.refresh(est_c)

    prof_a = Profissional(nome="Prof A", estabelecimento_id=est_a.id)
    prof_b = Profissional(nome="Prof B", estabelecimento_id=est_b.id)
    db_session.add_all([prof_a, prof_b])
    db_session.commit()
    db_session.refresh(prof_a)
    db_session.refresh(prof_b)

    corte = Servico(nome="Corte", duracao_minutos=30, preco=40.0, estabelecimento_id=est_a.id)
    barba = Servico(nome="Barba", duracao_minutos=20, preco=30.0, estabelecimento_id=est_a.id)
    serv_b = Servico(nome="Corte B", duracao_minutos=30, preco=50.0, estabelecimento_id=est_b.id)
    db_session.add_all([corte, barba, serv_b])
    db_session.commit()
    db_session.refresh(corte)
    db_session.refresh(barba)
    db_session.refresh(serv_b)

    cli_a = Cliente(nome="Alice", telefone="111", estabelecimento_id=est_a.id)
    cli_b = Cliente(nome="Bob", telefone="222", estabelecimento_id=est_a.id)
    cli_c = Cliente(nome="Carol", telefone="333", estabelecimento_id=est_a.id)
    cli_b2 = Cliente(nome="Dave", telefone="999", estabelecimento_id=est_b.id)
    db_session.add_all([cli_a, cli_b, cli_c, cli_b2])
    db_session.commit()
    for c in [cli_a, cli_b, cli_c, cli_b2]:
        db_session.refresh(c)

    d1 = hoje  # garantido <= hoje nas queries do mês

    def _ag(est_id, prof_id, serv_id, cli_id, tel, nome, data, hora_h, hora_m, status):
        dt = datetime(data.year, data.month, data.day, hora_h, hora_m)
        return Agendamento(
            estabelecimento_id=est_id,
            profissional_id=prof_id,
            servico_id=serv_id,
            cliente_id=cli_id,
            cliente_nome=nome,
            cliente_telefone=tel,
            data=data,
            hora_inicio=time(hora_h, hora_m),
            data_hora_inicio=dt,
            data_hora_fim=dt + timedelta(hours=1),
            status=status,
        )

    # 4 confirmados: 3x Corte (Alice, Bob, Carol) + 1x Barba (Alice → recorrente)
    ag1 = _ag(est_a.id, prof_a.id, corte.id, cli_a.id, "111", "Alice", d1, 9, 0, "confirmado")
    ag2 = _ag(est_a.id, prof_a.id, corte.id, cli_b.id, "222", "Bob",   d1, 18, 0, "confirmado")
    ag3 = _ag(est_a.id, prof_a.id, corte.id, cli_c.id, "333", "Carol", d1, 18, 0, "confirmado")
    ag4 = _ag(est_a.id, prof_a.id, barba.id, cli_a.id, "111", "Alice", d1, 10, 0, "confirmado")
    # 1 cancelado
    ag5 = _ag(est_a.id, prof_a.id, corte.id, cli_b.id, "222", "Bob",   d1, 14, 0, "cancelado")
    # no-show: pendente com data_hora_inicio no passado (1º do mês às 00:01)
    dt_noshow = datetime(inicio_mes.year, inicio_mes.month, inicio_mes.day, 0, 1)
    ag6 = Agendamento(
        estabelecimento_id=est_a.id, profissional_id=prof_a.id,
        servico_id=corte.id, cliente_id=cli_b.id,
        cliente_nome="Bob", cliente_telefone="222",
        data=dt_noshow.date(), hora_inicio=time(0, 1),
        data_hora_inicio=dt_noshow, data_hora_fim=dt_noshow + timedelta(hours=1),
        status="pendente",
    )
    # pendente futuro: não é no-show
    dt_futuro = agora + timedelta(hours=2)
    ag7 = Agendamento(
        estabelecimento_id=est_a.id, profissional_id=prof_a.id,
        servico_id=corte.id, cliente_id=cli_a.id,
        cliente_nome="Alice", cliente_telefone="111",
        data=dt_futuro.date(), hora_inicio=time(dt_futuro.hour % 24, dt_futuro.minute),
        data_hora_inicio=dt_futuro, data_hora_fim=dt_futuro + timedelta(hours=1),
        status="pendente",
    )
    # est_b: 1 confirmado — não deve aparecer nos resultados de est_a
    ag_b = _ag(est_b.id, prof_b.id, serv_b.id, cli_b2.id, "999", "Dave", d1, 9, 0, "confirmado")

    db_session.add_all([ag1, ag2, ag3, ag4, ag5, ag6, ag7, ag_b])
    db_session.commit()

    return {"est_a": est_a, "est_b": est_b, "est_c": est_c, "d1": d1}


def _get(client, est_id, headers):
    return client.get(f"/dashboard/{est_id}/analise", headers=headers)


def test_resumo_agendamentos(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    assert resp.json()["resumo"]["agendamentos"] == 4


def test_resumo_faturamento(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # 3 × R$40 + 1 × R$30 = R$150
    assert resp.json()["resumo"]["faturamento"] == pytest.approx(150.0)


def test_resumo_ticket_medio(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # R$150 / 4 = R$37.50
    assert resp.json()["resumo"]["ticket_medio"] == pytest.approx(37.5)


def test_resumo_ocupacao(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # confirmados=4, cancelados=1, no_show=1 → round(4/6*100) = 67
    assert resp.json()["resumo"]["ocupacao"] == 67


def test_semana_dia_e_contagem(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    d1 = dados_analise["d1"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    semana = resp.json()["semana"]
    # ag1, ag2, ag3, ag4 estão todos em d1 → 4 no dia da semana de d1
    expected_label = DIA_LABELS[d1.weekday()]
    dias = {item["dia"]: item["clientes"] for item in semana}
    assert dias[expected_label] == 4


def test_horarios_ordenados_por_volume(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    horarios = resp.json()["horarios"]
    # 18:00 tem 2 atendimentos (ag2 + ag3); os demais têm 1
    assert horarios[0]["hora"] == "18:00"
    assert horarios[0]["atendimentos"] == 2
    assert len(horarios) <= 5


def test_servicos_ordenados_por_total(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    servicos = resp.json()["servicos"]
    assert servicos[0]["nome"] == "Corte"
    assert servicos[0]["total"] == 3
    assert servicos[1]["nome"] == "Barba"
    assert servicos[1]["total"] == 1


def test_clientes_novos_e_recorrentes(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    clientes = resp.json()["clientes"]
    # Alice (111): ag1 + ag4 = 2 visitas → recorrente
    # Bob (222): ag2 = 1 visita → novo
    # Carol (333): ag3 = 1 visita → novo
    assert clientes["novos"] == 2
    assert clientes["recorrentes"] == 1


def test_clientes_cancelamentos(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    assert resp.json()["clientes"]["cancelamentos"] == 1


def test_clientes_no_show(client, dados_analise, make_tenant_headers):
    est = dados_analise["est_a"]
    resp = _get(client, est.id, make_tenant_headers(tenant_id=est.id))
    assert resp.status_code == 200
    # ag6: pendente com data_hora_inicio no passado → no-show
    # ag7: pendente com data_hora_inicio no futuro → não é no-show
    assert resp.json()["clientes"]["no_show"] == 1


def test_mes_vazio(client, dados_analise, make_tenant_headers):
    est_c = dados_analise["est_c"]
    resp = _get(client, est_c.id, make_tenant_headers(tenant_id=est_c.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resumo"]["agendamentos"] == 0
    assert body["resumo"]["faturamento"] == 0.0
    assert body["resumo"]["ocupacao"] == 0
    assert body["semana"] == []
    assert body["horarios"] == []
    assert body["servicos"] == []
    assert body["clientes"]["novos"] == 0
    assert body["clientes"]["cancelamentos"] == 0
    assert body["clientes"]["no_show"] == 0


def test_tenant_isolamento(client, dados_analise, make_tenant_headers):
    est_a = dados_analise["est_a"]
    resp = _get(client, est_a.id, make_tenant_headers(tenant_id=est_a.id))
    assert resp.status_code == 200
    # est_b tem 1 agendamento (ag_b) — não deve aparecer
    assert resp.json()["resumo"]["agendamentos"] == 4


def test_403_tenant_errado(client, dados_analise, make_tenant_headers):
    est_a = dados_analise["est_a"]
    est_b = dados_analise["est_b"]
    # Token de est_a, mas tentando acessar endpoint de est_b
    headers = make_tenant_headers(tenant_id=est_a.id)
    resp = client.get(f"/dashboard/{est_b.id}/analise", headers=headers)
    assert resp.status_code == 403


def test_401_sem_token(client, dados_analise):
    est = dados_analise["est_a"]
    resp = client.get(f"/dashboard/{est.id}/analise")
    assert resp.status_code == 401


def test_403_plano_basico(client, db_session, make_tenant_headers):
    est_basico = Estabelecimento(nome="Básico", plano="basico")
    db_session.add(est_basico)
    db_session.commit()
    db_session.refresh(est_basico)
    headers = make_tenant_headers(tenant_id=est_basico.id)
    resp = client.get(f"/dashboard/{est_basico.id}/analise", headers=headers)
    assert resp.status_code == 403
