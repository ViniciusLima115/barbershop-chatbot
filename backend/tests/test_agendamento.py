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


def test_agendamentos_sao_isolados_por_barbearia(
    client,
    db_session,
    dados_base,
    tenant_headers,
    make_tenant_headers,
):
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

    headers_b = make_tenant_headers(barbearia_b.id)
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


def test_listar_agendamentos_com_filtro_data(client, dados_base, tenant_headers):
    amanha = dados_base["amanha"].replace(hour=10, minute=0, second=0, microsecond=0)
    depois = dados_base["amanha"].replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2)

    payload_1 = {
        "telefone": "5582911111111",
        "nome_cliente": "Cliente Amanha",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": amanha.isoformat(),
        "status": "confirmado",
    }
    payload_2 = {
        "telefone": "5582922222222",
        "nome_cliente": "Cliente Depois",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": depois.isoformat(),
        "status": "confirmado",
    }
    assert client.post("/agendamentos/", json=payload_1, headers=tenant_headers).status_code == 200
    assert client.post("/agendamentos/", json=payload_2, headers=tenant_headers).status_code == 200

    listar_amanha = client.get(
        "/agendamentos/",
        params={"data": amanha.date().isoformat()},
        headers=tenant_headers,
    )
    assert listar_amanha.status_code == 200
    body = listar_amanha.json()
    assert len(body) == 1
    assert body[0]["cliente_nome"] == "Cliente Amanha"


def test_patch_agendamento_altera_status(client, dados_base, tenant_headers):
    inicio = dados_base["amanha"].replace(hour=13, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582933333333",
        "nome_cliente": "Cliente Patch",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    created = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert created.status_code == 200
    agendamento_id = created.json()["id"]

    patch = client.patch(
        f"/agendamentos/{agendamento_id}",
        json={"status": "cancelado"},
        headers=tenant_headers,
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "cancelado"


def test_remover_agendamento_remove_reminders_relacionados(
    client,
    db_session,
    dados_base,
    tenant_headers,
):
    from app.models.reminder_job import ReminderJob

    inicio = dados_base["amanha"].replace(hour=16, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582944444444",
        "nome_cliente": "Cliente Delete",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }

    created = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert created.status_code == 200
    agendamento_id = created.json()["id"]

    db_session.add(
        ReminderJob(
            tenant_id=dados_base["barbearia"].id,
            agendamento_id=agendamento_id,
            tipo="reminder_2h",
            canal="whatsapp",
            destinatario="5582944444444",
            mensagem="Lembrete de teste",
            enviar_em=inicio - timedelta(hours=2),
            status="pendente",
        )
    )
    db_session.commit()

    response = client.delete(f"/agendamentos/{agendamento_id}", headers=tenant_headers)
    assert response.status_code == 204

    assert (
        db_session.query(ReminderJob)
        .filter(ReminderJob.agendamento_id == agendamento_id)
        .count()
        == 0
    )
