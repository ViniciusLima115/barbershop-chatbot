from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.servico import Servico
from app.services.barbershop_hours_service import build_day_slots, get_working_window


def _hora_esta_no_periodo(hora: int, periodo: str) -> bool:
    periodo = periodo.strip().lower()

    if periodo == "manha":
        return 6 <= hora < 12
    if periodo == "tarde":
        return 12 <= hora < 18
    if periodo == "noite":
        return 18 <= hora < 24

    return False


def gerar_horarios_disponiveis(
    db: Session,
    barbeiro_id: int,
    servico_id: int,
    data: datetime,
    tenant_id: int,
    periodo: str | None = None,
):
    servico_query = db.query(Servico).filter(
        Servico.id == servico_id,
        Servico.barbearia_id == tenant_id,
    )
    servico = servico_query.first()
    if not servico:
        return []

    barbeiro_query = db.query(Barbeiro).filter(
        Barbeiro.id == barbeiro_id,
        Barbeiro.barbershop_id == tenant_id,
    )
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        return []

    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        return []

    duracao = servico.duracao_minutos
    window = get_working_window(barbearia, data.date(), barbeiro=barbeiro)
    if not window:
        return []

    inicio_dia = datetime.combine(data.date(), window[0])
    fim_dia = datetime.combine(data.date(), window[1])
    horarios = build_day_slots(barbearia, data.date(), duracao, barbeiro=barbeiro)

    agendamentos_query = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == barbeiro_id,
        Agendamento.barbearia_id == tenant_id,
        Agendamento.data_hora_inicio >= inicio_dia,
        Agendamento.data_hora_inicio < fim_dia,
    )
    agendamentos = agendamentos_query.all()

    livres = []

    for horario in horarios:
        if periodo and not _hora_esta_no_periodo(horario.hour, periodo):
            continue

        fim_slot = horario + timedelta(minutes=duracao)

        conflito = False
        for ag in agendamentos:
            if ag.data_hora_inicio < fim_slot and ag.data_hora_fim > horario:
                conflito = True
                break

        if not conflito:
            livres.append(horario.strftime("%H:%M"))

    return livres
