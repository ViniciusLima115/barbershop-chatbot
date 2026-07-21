import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.estabelecimento import Estabelecimento
from app.models.cliente import Cliente
from app.models.reminder_job import ReminderJob
from app.models.servico import Servico
from app.services.estabelecimento_hours_service import is_within_working_hours
from app.services.email_service import (
    AgendamentoEmailContext,
    build_confirmation_email,
    build_status_email,
)
from app.time_utils import utcnow_naive


logger = logging.getLogger(__name__)
MONEY_QUANTUM = Decimal("0.01")

STATUS_ATIVOS = ["pending_payment", "pendente", "confirmado", "reagendamento_solicitado"]
STATUS_VALIDOS = {"pending_payment", "payment_review_required", "pendente", "confirmado", "cancelado", "failed", "reagendamento_solicitado", "compareceu", "no_show", "expired"}


def _normalizar_email(email: str | None) -> str | None:
    valor = (email or "").strip().lower()
    return valor or None


def _normalizar_status_saida(status: str | None) -> str:
    valor = (status or "").strip().lower()
    if valor in STATUS_VALIDOS:
        return valor
    return "pendente"


def _filtro_status_ativos(agora: datetime):
    return or_(
        Agendamento.status.in_(["pendente", "confirmado", "reagendamento_solicitado"]),
        and_(
            Agendamento.status == "pending_payment",
            or_(
                Agendamento.payment_hold_expires_at.is_(None),
                Agendamento.payment_hold_expires_at > agora,
            ),
        ),
    )


def _serializar_agendamento(agendamento: Agendamento):
    cliente_nome = agendamento.cliente_nome or (agendamento.cliente.nome if agendamento.cliente else "")
    cliente_telefone = agendamento.cliente_telefone or (agendamento.cliente.telefone if agendamento.cliente else "")
    return {
        "id": agendamento.id,
        "cliente_nome": cliente_nome,
        "telefone": cliente_telefone,
        "cliente_email": _normalizar_email(agendamento.cliente_email),
        "barbeiro_nome": agendamento.barbeiro.nome,
        "servico_nome": agendamento.servico.nome,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": _normalizar_status_saida(agendamento.status),
        "payment_status": (agendamento.payment_status or "not_required"),
        "payment_required": bool(agendamento.payment_required_snapshot),
        "payment_amount": agendamento.payment_amount_snapshot,
        "payment_type": agendamento.payment_type_snapshot,
    }


def _serializar_dados_token(agendamento: Agendamento):
    return {
        "id": agendamento.id,
        "estabelecimento_id": agendamento.estabelecimento_id,
        "slug": agendamento.estabelecimento.slug if agendamento.estabelecimento else None,
        "confirmation_token": agendamento.confirmation_token,
        "cliente_nome": agendamento.cliente_nome or "",
        "cliente_email": _normalizar_email(agendamento.cliente_email),
        "barbeiro_id": agendamento.barbeiro_id,
        "barbeiro_nome": agendamento.barbeiro.nome,
        "servico_id": agendamento.servico_id,
        "servico_nome": agendamento.servico.nome,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": _normalizar_status_saida(agendamento.status),
    }


def _obter_barbearia(db: Session, tenant_id: int) -> Estabelecimento:
    barbearia = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not barbearia:
        raise ValueError("Estabelecimento não encontrado")
    return barbearia


def _validar_funcionamento(barbearia: Estabelecimento, inicio: datetime, fim: datetime):
    if not is_within_working_hours(barbearia, inicio, fim):
        raise ValueError("Horário fora do funcionamento do estabelecimento")


def _validar_funcionamento_barbeiro(
    barbearia: Estabelecimento,
    barbeiro: Barbeiro,
    inicio: datetime,
    fim: datetime,
):
    if not is_within_working_hours(barbearia, inicio, fim, barbeiro=barbeiro):
        raise ValueError("Horário fora da disponibilidade do profissional")


def _obter_agendamento_por_token(
    db: Session,
    token: str,
    *,
    for_update: bool = False,
) -> Agendamento | None:
    query = db.query(Agendamento).filter(Agendamento.confirmation_token == token)
    if for_update:
        query = query.with_for_update()
    agendamento = query.first()
    if not agendamento:
        return None
    expires_at = agendamento.confirmation_token_expires_at or (
        agendamento.data_hora_fim + timedelta(days=1)
    )
    if expires_at < utcnow_naive():
        return None
    return agendamento


def _resetar_flags_lembrete(agendamento: Agendamento):
    agendamento.lembrete_24h_enviado = False
    agendamento.lembrete_2h_enviado = False


