from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.models.servico import Servico


def criar_agendamento(db: Session, dados):
    servico = db.query(Servico).filter(Servico.id == dados.servico_id).first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    cliente = db.query(Cliente).filter(Cliente.telefone == dados.telefone).first()

    if not cliente:
        cliente = Cliente(nome=dados.nome_cliente, telefone=dados.telefone)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)

    conflito = (
        db.query(Agendamento)
        .filter(
            Agendamento.barbeiro_id == dados.barbeiro_id,
            Agendamento.data_hora_inicio < fim,
            Agendamento.data_hora_fim > dados.data_hora_inicio,
        )
        .first()
    )

    if conflito:
        raise ValueError("Horário indisponível")

    novo = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        data_hora_inicio=dados.data_hora_inicio,
        data_hora_fim=fim,
        status=dados.status,
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "id": novo.id,
        "cliente_nome": cliente.nome,
        "telefone": cliente.telefone,
        "barbeiro_nome": novo.barbeiro.nome,
        "servico_nome": servico.nome,
        "data_hora_inicio": novo.data_hora_inicio,
        "data_hora_fim": novo.data_hora_fim,
        "status": novo.status,
    }


def atualizar_status_agendamento(db: Session, agendamento_id: int, status: str):
    agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    agendamento.status = status
    db.commit()
    db.refresh(agendamento)

    return {
        "id": agendamento.id,
        "cliente_nome": agendamento.cliente.nome,
        "telefone": agendamento.cliente.telefone,
        "barbeiro_nome": agendamento.barbeiro.nome,
        "servico_nome": agendamento.servico.nome,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": agendamento.status,
    }
