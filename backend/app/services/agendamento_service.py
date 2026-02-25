from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.servico import Servico


def _serializar_agendamento(agendamento: Agendamento):
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


def criar_agendamento(db: Session, dados, tenant_id: int | None = None):
    servico_query = db.query(Servico).filter(Servico.id == dados.servico_id)
    if tenant_id is not None:
        servico_query = servico_query.filter(Servico.barbearia_id == tenant_id)
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(Barbeiro.id == dados.barbeiro_id)
    if tenant_id is not None:
        barbeiro_query = barbeiro_query.filter(Barbeiro.barbershop_id == tenant_id)
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")

    cliente_query = db.query(Cliente).filter(Cliente.telefone == dados.telefone)
    if tenant_id is not None:
        cliente_query = cliente_query.filter(Cliente.barbearia_id == tenant_id)
    cliente = cliente_query.first()
    if not cliente:
        cliente = Cliente(
            nome=dados.nome_cliente,
            telefone=dados.telefone,
            barbearia_id=tenant_id,
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.data_hora_inicio < fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    if tenant_id is not None:
        conflito_query = conflito_query.filter(Agendamento.barbearia_id == tenant_id)
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    novo = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        barbearia_id=tenant_id if tenant_id is not None else getattr(barbeiro, "barbershop_id", None),
        data_hora_inicio=dados.data_hora_inicio,
        data_hora_fim=fim,
        status=dados.status,
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return _serializar_agendamento(novo)


def listar_agendamentos(db: Session, tenant_id: int | None = None):
    query = db.query(Agendamento)
    if tenant_id is not None:
        query = query.filter(Agendamento.barbearia_id == tenant_id)
    agendamentos = query.order_by(Agendamento.data_hora_inicio.asc()).all()
    return [_serializar_agendamento(ag) for ag in agendamentos]


def atualizar_status_agendamento(
    db: Session,
    agendamento_id: int,
    status: str,
    tenant_id: int | None = None,
):
    query = db.query(Agendamento).filter(Agendamento.id == agendamento_id)
    if tenant_id is not None:
        query = query.filter(Agendamento.barbearia_id == tenant_id)
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    agendamento.status = status
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def remarcar_agendamento(
    db: Session,
    agendamento_id: int,
    nova_data_hora_inicio,
    tenant_id: int | None = None,
):
    query = db.query(Agendamento).filter(Agendamento.id == agendamento_id)
    if tenant_id is not None:
        query = query.filter(Agendamento.barbearia_id == tenant_id)
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    servico = db.query(Servico).filter(Servico.id == agendamento.servico_id).first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    nova_data_hora_fim = nova_data_hora_inicio + timedelta(minutes=servico.duracao_minutos)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == agendamento.barbeiro_id,
        Agendamento.data_hora_inicio < nova_data_hora_fim,
        Agendamento.data_hora_fim > nova_data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    if tenant_id is not None:
        conflito_query = conflito_query.filter(Agendamento.barbearia_id == tenant_id)
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = nova_data_hora_fim
    agendamento.status = "confirmado"
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def atualizar_agendamento(
    db: Session,
    agendamento_id: int,
    dados,
    tenant_id: int | None = None,
):
    query = db.query(Agendamento).filter(Agendamento.id == agendamento_id)
    if tenant_id is not None:
        query = query.filter(Agendamento.barbearia_id == tenant_id)
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    servico_query = db.query(Servico).filter(Servico.id == dados.servico_id)
    if tenant_id is not None:
        servico_query = servico_query.filter(Servico.barbearia_id == tenant_id)
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(Barbeiro.id == dados.barbeiro_id)
    if tenant_id is not None:
        barbeiro_query = barbeiro_query.filter(Barbeiro.barbershop_id == tenant_id)
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")

    novo_fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.data_hora_inicio < novo_fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    if tenant_id is not None:
        conflito_query = conflito_query.filter(Agendamento.barbearia_id == tenant_id)
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.barbeiro_id = dados.barbeiro_id
    agendamento.servico_id = dados.servico_id
    agendamento.data_hora_inicio = dados.data_hora_inicio
    agendamento.data_hora_fim = novo_fim
    agendamento.status = dados.status
    if tenant_id is not None:
        agendamento.barbearia_id = tenant_id
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def remover_agendamento(db: Session, agendamento_id: int, tenant_id: int | None = None):
    query = db.query(Agendamento).filter(Agendamento.id == agendamento_id)
    if tenant_id is not None:
        query = query.filter(Agendamento.barbearia_id == tenant_id)
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    db.delete(agendamento)
    db.commit()