def _validar_confirmacao_com_pagamento(agendamento: Agendamento, status_destino: str) -> None:
    if status_destino != "confirmado":
        return
    if not bool(agendamento.payment_required_snapshot):
        return
    if (agendamento.payment_status or "").lower() == "approved":
        return
    raise ValueError("Pagamento nao aprovado. O agendamento nao pode ser confirmado por este fluxo.")


def criar_agendamento(db: Session, dados, tenant_id: int):
    barbearia = _obter_barbearia(db, tenant_id)
    servico_query = db.query(Servico).filter(
        Servico.id == dados.servico_id,
        Servico.estabelecimento_id == tenant_id,
    )
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(
        Barbeiro.id == dados.barbeiro_id,
        Barbeiro.estabelecimento_id == tenant_id,
    )
    barbeiro = barbeiro_query.with_for_update().first()
    if not barbeiro:
        raise ValueError("Profissional não encontrado")

    cliente_query = db.query(Cliente).filter(
        Cliente.telefone == dados.telefone,
        Cliente.estabelecimento_id == tenant_id,
    )
    cliente = cliente_query.first()
    if not cliente:
        cliente = Cliente(
            nome=dados.nome_cliente,
            telefone=dados.telefone,
            estabelecimento_id=tenant_id,
        )
        db.add(cliente)
        db.flush()

    fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)
    _validar_funcionamento(barbearia, dados.data_hora_inicio, fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, dados.data_hora_inicio, fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.estabelecimento_id == tenant_id,
        Agendamento.data_hora_inicio < fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        _filtro_status_ativos(utcnow_naive()),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    novo = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=dados.barbeiro_id,
        servico_id=dados.servico_id,
        estabelecimento_id=tenant_id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        cliente_email=_normalizar_email(getattr(dados, "cliente_email", None)),
        data=dados.data_hora_inicio.date(),
        hora_inicio=dados.data_hora_inicio.time().replace(microsecond=0),
        data_hora_inicio=dados.data_hora_inicio,
        data_hora_fim=fim,
        confirmation_token_expires_at=fim + timedelta(days=1),
        status="pending_payment" if bool(getattr(servico, "pagamento_adiantado_obrigatorio", False)) else dados.status,
        payment_required_snapshot=bool(getattr(servico, "pagamento_adiantado_obrigatorio", False)),
        payment_type_snapshot=(getattr(servico, "advance_payment_type", None) or None),
        payment_amount_snapshot=(
            Decimal(str(getattr(servico, "advance_payment_amount", 0) or 0)).quantize(
                MONEY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            if (getattr(servico, "advance_payment_type", "") or "").strip().lower() == "signal"
            else Decimal(str(servico.preco or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        ) if bool(getattr(servico, "pagamento_adiantado_obrigatorio", False)) else None,
        payment_status="pending" if bool(getattr(servico, "pagamento_adiantado_obrigatorio", False)) else "not_required",
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
    query = db.query(Agendamento).filter(Agendamento.estabelecimento_id == tenant_id)
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
        Agendamento.estabelecimento_id == tenant_id,
    )
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    _validar_confirmacao_com_pagamento(agendamento, status)
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
        Agendamento.estabelecimento_id == tenant_id,
    )
    agendamento = query.with_for_update().first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")
    barbearia = _obter_barbearia(db, tenant_id)

    servico = (
        db.query(Servico)
        .filter(
            Servico.id == agendamento.servico_id,
            Servico.estabelecimento_id == tenant_id,
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
            Barbeiro.estabelecimento_id == tenant_id,
        )
        .with_for_update()
        .first()
    )
    if not barbeiro:
        raise ValueError("Profissional não encontrado")

    _validar_funcionamento(barbearia, nova_data_hora_inicio, nova_data_hora_fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, nova_data_hora_inicio, nova_data_hora_fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == agendamento.barbeiro_id,
        Agendamento.estabelecimento_id == tenant_id,
        Agendamento.data_hora_inicio < nova_data_hora_fim,
        Agendamento.data_hora_fim > nova_data_hora_inicio,
        _filtro_status_ativos(utcnow_naive()),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = nova_data_hora_fim
    agendamento.data = nova_data_hora_inicio.date()
    agendamento.hora_inicio = nova_data_hora_inicio.time().replace(microsecond=0)
    agendamento.confirmation_token_expires_at = nova_data_hora_fim + timedelta(days=1)
    agendamento.status = "confirmado"
    _resetar_flags_lembrete(agendamento)
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
        Agendamento.estabelecimento_id == tenant_id,
    )
    agendamento = query.with_for_update().first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")
    barbearia = _obter_barbearia(db, tenant_id)

    servico_query = db.query(Servico).filter(
        Servico.id == dados.servico_id,
        Servico.estabelecimento_id == tenant_id,
    )
    servico = servico_query.first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro_query = db.query(Barbeiro).filter(
        Barbeiro.id == dados.barbeiro_id,
        Barbeiro.estabelecimento_id == tenant_id,
    )
    barbeiro = barbeiro_query.with_for_update().first()
    if not barbeiro:
        raise ValueError("Profissional não encontrado")

    novo_fim = dados.data_hora_inicio + timedelta(minutes=servico.duracao_minutos)
    _validar_funcionamento(barbearia, dados.data_hora_inicio, novo_fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, dados.data_hora_inicio, novo_fim)

    conflito_query = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == dados.barbeiro_id,
        Agendamento.estabelecimento_id == tenant_id,
        Agendamento.data_hora_inicio < novo_fim,
        Agendamento.data_hora_fim > dados.data_hora_inicio,
        _filtro_status_ativos(utcnow_naive()),
    )
    conflito = conflito_query.first()

    if conflito:
        raise ValueError("Horário indisponível")

    houve_remarcacao = agendamento.data_hora_inicio != dados.data_hora_inicio
    _validar_confirmacao_com_pagamento(agendamento, dados.status)
    agendamento.barbeiro_id = dados.barbeiro_id
    agendamento.servico_id = dados.servico_id
    agendamento.data_hora_inicio = dados.data_hora_inicio
    agendamento.data_hora_fim = novo_fim
    agendamento.data = dados.data_hora_inicio.date()
    agendamento.hora_inicio = dados.data_hora_inicio.time().replace(microsecond=0)
    agendamento.confirmation_token_expires_at = novo_fim + timedelta(days=1)
    agendamento.status = dados.status
    agendamento.cliente_email = _normalizar_email(getattr(dados, "cliente_email", agendamento.cliente_email))
    agendamento.estabelecimento_id = tenant_id
    if houve_remarcacao:
        _resetar_flags_lembrete(agendamento)
    db.commit()
    db.refresh(agendamento)

    return _serializar_agendamento(agendamento)


def aplicar_patch_agendamento(
    db: Session,
    agendamento_id: int,
    dados,
    tenant_id: int,
):
    if dados.status and not (dados.barbeiro_id or dados.servico_id or dados.data_hora_inicio or dados.cliente_email):
        return atualizar_status_agendamento(
            db,
            agendamento_id=agendamento_id,
            status=dados.status,
            tenant_id=tenant_id,
        )

    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.estabelecimento_id == tenant_id,
    )
    existente = query.first()
    if not existente:
        raise ValueError("Agendamento não encontrado")

    class _Payload:
        barbeiro_id = dados.barbeiro_id or existente.barbeiro_id
        servico_id = dados.servico_id or existente.servico_id
        data_hora_inicio = dados.data_hora_inicio or existente.data_hora_inicio
        status = dados.status or existente.status
        cliente_email = dados.cliente_email if dados.cliente_email is not None else existente.cliente_email

    return atualizar_agendamento(
        db,
        agendamento_id=agendamento_id,
        dados=_Payload,
        tenant_id=tenant_id,
    )


