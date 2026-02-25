from datetime import datetime, timedelta


def test_criar_agendamento_com_sucesso(client, dados_base, tenant_headers):
    inicio = (dados_base["amanha"].replace(hour=14, minute=0, second=0, microsecond=0)).isoformat()
    payload = {
        "telefone": "5582999999999",
        "nome_cliente": "Vinicius",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio,
        "status": "confirmado",
    }

    resp = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmado"
    assert body["servico_nome"] == "corte social"
    assert body["cliente_nome"] == "Vinicius"


def test_criar_agendamento_com_conflito(client, dados_base, tenant_headers):
    inicio = dados_base["amanha"].replace(hour=14, minute=0, second=0, microsecond=0)
    payload_1 = {
        "telefone": "5582999999999",
        "nome_cliente": "Cliente 1",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    payload_2 = {
        "telefone": "5582988888888",
        "nome_cliente": "Cliente 2",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": (inicio + timedelta(minutes=20)).isoformat(),
        "status": "confirmado",
    }

    first = client.post("/agendamentos/", json=payload_1, headers=tenant_headers)
    assert first.status_code == 200

    second = client.post("/agendamentos/", json=payload_2, headers=tenant_headers)
    assert second.status_code == 400
    assert second.json()["detail"] == "Horário indisponível"


def test_atualizar_status_agendamento(client, dados_base, tenant_headers):
    inicio = dados_base["amanha"].replace(hour=15, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582977777777",
        "nome_cliente": "Cliente Status",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    created = client.post("/agendamentos/", json=payload, headers=tenant_headers).json()

    resp = client.patch(
        f"/agendamentos/{created['id']}/status",
        json={"status": "cancelado"},
        headers=tenant_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelado"


def test_atualizar_status_agendamento_inexistente(client, tenant_headers):
    resp = client.patch(
        "/agendamentos/9999/status",
        json={"status": "cancelado"},
        headers=tenant_headers,
    )
    assert resp.status_code == 404


def test_agendamentos_sao_isolados_por_barbearia(client, db_session, dados_base, tenant_headers):
    from app.models.barbearia import Barbearia
    from app.models.barbeiro import Barbeiro
    from app.models.servico import Servico

    barbearia_b = Barbearia(nome="Barbearia B", endereco="Rua B")
    db_session.add(barbearia_b)
    db_session.commit()
    db_session.refresh(barbearia_b)

    barbeiro_b = Barbeiro(nome="Barbeiro B", barbearia_id=barbearia_b.id)
    servico_b = Servico(
        nome="Servico B",
        duracao_minutos=30,
        preco=30.0,
        barbearia_id=barbearia_b.id,
    )
    db_session.add_all([barbeiro_b, servico_b])
    db_session.commit()
    db_session.refresh(barbeiro_b)
    db_session.refresh(servico_b)

    headers_b = {"X-Barbearia-Id": str(barbearia_b.id)}
    inicio_a = dados_base["amanha"].replace(hour=11, minute=0, second=0, microsecond=0)
    inicio_b = dados_base["amanha"].replace(hour=12, minute=0, second=0, microsecond=0)

    payload_a = {
        "telefone": "558290000001",
        "nome_cliente": "Cliente A",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio_a.isoformat(),
        "status": "confirmado",
    }
    payload_b = {
        "telefone": "558290000002",
        "nome_cliente": "Cliente B",
        "barbeiro_id": barbeiro_b.id,
        "servico_id": servico_b.id,
        "data_hora_inicio": inicio_b.isoformat(),
        "status": "confirmado",
    }

    create_a = client.post("/agendamentos/", json=payload_a, headers=tenant_headers)
    create_b = client.post("/agendamentos/", json=payload_b, headers=headers_b)
    assert create_a.status_code == 200
    assert create_b.status_code == 200

    listar_a = client.get("/agendamentos/", headers=tenant_headers)
    listar_b = client.get("/agendamentos/", headers=headers_b)
    assert listar_a.status_code == 200
    assert listar_b.status_code == 200
    assert len(listar_a.json()) == 1
    assert len(listar_b.json()) == 1

    agendamento_id_b = create_b.json()["id"]
    patch_cruzado = client.patch(
        f"/agendamentos/{agendamento_id_b}/status",
        json={"status": "cancelado"},
        headers=tenant_headers,
    )
    assert patch_cruzado.status_code == 404
