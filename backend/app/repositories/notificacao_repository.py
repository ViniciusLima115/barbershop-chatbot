from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.notificacao import Notificacao


def criar(
    db: Session,
    *,
    estabelecimento_id: int,
    tipo: str,
    titulo: str,
    corpo: str | None = None,
    agendamento_id: int | None = None,
) -> Notificacao:
    notif = Notificacao(
        estabelecimento_id=estabelecimento_id,
        agendamento_id=agendamento_id,
        tipo=tipo,
        titulo=titulo,
        corpo=corpo,
    )
    db.add(notif)
    db.flush()  # obtém o id sem commit
    return notif


def listar(
    db: Session,
    *,
    estabelecimento_id: int,
    apenas_nao_lidas: bool = False,
    limite: int = 30,
) -> list[Notificacao]:
    q = db.query(Notificacao).filter(Notificacao.estabelecimento_id == estabelecimento_id)
    if apenas_nao_lidas:
        q = q.filter(Notificacao.lida.is_(False))
    return q.order_by(Notificacao.criada_em.desc()).limit(limite).all()


def marcar_lida(db: Session, *, notificacao_id: int, estabelecimento_id: int) -> Notificacao | None:
    notif = (
        db.query(Notificacao)
        .filter(Notificacao.id == notificacao_id, Notificacao.estabelecimento_id == estabelecimento_id)
        .first()
    )
    if notif and not notif.lida:
        notif.lida = True
        notif.lida_em = datetime.now(timezone.utc)
        db.flush()
    return notif


def marcar_todas_lidas(db: Session, *, estabelecimento_id: int) -> int:
    """Marca todas as notificações não lidas de um tenant como lidas.

    Nota: usa synchronize_session=False para performance. Instâncias de Notificacao
    já carregadas na sessão ficam com dados stale após esta chamada — faça re-query
    se precisar dos objetos atualizados.
    """
    count = (
        db.query(Notificacao)
        .filter(Notificacao.estabelecimento_id == estabelecimento_id, Notificacao.lida.is_(False))
        .update({"lida": True, "lida_em": datetime.now(timezone.utc)}, synchronize_session=False)
    )
    db.flush()
    return count


def existe_pendente_confirmacao(db: Session, *, agendamento_id: int) -> bool:
    """Verifica se já existe notificação pendente_confirmacao para este agendamento (idempotência)."""
    return (
        db.query(Notificacao.id)
        .filter(
            Notificacao.agendamento_id == agendamento_id,
            Notificacao.tipo == "pendente_confirmacao",
        )
        .first()
    ) is not None


def marcar_lida_por_agendamento_e_tipo(
    db: Session, *, agendamento_id: int, tipo: str
) -> None:
    """Marca como lida a notificação de um agendamento específico (ex: após confirmar presença)."""
    db.query(Notificacao).filter(
        Notificacao.agendamento_id == agendamento_id,
        Notificacao.tipo == tipo,
        Notificacao.lida.is_(False),
    ).update({"lida": True, "lida_em": datetime.now(timezone.utc)}, synchronize_session=False)
    db.flush()