def remover_agendamento(db: Session, agendamento_id: int, tenant_id: int):
    query = db.query(Agendamento).filter(
        Agendamento.id == agendamento_id,
        Agendamento.estabelecimento_id == tenant_id,
    )
    agendamento = query.first()
    if not agendamento:
        raise ValueError("Agendamento não encontrado")

    db.query(ReminderJob).filter(
        ReminderJob.agendamento_id == agendamento.id,
        ReminderJob.tenant_id == tenant_id,
    ).delete(synchronize_session=False)

    db.delete(agendamento)
    db.commit()


def obter_contexto_email_agendamento(
    db: Session,
    *,
    agendamento_id: int | None = None,
    token: str | None = None,
) -> AgendamentoEmailContext | None:
    query = db.query(Agendamento)
    if agendamento_id is not None:
        query = query.filter(Agendamento.id == agendamento_id)
    elif token:
        query = query.filter(Agendamento.confirmation_token == token)
    else:
        return None

    agendamento = query.first()
    if not agendamento or not agendamento.cliente_email:
        return None

    barbearia = agendamento.estabelecimento or db.query(Estabelecimento).filter(Estabelecimento.id == agendamento.estabelecimento_id).first()
    barbeiro = agendamento.barbeiro or db.query(Barbeiro).filter(Barbeiro.id == agendamento.barbeiro_id).first()
    servico = agendamento.servico or db.query(Servico).filter(Servico.id == agendamento.servico_id).first()
    if not barbearia or not barbeiro or not servico:
        return None

    return AgendamentoEmailContext(
        agendamento_id=agendamento.id,
        confirmation_token=agendamento.confirmation_token,
        cliente_nome=agendamento.cliente_nome or "",
        cliente_email=agendamento.cliente_email,
        barbearia_nome=barbearia.nome,
        estabelecimento_id=barbearia.id,
        slug=barbearia.slug,
        servico_nome=servico.nome,
        barbeiro_nome=barbeiro.nome,
        data_hora_inicio=agendamento.data_hora_inicio,
    )


