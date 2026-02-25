def _criar_agendamento(client, headers, barbeiro_id, servico_id, telefone, nome, inicio_iso):
    payload = {
        "telefone": telefone,
        "nome_cliente": nome,
        "barbeiro_id": barbeiro_id,
        "servico_id": servico_id,
        "data_hora_inicio": inicio_iso,
        "status": "confirmado",
    }
    return client.post("/agendamentos/", json=payload, headers=headers)


def test_horarios_disponiveis_remove_horario_com_conflito(client, dados_base, tenant_headers):
    data = dados_base["amanha"].replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = data.replace(hour=8, minute=0)

    sem_agendamento = client.get(
        "/agenda/horarios-disponiveis",
        params={
            "barbeiro_id": dados_base["barbeiro"].id,
            "servico_id": dados_base["servico"].id,
            "data": data.isoformat(),
        },
        headers=tenant_headers,
    )
    assert sem_agendamento.status_code == 200
    assert "08:00" in sem_agendamento.json()

    created = _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        "5582966666666",
        "Cliente Agenda",
        inicio.isoformat(),
    )
    assert created.status_code == 200

    com_agendamento = client.get(
        "/agenda/horarios-disponiveis",
        params={
            "barbeiro_id": dados_base["barbeiro"].id,
            "servico_id": dados_base["servico"].id,
            "data": data.isoformat(),
        },
        headers=tenant_headers,
    )
    assert com_agendamento.status_code == 200
    assert "08:00" not in com_agendamento.json()


def test_horarios_disponiveis_por_periodo_tarde(client, dados_base, tenant_headers):
    data = dados_base["amanha"].replace(hour=0, minute=0, second=0, microsecond=0)
    resp = client.get(
        "/agenda/horarios-disponiveis",
        params={
            "barbeiro_id": dados_base["barbeiro"].id,
            "servico_id": dados_base["servico"].id,
            "data": data.isoformat(),
            "periodo": "tarde",
        },
        headers=tenant_headers,
    )

    assert resp.status_code == 200
    horarios = resp.json()
    assert horarios
    for h in horarios:
        hora = int(h.split(":")[0])
        assert 12 <= hora < 18


def test_agenda_dia_retorna_agendamentos_por_barbeiro(client, dados_base, tenant_headers):
    data = dados_base["amanha"].replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = data.replace(hour=10, minute=0)
    _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        "5582955555555",
        "Cliente Dia",
        inicio.isoformat(),
    )

    resp = client.get("/agenda/dia", params={"data": data.isoformat()}, headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "horarios" in body
    assert "barbeiros" in body
    assert body["barbeiros"]

    ags = body["barbeiros"][0]["agendamentos"]
    assert any(item["hora"] == "10:00" for item in ags)
