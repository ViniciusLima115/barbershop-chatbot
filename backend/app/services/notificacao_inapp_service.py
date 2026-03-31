import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.agendamento import Agendamento
from app.repositories import notificacao_repository as repo

logger = logging.getLogger(__name__)


def _corpo_agendamento(agendamento: Agendamento) -> str:
    cliente = agendamento.cliente_nome or "Cliente"
    servico = agendamento.servico.nome if agendamento.servico else "Serviço"
    data_str = agendamento.data_hora_inicio.strftime("%d/%m %H:%M") if agendamento.data_hora_inicio else ""
    return f"{cliente} · {servico} · {data_str}"


def criar_notificacao_novo_agendamento(db: Session, agendamento: Agendamento) -> None:
    """Chamado com db próprio ao criar um agendamento (via wrapper de background task)."""
    try:
        repo.criar(
            db,
            estabelecimento_id=agendamento.estabelecimento_id,
            agendamento_id=agendamento.id,
            tipo="novo_agendamento",
            titulo="Novo agendamento",
            corpo=_corpo_agendamento(agendamento),
        )
        db.commit()
    except Exception:
        logger.exception("Erro ao criar notificacao novo_agendamento para agendamento %s", agendamento.id)
        db.rollback()


def criar_notificacao_confirmado(db: Session, agendamento: Agendamento) -> None:
    """Chamado com db próprio quando o cliente confirma pelo link de email."""
    try:
        repo.criar(
            db,
            estabelecimento_id=agendamento.estabelecimento_id,
            agendamento_id=agendamento.id,
            tipo="agendamento_confirmado",
            titulo="Agendamento confirmado",
            corpo=_corpo_agendamento(agendamento),
        )
        db.commit()
    except Exception:
        logger.exception("Erro ao criar notificacao agendamento_confirmado para agendamento %s", agendamento.id)
        db.rollback()


# ── Wrappers para BackgroundTasks ────────────────────────────────────────────
# Criam sua própria sessão para não depender da sessão da requisição HTTP.

def task_notificacao_novo_agendamento(agendamento_id: int) -> None:
    """Versão para BackgroundTasks — cria sessão própria."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ag = (
            db.query(Agendamento)
            .options(joinedload(Agendamento.servico))
            .filter(Agendamento.id == agendamento_id)
            .first()
        )
        if ag:
            criar_notificacao_novo_agendamento(db, ag)
    finally:
        db.close()


def task_notificacao_confirmado(agendamento_id: int) -> None:
    """Versão para BackgroundTasks — cria sessão própria."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ag = (
            db.query(Agendamento)
            .options(joinedload(Agendamento.servico))
            .filter(Agendamento.id == agendamento_id)
            .first()
        )
        if ag:
            criar_notificacao_confirmado(db, ag)
    finally:
        db.close()


def processar_pendentes_confirmacao(db: Session) -> int:
    """
    Chamado pelo APScheduler a cada minuto.
    Cria notificações pendente_confirmacao para agendamentos cujo horário já passou
    e que ainda não têm marcação de presença. Idempotente.
    """
    agora = datetime.now()
    try:
        agendamentos = (
            db.query(Agendamento)
            .options(
                joinedload(Agendamento.servico),
                joinedload(Agendamento.cliente),
                joinedload(Agendamento.barbeiro),
            )
            .filter(
                Agendamento.data_hora_fim < agora,
                Agendamento.status.in_(["pendente", "confirmado"]),
            )
            .all()
        )

        criados = 0
        for ag in agendamentos:
            if repo.existe_pendente_confirmacao(db, agendamento_id=ag.id):
                continue

            repo.criar(
                db,
                estabelecimento_id=ag.estabelecimento_id,
                agendamento_id=ag.id,
                tipo="pendente_confirmacao",
                titulo="Confirmar presença",
                corpo=_corpo_agendamento(ag),
            )
            criados += 1

        if criados:
            db.commit()
            logger.info("Criadas %s notificações pendente_confirmacao.", criados)

        return criados
    except Exception:
        logger.exception("Erro ao processar pendentes de confirmacao.")
        db.rollback()
        return 0
