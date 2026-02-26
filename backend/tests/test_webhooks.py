def test_webhook_megaapi_exige_assinatura_ou_token(monkeypatch, client):
    import app.routes.webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_ALLOW_UNSIGNED", False)
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_TOKEN", "token-seguro")
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_SECRET", None)

    payload = {
        "instance_key": "inst-1",
        "data": {"from": "5582999999999", "text": "oi"},
        "event_id": "evt-1",
    }
    resp = client.post("/webhooks/megaapi", json=payload)
    assert resp.status_code == 401


def test_webhook_megaapi_processa_por_instance_key(monkeypatch, client, db_session):
    import app.routes.webhooks as webhooks_module
    from app.models.barbearia import Barbearia

    barbearia = Barbearia(
        nome="Barbearia Webhook",
        endereco="Rua A",
        mega_instance_key="inst-tenant-1",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_ALLOW_UNSIGNED", False)
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_TOKEN", "token-seguro")
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_SECRET", None)
    monkeypatch.setattr(
        webhooks_module,
        "responder_mensagem",
        lambda db, telefone, texto, tenant_id: {"resposta": f"ok-{tenant_id}"},
    )

    payload = {
        "instance_key": "inst-tenant-1",
        "data": {"from": "5582998887777", "text": "oi"},
        "event_id": "evt-ok-1",
    }
    resp = client.post(
        "/webhooks/megaapi",
        headers={"X-Webhook-Token": "token-seguro"},
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tenant_id"] == barbearia.id
    assert body["event_id"] == "evt-ok-1"


def test_webhook_megaapi_ignora_evento_duplicado(monkeypatch, client, db_session):
    import app.routes.webhooks as webhooks_module
    from app.models.barbearia import Barbearia

    barbearia = Barbearia(
        nome="Barbearia Duplicado",
        endereco="Rua B",
        mega_instance_key="inst-tenant-dup",
    )
    db_session.add(barbearia)
    db_session.commit()

    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_ALLOW_UNSIGNED", False)
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_TOKEN", "token-seguro")
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_SECRET", None)
    monkeypatch.setattr(
        webhooks_module,
        "responder_mensagem",
        lambda db, telefone, texto, tenant_id: "ok",
    )

    payload = {
        "instance_key": "inst-tenant-dup",
        "data": {"from": "5582991111111", "text": "oi"},
        "event_id": "evt-dup-1",
    }
    headers = {"X-Webhook-Token": "token-seguro"}

    first = client.post("/webhooks/megaapi", headers=headers, json=payload)
    second = client.post("/webhooks/megaapi", headers=headers, json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert second.json()["reason"] == "evento_duplicado"


def test_webhook_megaapi_ignora_sem_tenant(monkeypatch, client):
    import app.routes.webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_ALLOW_UNSIGNED", False)
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_TOKEN", "token-seguro")
    monkeypatch.setattr(webhooks_module, "MEGAAPI_WEBHOOK_SECRET", None)

    payload = {
        "instance_key": "inst-inexistente",
        "data": {"from": "5582992222222", "text": "oi"},
        "event_id": "evt-no-tenant",
    }
    resp = client.post(
        "/webhooks/megaapi",
        headers={"X-Webhook-Token": "token-seguro"},
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert resp.json()["reason"] == "tenant_nao_resolvido"
