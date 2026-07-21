from datetime import datetime, timedelta


def _funcionamento_padrao():
    return {
        "seg": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "09:00", "fim": "14:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }


def test_obter_funcionamento(client, dados_base, tenant_headers, db_session):
    dados_base["barbearia"].horarios_funcionamento = _funcionamento_padrao()
    db_session.commit()

    resp = client.get("/estabelecimentos/me/funcionamento", headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["seg"]["ativo"] is True
    assert body["dom"]["ativo"] is False


def test_atualizar_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_padrao()
    payload["sab"]["ativo"] = False

    resp = client.put("/estabelecimentos/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    assert resp.json()["sab"]["ativo"] is False

    db_session.refresh(dados_base["barbearia"])
    assert dados_base["barbearia"].horarios_funcionamento["sab"]["ativo"] is False


def test_obter_funcionamento_nao_encontrado(client, make_tenant_headers):
    headers = make_tenant_headers(tenant_id=99999)
    resp = client.get("/estabelecimentos/me/funcionamento", headers=headers)
    assert resp.status_code == 401


def test_atualizar_funcionamento_nao_encontrado(client, make_tenant_headers):
    headers = make_tenant_headers(tenant_id=99999)
    resp = client.put(
        "/estabelecimentos/me/funcionamento",
        json=_funcionamento_padrao(),
        headers=headers,
    )
    assert resp.status_code == 401


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


def _proximo_dia_semana(target_weekday: int) -> datetime:
    now = datetime.now()
    delta = (target_weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return now + timedelta(days=delta)


def test_tenant_pode_salvar_funcionamento(client, dados_base, tenant_headers, db_session):
    payload = _funcionamento_seg_a_sab()

    resp = client.put("/estabelecimentos/me/funcionamento", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    assert resp.json()["dom"]["ativo"] is False
    assert resp.json()["seg"]["inicio"] == "08:00"

    db_session.refresh(dados_base["barbearia"])
    assert dados_base["barbearia"].horarios_funcionamento["sab"]["fim"] == "18:00"


def test_horarios_publicos_respeitam_dia_fechado(client, db_session):
    from app.models.estabelecimento import Estabelecimento
    from app.models.profissional import Profissional
    from app.models.servico import Servico

    estabelecimento = Estabelecimento(
        nome="Estabelecimento Horarios",
        slug="estabelecimento-horarios",
        horarios_funcionamento=_funcionamento_seg_a_sab(),
    )
    db_session.add(estabelecimento)
    db_session.commit()
    db_session.refresh(estabelecimento)

    barbeiro = Profissional(nome="Carlos", estabelecimento_id=estabelecimento.id, ativo=True)
    servico = Servico(nome="Corte", duracao_minutos=40, preco=45.0, estabelecimento_id=estabelecimento.id)
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    domingo = _proximo_dia_semana(6).date()
    resp = client.get(
        "/public/horarios-disponiveis",
        params={
            "estabelecimento_id": estabelecimento.id,
            "barbeiro_id": barbeiro.id,
            "servico_id": servico.id,
            "data": domingo.isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["horarios_disponiveis"] == []
    assert body["horarios_grade"] == []


def test_agendamento_bloqueia_horario_fora_do_funcionamento(client, dados_base, tenant_headers, db_session):
    payload_funcionamento = _funcionamento_seg_a_sab()
    resp_put = client.put("/estabelecimentos/me/funcionamento", json=payload_funcionamento, headers=tenant_headers)
    assert resp_put.status_code == 200

    domingo = _proximo_dia_semana(6)
    inicio = domingo.replace(hour=10, minute=0, second=0, microsecond=0)

    resp = client.post(
        "/agendamentos/",
        json={
            "telefone": "5582999999999",
            "nome_cliente": "Cliente Teste",
            "barbeiro_id": dados_base["barbeiro"].id,
            "servico_id": dados_base["servico"].id,
            "data_hora_inicio": inicio.isoformat(),
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Horário fora do funcionamento do estabelecimento"


def test_agendamento_bloqueia_horario_fora_do_funcionamento_do_barbeiro(
    client, dados_base, tenant_headers, db_session
):
    barbeiro = dados_base["barbeiro"]
    barbeiro.horarios_funcionamento = {
        **_funcionamento_seg_a_sab(),
        "seg": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }
    db_session.commit()

    segunda = _proximo_dia_semana(0)
    inicio = segunda.replace(hour=10, minute=0, second=0, microsecond=0)

    resp = client.post(
        "/agendamentos/",
        json={
            "telefone": "5582999999999",
            "nome_cliente": "Cliente Teste",
            "barbeiro_id": barbeiro.id,
            "servico_id": dados_base["servico"].id,
            "data_hora_inicio": inicio.isoformat(),
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Horário fora da disponibilidade do profissional"
