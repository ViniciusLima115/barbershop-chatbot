def test_whatsapp_verify_webhook_ok(client):
    resp = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-whatsapp-verify-token",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == 12345


def test_whatsapp_verify_webhook_token_invalido(client):
    resp = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token_errado",
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 403


def test_whatsapp_receive_message_ignored_sem_entry(client):
    resp = client.post("/whatsapp/webhook", json={})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}


def test_whatsapp_receive_message_ignored_non_text(client):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "type": "image",
                                    "from": "5582999999999",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    resp = client.post("/whatsapp/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}


def test_whatsapp_receive_message_ok(monkeypatch, client):
    import app.routes.whatsapp as whatsapp_module

    enviados = {}

    class DummyDB:
        def close(self):
            pass

    monkeypatch.setattr(whatsapp_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr(
        whatsapp_module,
        "_resolver_tenant_id",
        lambda db, instance_key=None, whatsapp_number=None: 1,
    )
    monkeypatch.setattr(
        whatsapp_module,
        "responder_mensagem",
        lambda db, telefone, texto, tenant_id: "Resposta teste",
    )

    def fake_enviar(telefone, texto, phone_number_id=None):
        enviados["telefone"] = telefone
        enviados["texto"] = texto
        enviados["phone_number_id"] = phone_number_id

    monkeypatch.setattr(whatsapp_module, "enviar_resposta_whatsapp", fake_enviar)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "instance_key": "instancia-1",
                            "metadata": {"phone_number_id": "999"},
                            "messages": [
                                {
                                    "type": "text",
                                    "from": "5582999999999",
                                    "text": {"body": "oi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    resp = client.post("/whatsapp/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert enviados["telefone"] == "5582999999999"
    assert enviados["texto"] == "Resposta teste"
    assert enviados["phone_number_id"] == "999"


def test_whatsapp_receive_message_captura_excecao(monkeypatch, client):
    import app.routes.whatsapp as whatsapp_module

    class DummyDB:
        def close(self):
            pass

    monkeypatch.setattr(whatsapp_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr(
        whatsapp_module,
        "_resolver_tenant_id",
        lambda db, instance_key=None, whatsapp_number=None: 1,
    )

    def quebra(*args, **kwargs):
        raise RuntimeError("falha proposital")

    monkeypatch.setattr(whatsapp_module, "responder_mensagem", quebra)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "type": "text",
                                    "from": "5582999999999",
                                    "text": {"body": "oi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    resp = client.post("/whatsapp/webhook", json=payload)
    assert resp.status_code == 500


def test_whatsapp_receive_message_ignored_sem_tenant(monkeypatch, client):
    import app.routes.whatsapp as whatsapp_module

    class DummyDB:
        def close(self):
            pass

    monkeypatch.setattr(whatsapp_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr(
        whatsapp_module,
        "_resolver_tenant_id",
        lambda db, instance_key=None, whatsapp_number=None: None,
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "sem-mapa"},
                            "messages": [
                                {
                                    "type": "text",
                                    "from": "5582999999999",
                                    "text": {"body": "oi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    resp = client.post("/whatsapp/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}


def test_resolve_tenant_por_instance_key(db_session):
    from app.models.estabelecimento import Estabelecimento
    from app.routes.whatsapp import _resolver_tenant_id

    barbearia = Estabelecimento(
        nome="Estabelecimento Instance",
        endereco="Rua A",
        mega_instance_key="instancia-teste-1",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    tenant_id = _resolver_tenant_id(db_session, instance_key="instancia-teste-1")
    assert tenant_id == barbearia.id
