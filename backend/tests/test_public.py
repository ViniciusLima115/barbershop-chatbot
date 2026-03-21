from datetime import datetime, timedelta

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.reminder_job import ReminderJob
from app.models.servico import Servico


def test_public_lookup_retorna_barbeiros_servicos_e_horarios(client, db_session):
    barbearia = Barbearia(nome="Barbearia Publica", slug="publica", endereco="Rua Publica")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro_ativo = Barbeiro(nome="Ativo", barbershop_id=barbearia.id, ativo=True)
    barbeiro_inativo = Barbeiro(nome="Inativo", barbershop_id=barbearia.id, ativo=False)
    servico = Servico(nome="Corte", duracao_minutos=40, preco=50.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro_ativo, barbeiro_inativo, servico])
    db_session.commit()
    db_session.refresh(barbeiro_ativo)
    db_session.refresh(servico)

    data_futura = (datetime.now() + timedelta(days=2)).date()
    resp = client.get(
        "/public/barbearia/publica",
        params={
            "barbeiro_id": barbeiro_ativo.id,
            "servico_id": servico.id,
            "data": data_futura.isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Barbearia Publica"
    assert body["barbearia_id"] == barbearia.id
    assert body["slug"] == "publica"
    assert len(body["barbeiros"]) == 1
    assert body["barbeiros"][0]["nome"] == "Ativo"
    assert body["servicos"][0]["duracao"] == 40
    assert body["horarios_disponiveis"]

    resp_servicos = client.get("/public/servicos", params={"barbearia_id": barbearia.id})
    assert resp_servicos.status_code == 200
    assert any(item["id"] == servico.id for item in resp_servicos.json())

    resp_barbeiros = client.get("/public/barbeiros", params={"barbearia_id": barbearia.id})
    assert resp_barbeiros.status_code == 200
    assert len(resp_barbeiros.json()) == 1

    resp_horarios = client.get(
        "/public/horarios-disponiveis",
        params={
            "barbearia_id": barbearia.id,
            "barbeiro_id": barbeiro_ativo.id,
            "servico_id": servico.id,
            "data": data_futura.isoformat(),
        },
    )
    assert resp_horarios.status_code == 200
    assert "horarios_disponiveis" in resp_horarios.json()


def test_public_lookup_respeita_funcionamento_individual_do_barbeiro(client, db_session):
    horarios_barbearia = {
        "seg": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "08:00", "fim": "18:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }
    horarios_barbeiro = {
        "seg": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "ter": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "qua": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "qui": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "sex": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "sab": {"ativo": True, "inicio": "13:00", "fim": "18:00"},
        "dom": {"ativo": False, "inicio": "08:00", "fim": "18:00"},
    }

    barbearia = Barbearia(
        nome="Barbearia Tarde",
        slug="publica-tarde",
        endereco="Rua Publica",
        horarios_funcionamento=horarios_barbearia,
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(
        nome="Tarde",
        barbershop_id=barbearia.id,
        ativo=True,
        horarios_funcionamento=horarios_barbeiro,
    )
    servico = Servico(nome="Corte", duracao_minutos=40, preco=50.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    data_futura = (datetime.now() + timedelta(days=2)).date()
    resp = client.get(
        "/public/horarios-disponiveis",
        params={
            "barbearia_id": barbearia.id,
            "barbeiro_id": barbeiro.id,
            "servico_id": servico.id,
            "data": data_futura.isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["horarios_disponiveis"]
    assert all(int(item.split(":")[0]) >= 13 for item in body["horarios_disponiveis"])


def test_public_agendamento_cria_confirma_e_agenda_lembretes(monkeypatch, client, db_session):
    import app.services.public_booking_service as public_service

    enviados = {}

    def fake_enviar(barbearia, telefone, mensagem):
        enviados["barbearia"] = barbearia.nome
        enviados["telefone"] = telefone
        enviados["mensagem"] = mensagem
        return True

    monkeypatch.setattr(public_service, "enviar_mensagem_whatsapp", fake_enviar)

    barbearia = Barbearia(
        nome="Barbearia Agenda",
        slug="agenda-publica",
        endereco="Rua Agenda",
        mega_instance_key="inst-agenda",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(nome="Carlos", barbershop_id=barbearia.id, ativo=True)
    servico = Servico(nome="Barba", duracao_minutos=30, preco=35.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    data_hora = datetime.now() + timedelta(days=3)
    payload = {
        "barbearia_id": barbearia.id,
        "cliente_nome": "Vinicius",
        "cliente_telefone": "558298373869",
        "cliente_email": "vinicius@example.com",
        "barbeiro_id": barbeiro.id,
        "servico_id": servico.id,
        "data": data_hora.date().isoformat(),
        "hora_inicio": "10:00",
    }
    resp = client.post("/public/agendamentos", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "pendente"
    assert body["tenant_id"] == barbearia.id
    assert body["barbearia_id"] == barbearia.id
    assert body["cliente_email"] == "vinicius@example.com"
    assert body["confirmation_token"]
    assert body["lembretes_agendados"] == 2

    agendamento = db_session.query(Agendamento).filter(Agendamento.id == body["id"]).first()
    assert agendamento is not None
    assert agendamento.cliente_nome == "Vinicius"
    assert agendamento.cliente_telefone == "8298373869"
    assert agendamento.cliente_email == "vinicius@example.com"
    assert agendamento.confirmation_token == body["confirmation_token"]

    lembretes = (
        db_session.query(ReminderJob)
        .filter(ReminderJob.agendamento_id == agendamento.id)
        .order_by(ReminderJob.id.asc())
        .all()
    )
    assert len(lembretes) == 2
    assert {item.tipo for item in lembretes} == {"reminder_24h", "reminder_2h"}
    assert enviados["barbearia"] == "Barbearia Agenda"
