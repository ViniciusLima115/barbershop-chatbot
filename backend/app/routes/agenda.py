from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.config import INTERVALO_MINUTOS
from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.routes.deps import tenant_id_from_header
from app.services.barbershop_hours_service import build_day_slots, get_working_window
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
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    barbeiros = (
        db.query(Barbeiro)
        .filter(Barbeiro.barbershop_id == tenant_id)
        .order_by(Barbeiro.id.asc())
        .all()
    )

    horarios_por_barbeiro = {
        barbeiro.id: [
            slot.strftime("%H:%M")
            for slot in build_day_slots(barbearia, data.date(), INTERVALO_MINUTOS, barbeiro=barbeiro)
        ]
        for barbeiro in barbeiros
    }
    horarios = sorted({hora for itens in horarios_por_barbeiro.values() for hora in itens})

    janelas = [
        get_working_window(barbearia, data.date(), barbeiro=barbeiro)
        for barbeiro in barbeiros
    ]
    intervalos_ativos = [janela for janela in janelas if janela]

    agendamentos = []
    if intervalos_ativos:
        inicio_dia = min(datetime.combine(data.date(), janela[0]) for janela in intervalos_ativos)
        fim_dia = max(datetime.combine(data.date(), janela[1]) for janela in intervalos_ativos)
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
                "horarios": horarios_por_barbeiro.get(b.id, []),
                "agendamentos": por_barbeiro.get(b.id, []),
            }
            for b in barbeiros
        ],
    }
