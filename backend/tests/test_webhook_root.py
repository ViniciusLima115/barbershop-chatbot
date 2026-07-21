from app.models.estabelecimento import Estabelecimento
from app.models.conversa import Conversa
from app.models.webhook_event import WebhookEvent


def test_webhook_primeira_mensagem_envia_saudacao_e_cria_conversa(monkeypatch, client, db_session):
    import app.services.webhook_greeting_service as greeting_service

    enviados = {}

    def fake_enviar(barbearia, telefone, mensagem):
        enviados["barbearia"] = barbearia.id
        enviados["telefone"] = telefone
        enviados["mensagem"] = mensagem
        return True

    monkeypatch.setattr(greeting_service, "enviar_mensagem_whatsapp", fake_enviar)

    barbearia = Estabelecimento(
        nome="Estabelecimento Teste",
        slug="barbearia-teste",
        mega_instance_key="inst-webhook",
        whatsapp_number="5582999912345",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    payload = {
        "instance_key": "inst-webhook",
        "data": {"from": "5582990001111", "text": "Oi"},
        "event_id": "evt-webhook-1",
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["saudacao_enviada"] is True
    assert f"/agendar/{barbearia.id}" in body["mensagem"]

    conversa = (
        db_session.query(Conversa)
        .filter(Conversa.tenant_id == barbearia.id, Conversa.telefone == "5582990001111")
        .first()
    )
    assert conversa is not None
    assert conversa.ativa is True
    assert conversa.estado == "saudacao_enviada"

    evento = (
        db_session.query(WebhookEvent)
        .filter(WebhookEvent.provider == "meta-webhook", WebhookEvent.event_id == "evt-webhook-1")
        .first()
    )
    assert evento is not None
    assert evento.tenant_id == barbearia.id
    assert enviados["telefone"] == "5582990001111"


def test_webhook_nao_repete_saudacao_com_conversa_ativa(monkeypatch, client, db_session):
    import app.services.webhook_greeting_service as greeting_service

    chamadas = {"total": 0}

    def fake_enviar(*args, **kwargs):
        chamadas["total"] += 1
        return True

    monkeypatch.setattr(greeting_service, "enviar_mensagem_whatsapp", fake_enviar)

    barbearia = Estabelecimento(
        nome="Estabelecimento Fluxo",
        slug="barbearia-fluxo",
        mega_instance_key="inst-webhook-2",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    primeiro = client.post(
        "/webhook",
        json={
            "instance_key": "inst-webhook-2",
            "data": {"from": "5582990002222", "text": "Oi"},
            "event_id": "evt-webhook-2a",
        },
    )
    segundo = client.post(
        "/webhook",
        json={
            "instance_key": "inst-webhook-2",
            "data": {"from": "5582990002222", "text": "quero agendar"},
            "event_id": "evt-webhook-2b",
        },
    )

    assert primeiro.status_code == 200
    assert primeiro.json()["saudacao_enviada"] is True
    assert segundo.status_code == 200
    assert segundo.json()["saudacao_enviada"] is False
    assert chamadas["total"] == 1
