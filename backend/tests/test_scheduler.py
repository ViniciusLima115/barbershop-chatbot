from datetime import datetime, timedelta

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.cliente import Cliente
from app.models.servico import Servico
from app.services.scheduler import processar_lembretes_email_pendentes


def test_scheduler_envia_lembrete_24h(monkeypatch, db_session):
    enviados: list[dict[str, str]] = []

    def fake_send(payload):
        enviados.append(payload)
        return True

    monkeypatch.setattr("app.services.scheduler.send_email_payload", fake_send)
    monkeypatch.setattr("app.services.scheduler.SessionLocal", lambda: db_session)

    barbearia = Barbearia(nome="Barbearia Scheduler", slug="scheduler", endereco="Rua Scheduler")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(nome="Mauro", barbershop_id=barbearia.id, ativo=True)
    servico = Servico(nome="Barba", duracao_minutos=30, preco=35.0, barbearia_id=barbearia.id)
    cliente = Cliente(nome="Cliente Scheduler", telefone="5582992222222", barbearia_id=barbearia.id)
    db_session.add_all([barbeiro, servico, cliente])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)
    db_session.refresh(cliente)

    inicio = datetime.now() + timedelta(hours=24)
    agendamento = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=barbeiro.id,
        servico_id=servico.id,
        barbearia_id=barbearia.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        cliente_email="scheduler@example.com",
        data=inicio.date(),
        hora_inicio=inicio.time().replace(second=0, microsecond=0),
        data_hora_inicio=inicio,
        data_hora_fim=inicio + timedelta(minutes=30),
        status="pendente",
    )
    db_session.add(agendamento)
    db_session.commit()
    db_session.refresh(agendamento)
    agendamento_id = agendamento.id

    resultado = processar_lembretes_email_pendentes()

    assert resultado["enviados"] == 1
    assert enviados
    assert enviados[0]["to_email"] == "scheduler@example.com"
    assert "Lembrete de agendamento" in enviados[0]["subject"]

    # scheduler calls db.close() which expunges objects — re-query instead of refresh
    agendamento_atualizado = db_session.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    assert agendamento_atualizado.lembrete_24h_enviado is True
    assert agendamento_atualizado.lembrete_2h_enviado is False
