from datetime import datetime, timedelta

from app.models.barbeiro import Barbeiro
from app.models.servico import Servico


def _funcionamento_seg_a_sab():
    return {
        "seg": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }


def _funcionamento_tarde():
    return {
        "seg": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }


def _proximo_dia_semana(target_weekday: int) -> datetime:
    now = datetime.now()
    delta = (target_weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return now + timedelta(days=delta)


def test_tenant_pode_salvar_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_seg_a_sab()

    resp = client.put("/barbearias/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    assert resp.json()["dom"]["ativo"] is False
    assert resp.json()["seg"]["inicio"] == "08:00"

    db_session.refresh(dados_base["barbearia"])
    assert dados_base["barbearia"].horarios_funcionamento["sab"]["fim"] == "18:00"


def test_horarios_publicos_respeitam_dia_fechado(client, db_session):
    from app.models.barbearia import Barbearia

    barbearia = Barbearia(
        nome="Barbearia Horarios",
        slug="barbearia-horarios",
        horarios_funcionamento=_funcionamento_seg_a_sab(),
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(nome="Carlos", barbershop_id=barbearia.id, ativo=True)
    servico = Servico(nome="Corte", duracao_minutos=40, preco=45.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    domingo = _proximo_dia_semana(6).date()
    resp = client.get(
        "/public/horarios-disponiveis",
        params={
            "barbearia_id": barbearia.id,
            "barbeiro_id": barbeiro.id,
            "servico_id": servico.id,
            "data": domingo.isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["horarios_disponiveis"] == []
    assert body["horarios_grade"] == []


def test_agendamento_bloqueia_horario_fora_do_funcionamento(
    client,
    dados_base,
    tenant_headers,
    db_session,
):
    dados_base["barbearia"].horarios_funcionamento = _funcionamento_seg_a_sab()
    db_session.commit()
    db_session.refresh(dados_base["barbearia"])

    segunda = _proximo_dia_semana(0).replace(hour=19, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582999990000",
        "nome_cliente": "Cliente Fora",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": segunda.isoformat(),
        "status": "confirmado",
    }

    resp = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Horário fora do funcionamento da barbearia"


def test_agendamento_bloqueia_horario_fora_do_funcionamento_do_barbeiro(
    client,
    dados_base,
    tenant_headers,
    db_session,
):
    dados_base["barbearia"].horarios_funcionamento = _funcionamento_seg_a_sab()
    dados_base["barbeiro"].horarios_funcionamento = _funcionamento_tarde()
    db_session.commit()
    db_session.refresh(dados_base["barbearia"])
    db_session.refresh(dados_base["barbeiro"])

    segunda = _proximo_dia_semana(0).replace(hour=10, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582999991000",
        "nome_cliente": "Cliente Barbeiro",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": segunda.isoformat(),
        "status": "confirmado",
    }

    resp = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Horário fora do funcionamento do barbeiro"
