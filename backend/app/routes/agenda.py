from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.routes.deps import tenant_id_from_header
from app.services.estabelecimento_hours_service import build_day_slots, get_working_window
from app.services.agenda_service import gerar_horarios_disponiveis
from app.services.payments.webhook_service import sync_pending_payment_statuses
from app.time_utils import utcnow_naive

router = APIRouter(prefix="/agenda")


@router.get("/horarios-disponiveis")
def horarios(
    barbeiro_id: int,
    servico_id: int,
    data: datetime,
    periodo: str | None = None,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    return gerar_horarios_disponiveis(
        db,
        barbeiro_id,
        servico_id,
        data,
        periodo=periodo,
        tenant_id=tenant_id,
    )


@router.get("/dia")
def agenda_dia(
    data: datetime,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    barbearia = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    barbeiros = (
        db.query(Barbeiro)
        .filter(Barbeiro.estabelecimento_id == tenant_id)
        .order_by(Barbeiro.id.asc())
        .all()
    )

    horarios_por_barbeiro = {
        barbeiro.id: [
            slot.strftime("%H:%M")
            for slot in build_day_slots(barbearia, data.date(), duration_minutes=1, barbeiro=barbeiro)
        ]
        for barbeiro in barbeiros
    }

    janelas = [
        get_working_window(barbearia, data.date(), barbeiro=barbeiro)
        for barbeiro in barbeiros
    ]
    intervalos_ativos = [janela for janela in janelas if janela]

    agendamentos: list[Agendamento] = []
    if intervalos_ativos:
        agora = utcnow_naive()
        inicio_dia = min(datetime.combine(data.date(), janela[0]) for janela in intervalos_ativos)
        fim_dia = max(datetime.combine(data.date(), janela[1]) for janela in intervalos_ativos)
        sync_pending_payment_statuses(db, establishment_id=tenant_id, limit=20)
        agendamentos = (
            db.query(Agendamento)
            .options(
                joinedload(Agendamento.cliente),
                joinedload(Agendamento.servico),
            )
            .filter(
                Agendamento.estabelecimento_id == tenant_id,
                Agendamento.data_hora_inicio >= inicio_dia,
                Agendamento.data_hora_inicio < fim_dia,
                or_(
                    Agendamento.status.in_(["pendente", "confirmado", "reagendamento_solicitado"]),
                    and_(
                        Agendamento.status == "pending_payment",
                        or_(
                            Agendamento.payment_hold_expires_at.is_(None),
                            Agendamento.payment_hold_expires_at > agora,
                        ),
                    ),
                ),
            )
            .all()
        )

    grade_times = {hora for itens in horarios_por_barbeiro.values() for hora in itens}
    booking_times = {ag.data_hora_inicio.strftime("%H:%M") for ag in agendamentos}
    horarios = sorted(grade_times | booking_times)

    por_barbeiro = {b.id: [] for b in barbeiros}
    pagamentos_por_agendamento: dict[int, Pagamento] = {}
    if agendamentos:
        pagamentos = (
            db.query(Pagamento)
            .filter(Pagamento.agendamento_id.in_([ag.id for ag in agendamentos]))
            .all()
        )
        pagamentos_por_agendamento = {p.agendamento_id: p for p in pagamentos}

    for ag in agendamentos:
        pagamento = pagamentos_por_agendamento.get(ag.id)
        por_barbeiro.setdefault(ag.barbeiro_id, []).append(
            {
                "hora": ag.data_hora_inicio.strftime("%H:%M"),
                "cliente": ag.cliente.nome if ag.cliente else "Cliente",
                "servico": ag.servico.nome if ag.servico else "Servico",
                "telefone": ag.cliente.telefone if ag.cliente else None,
                "status": ag.status,
                "payment_status": ag.payment_status,
                "payment_amount": ag.payment_amount_snapshot,
                "payment_method": pagamento.payment_method if pagamento else None,
                "inicio": ag.data_hora_inicio.isoformat(),
                "fim": ag.data_hora_fim.isoformat(),
            }
        )

    return {
        "data": data.date().isoformat(),
        "horarios": horarios,
        "barbeiros": [
            {
                "id": b.id,
                "nome": b.nome,
                "horarios": horarios_por_barbeiro.get(b.id, []),
                "agendamentos": por_barbeiro.get(b.id, []),
            }
            for b in barbeiros
        ],
    }
