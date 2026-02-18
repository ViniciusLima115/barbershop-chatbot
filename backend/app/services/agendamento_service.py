from datetime import timedelta
from sqlalchemy.orm import Session
from app.models.agendamento import Agendamento
from app.models.servico import Servico
from app.models.cliente import Cliente


def criar_agendamento(db: Session, dados):
    servico = db.query(Servico).filter(
        Servico.id == dados.servico_id
    ).first()

    cliente = db.query(Cliente).filter(
        Cliente.telefone == dados.telefone
    ).first()

    if not cliente:
        cliente = Cliente(
            nome=dados.nome_cliente,
            telefone=dados.telefone
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    fim = dados.data_hora_inicio + timedelta(
        minutes=servico.duracao_minutos
    )

    conflito = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.data_hora_inicio < fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio
    ).first()

    if conflito:
        raise Exception("Horário indisponível")

    novo = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        data_hora_inicio=dados.data_hora_inicio,
        data_hora_fim=fim
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
    "status": novo.status
}