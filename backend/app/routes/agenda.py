from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS
from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.routes.deps import tenant_id_from_header
from app.services.agenda_service import gerar_horarios_disponiveis

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
    inicio_dia = datetime.combine(data.date(), time(HORARIO_ABERTURA, 0))
    fim_dia = datetime.combine(data.date(), time(HORARIO_FECHAMENTO, 0))

    horarios = []
    atual = inicio_dia
    while atual < fim_dia:
        horarios.append(atual.strftime("%H:%M"))
        atual += timedelta(minutes=INTERVALO_MINUTOS)

    barbeiros = (
        db.query(Barbeiro)
        .filter(Barbeiro.barbershop_id == tenant_id)
        .order_by(Barbeiro.id.asc())
        .all()
    )

    agendamentos = (
        db.query(Agendamento)
        .options(
            joinedload(Agendamento.cliente),
            joinedload(Agendamento.servico),
        )
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.data_hora_inicio >= inicio_dia,
            Agendamento.data_hora_inicio < fim_dia,
        )
        .all()
    )

    por_barbeiro = {b.id: [] for b in barbeiros}

    for ag in agendamentos:
        por_barbeiro.setdefault(ag.barbeiro_id, []).append(
            {
                "hora": ag.data_hora_inicio.strftime("%H:%M"),
                "cliente": ag.cliente.nome if ag.cliente else "Cliente",
                "servico": ag.servico.nome if ag.servico else "Serviço",
                "telefone": ag.cliente.telefone if ag.cliente else None,
                "status": ag.status,
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
                "agendamentos": por_barbeiro.get(b.id, []),
            }
            for b in barbeiros
        ],
    }
