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
    assert body["slug"] == "publica"
    assert len(body["barbeiros"]) == 1
    assert body["barbeiros"][0]["nome"] == "Ativo"
    assert body["servicos"][0]["duracao"] == 40
    assert body["horarios_disponiveis"]


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
        "slug": "agenda-publica",
        "cliente_nome": "Vinicius",
        "cliente_telefone": "558298373869",
        "barbeiro_id": barbeiro.id,
        "servico_id": servico.id,
        "data": data_hora.date().isoformat(),
        "hora_inicio": data_hora.replace(minute=30, second=0, microsecond=0).strftime("%H:%M"),
    }
    resp = client.post("/public/agendamentos", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "confirmado"
    assert body["tenant_id"] == barbearia.id
    assert body["lembretes_agendados"] == 2

    agendamento = db_session.query(Agendamento).filter(Agendamento.id == body["id"]).first()
    assert agendamento is not None
    assert agendamento.cliente_nome == "Vinicius"
    assert agendamento.cliente_telefone == "558298373869"

    lembretes = (
        db_session.query(ReminderJob)
        .filter(ReminderJob.agendamento_id == agendamento.id)
        .order_by(ReminderJob.id.asc())
        .all()
    )
    assert len(lembretes) == 2
    assert {item.tipo for item in lembretes} == {"reminder_24h", "reminder_2h"}
    assert enviados["barbearia"] == "Barbearia Agenda"