def obter_payload_email_confirmacao(db: Session, *, agendamento_id: int) -> dict[str, str] | None:
    contexto = obter_contexto_email_agendamento(db, agendamento_id=agendamento_id)
    if not contexto:
        return None
    return build_confirmation_email(contexto)


def obter_payload_email_status(
    db: Session,
    *,
    token: str,
    tipo: str,
) -> dict[str, str] | None:
    contexto = obter_contexto_email_agendamento(db, token=token)
    if not contexto:
        return None
    return build_status_email(contexto, tipo=tipo)


def obter_dados_agendamento_por_token(db: Session, token: str):
    agendamento = _obter_agendamento_por_token(db, token)
    if not agendamento:
        raise ValueError("Token de agendamento inválido")
    return _serializar_dados_token(agendamento)


def atualizar_status_agendamento_por_token(db: Session, token: str, status: str):
    agendamento = _obter_agendamento_por_token(db, token, for_update=True)
    if not agendamento:
        raise ValueError("Token de agendamento inválido")

    if agendamento.status == status:
        return _serializar_dados_token(agendamento)

    if agendamento.status == "cancelado" and status != "cancelado":
        raise ValueError("Agendamento cancelado não pode ser alterado por este link")

    _validar_confirmacao_com_pagamento(agendamento, status)
    agendamento.status = status
    if status == "reagendamento_solicitado":
        _resetar_flags_lembrete(agendamento)
    db.commit()
    db.refresh(agendamento)

    logger.info(
        "Status do agendamento %s atualizado para %s via token.",
        agendamento.id,
        status,
    )
    return _serializar_dados_token(agendamento)


def remarcar_agendamento_por_token(db: Session, token: str, nova_data_hora_inicio: datetime):
    agendamento = _obter_agendamento_por_token(db, token, for_update=True)
    if not agendamento:
        raise ValueError("Token de agendamento inválido")

    if agendamento.status == "cancelado":
        raise ValueError("Agendamento cancelado não pode ser reagendado por este link")

    tenant_id = agendamento.estabelecimento_id
    barbearia = _obter_barbearia(db, tenant_id)

    servico = db.query(Servico).filter(
        Servico.id == agendamento.servico_id,
        Servico.estabelecimento_id == tenant_id,
    ).first()
    if not servico:
        raise ValueError("Serviço não encontrado")

    barbeiro = db.query(Barbeiro).filter(
        Barbeiro.id == agendamento.barbeiro_id,
        Barbeiro.estabelecimento_id == tenant_id,
    ).with_for_update().first()
    if not barbeiro:
        raise ValueError("Profissional não encontrado")

    nova_fim = nova_data_hora_inicio + timedelta(minutes=servico.duracao_minutos)
    _validar_funcionamento(barbearia, nova_data_hora_inicio, nova_fim)
    _validar_funcionamento_barbeiro(barbearia, barbeiro, nova_data_hora_inicio, nova_fim)

    conflito = db.query(Agendamento).filter(
        Agendamento.id != agendamento.id,
        Agendamento.barbeiro_id == agendamento.barbeiro_id,
        Agendamento.estabelecimento_id == tenant_id,
        Agendamento.data_hora_inicio < nova_fim,
        Agendamento.data_hora_fim > nova_data_hora_inicio,
        _filtro_status_ativos(utcnow_naive()),
    ).first()
    if conflito:
        raise ValueError("Horário indisponível")

    agendamento.data_hora_inicio = nova_data_hora_inicio
    agendamento.data_hora_fim = nova_fim
    agendamento.data = nova_data_hora_inicio.date()
    agendamento.hora_inicio = nova_data_hora_inicio.time().replace(microsecond=0)
    agendamento.confirmation_token_expires_at = nova_fim + timedelta(days=1)
    agendamento.status = "confirmado"
    _resetar_flags_lembrete(agendamento)
    db.commit()
    db.refresh(agendamento)

    logger.info(
        "Agendamento %s reagendado para %s via token.",
        agendamento.id,
        nova_data_hora_inicio,
    )
    return _serializar_dados_token(agendamento)


