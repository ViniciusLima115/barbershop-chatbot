from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.cliente import Cliente
from app.models.reminder_job import ReminderJob
from app.models.servico import Servico
from app.services.barbershop_hours_service import is_within_working_hours


def _serializar_agendamento(agendamento: Agendamento):
    cliente_nome = agendamento.cliente_nome or (agendamento.cliente.nome if agendamento.cliente else "")
    cliente_telefone = agendamento.cliente_telefone or (agendamento.cliente.telefone if agendamento.cliente else "")
    return {
        "id": agendamento.id,
        "cliente_nome": cliente_nome,
        "telefone": cliente_telefone,
        "barbeiro_nome": agendamento.barbeiro.nome,
        "servico_nome": agendamento.servico.nome,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": agendamento.status,
    }


def _obter_barbearia(db: Session, tenant_id: int) -> Barbearia:
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise ValueError("Barbearia não encontrada")
    return barbearia


def _validar_funcionamento(barbearia: Barbearia, inicio: datetime, fim: datetime):
    if not is_within_working_hours(barbearia, inicio, fim):
        raise ValueError("Horário fora do funcionamento da barbearia")


def _validar_funcionamento_barbeiro(
    barbearia: Barbearia,
    barbeiro: Barbeiro,
    inicio: datetime,
    fim: datetime,
):
    if not is_within_working_hours(barbearia, inicio, fim, barbeiro=barbeiro):
        raise ValueError("Horário fora do funcionamento do barbeiro")


def criar_agendamento(db: Session, dados, tenant_id: int):
    barbearia = _obter_barbearia(db, tenant_id)
    servico_query = db.query(Servico).filter(
        Servico.id == dados.servico_id,
        Servico.barbearia_id == tenant_id,
    )
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(
        Barbeiro.id == dados.barbeiro_id,
        Barbeiro.barbershop_id == tenant_id,
    )
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")

    cliente_query = db.query(Cliente).filter(
        Cliente.telefone == dados.telefone,
        Cliente.barbearia_id == tenant_id,
    )
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
    _validar_funcionamento(barbearia, dados.data_hora_inicio, fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, dados.data_hora_inicio, fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.barbearia_id == tenant_id,
        Agendamento.data_hora_inicio < fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    novo = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        barbearia_id=tenant_id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        data=dados.data_hora_inicio.date(),
        hora_inicio=dados.data_hora_inicio.time().replace(microsecond=0),
        data_hora_inicio=dados.data_hora_inicio,
        data_hora_fim=fim,
        status=dados.status,
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return _serializar_agendamento(novo)


def listar_agendamentos(
    db: Session,
    tenant_id: int,
    *,
    data: date | None = None,
    barbeiro_id: int | None = None,
):
    query = db.query(Agendamento).filter(Agendamento.barbearia_id == tenant_id)
    if data:
        inicio = datetime.combine(data, time(0, 0))
        fim = inicio + timedelta(days=1)
        query = query.filter(
            Agendamento.data_hora_inicio >= inicio,
            Agendamento.data_hora_inicio < fim,
        )
    if barbeiro_id:
        query = query.filter(Agendamento.barbeiro_id == barbeiro_id)

    agendamentos = query.order_by(Agendamento.data_hora_inicio.asc()).all()
    return [_serializar_agendamento(ag) for ag in agendamentos]


def atualizar_status_agendamento(
    db: Session,
    agendamento_id: int,
    status: str,
    tenant_id: int,
):
    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.barbearia_id == tenant_id,
    )
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
    tenant_id: int,
):
    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.barbearia_id == tenant_id,
    )
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")
    barbearia = _obter_barbearia(db, tenant_id)

    servico = (
        db.query(Servico)
        .filter(
            Servico.id == agendamento.servico_id,
            Servico.barbearia_id == tenant_id,
        )
        .first()
    )
    if not servico:
        raise ValueError("Serviço não encontrado")

    nova_data_hora_fim = nova_data_hora_inicio + timedelta(minutes=servico.duracao_minutos)
    barbeiro = (
        db.query(Barbeiro)
        .filter(
            Barbeiro.id == agendamento.barbeiro_id,
            Barbeiro.barbershop_id == tenant_id,
        )
        .first()
    )
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")

    _validar_funcionamento(barbearia, nova_data_hora_inicio, nova_data_hora_fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, nova_data_hora_inicio, nova_data_hora_fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == agendamento.barbeiro_id,
        Agendamento.barbearia_id == tenant_id,
        Agendamento.data_hora_inicio < nova_data_hora_fim,
        Agendamento.data_hora_fim > nova_data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = nova_data_hora_fim
    agendamento.data = nova_data_hora_inicio.date()
    agendamento.hora_inicio = nova_data_hora_inicio.time().replace(microsecond=0)
    agendamento.status = "confirmado"
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def atualizar_agendamento(
    db: Session,
    agendamento_id: int,
    dados,
    tenant_id: int,
):
    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.barbearia_id == tenant_id,
    )
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")
    barbearia = _obter_barbearia(db, tenant_id)

    servico_query = db.query(Servico).filter(
        Servico.id == dados.servico_id,
        Servico.barbearia_id == tenant_id,
    )
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(
        Barbeiro.id == dados.barbeiro_id,
        Barbeiro.barbershop_id == tenant_id,
    )
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")

    novo_fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)
    _validar_funcionamento(barbearia, dados.data_hora_inicio, novo_fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, dados.data_hora_inicio, novo_fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.barbearia_id == tenant_id,
        Agendamento.data_hora_inicio < novo_fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        Agendamento.status.in_(["pendente", "confirmado"]),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.barbeiro_id = dados.barbeiro_id
    agendamento.servico_id = dados.servico_id
    agendamento.data_hora_inicio = dados.data_hora_inicio
    agendamento.data_hora_fim = novo_fim
    agendamento.data = dados.data_hora_inicio.date()
    agendamento.hora_inicio = dados.data_hora_inicio.time().replace(microsecond=0)
    agendamento.status = dados.status
    agendamento.barbearia_id = tenant_id
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def aplicar_patch_agendamento(
    db: Session,
    agendamento_id: int,
    dados,
    tenant_id: int,
):
    if dados.status and not (dados.barbeiro_id or dados.servico_id or dados.data_hora_inicio):
        return atualizar_status_agendamento(
            db,
            agendamento_id=agendamento_id,
            status=dados.status,
            tenant_id=tenant_id,
        )

    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.barbearia_id == tenant_id,
    )
    existente = query.first()
    if not existente:
        raise ValueError("Agendamento não encontrado")

    class _Payload:
        barbeiro_id = dados.barbeiro_id or existente.barbeiro_id
        servico_id = dados.servico_id or existente.servico_id
        data_hora_inicio = dados.data_hora_inicio or existente.data_hora_inicio
        status = dados.status or existente.status

    return atualizar_agendamento(
        db,
        agendamento_id=agendamento_id,
        dados=_Payload,
        tenant_id=tenant_id,
    )


def remover_agendamento(db: Session, agendamento_id: int, tenant_id: int):
    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.barbearia_id == tenant_id,
    )
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    # Remove lembretes pendentes/enviados vinculados antes do DELETE do agendamento
    # para evitar violação de chave estrangeira no Postgres/Neon.
    db.query(ReminderJob).filter(
        ReminderJob.agendamento_id == agendamento.id,
        ReminderJob.tenant_id == tenant_id,
    ).delete(synchronize_session=False)

    db.delete(agendamento)
    db.commit()
