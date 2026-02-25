from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS
from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.servico import Servico


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
    periodo: str | None = None,
    tenant_id: int | None = None,
):
    servico_query = db.query(Servico).filter(Servico.id == servico_id)
    if tenant_id is not None:
        servico_query = servico_query.filter(Servico.barbearia_id == tenant_id)
    servico = servico_query.first()
    if not servico:
        return []

    barbeiro_query = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id)
    if tenant_id is not None:
        barbeiro_query = barbeiro_query.filter(Barbeiro.barbershop_id == tenant_id)
    barbeiro = barbeiro_query.first()
    if not barbeiro:
        return []

    duracao = servico.duracao_minutos

    inicio_dia = datetime.combine(data.date(), time(HORARIO_ABERTURA, 0))
    fim_dia = datetime.combine(data.date(), time(HORARIO_FECHAMENTO, 0))

    horarios = []
    atual = inicio_dia

    while atual + timedelta(minutes=duracao) <= fim_dia:
        horarios.append(atual)
        atual += timedelta(minutes=INTERVALO_MINUTOS)

    agendamentos_query = db.query(Agendamento).filter(
        Agendamento.barbeiro_id == barbeiro_id,
        Agendamento.data_hora_inicio >= inicio_dia,
        Agendamento.data_hora_inicio < fim_dia,
    )
    if tenant_id is not None:
        agendamentos_query = agendamentos_query.filter(Agendamento.barbearia_id == tenant_id)
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
