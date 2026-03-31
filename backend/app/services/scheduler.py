import logging
from datetime import datetime, timedelta
from threading import Lock

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models.agendamento import Agendamento
from app.services.email_service import (
    AgendamentoEmailContext,
    build_reminder_email,
    send_email_payload,
)


logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover - depends on optional dependency at runtime
    BackgroundScheduler = None


_scheduler = None
_scheduler_lock = Lock()
_REMINDER_GRACE_MINUTES = 5


def _montar_contexto_email(agendamento: Agendamento) -> AgendamentoEmailContext | None:
    if not agendamento.cliente_email or not agendamento.barbearia or not agendamento.barbeiro or not agendamento.servico:
        return None

    return AgendamentoEmailContext(
        agendamento_id=agendamento.id,
        confirmation_token=agendamento.confirmation_token,
        cliente_nome=agendamento.cliente_nome or "",
        cliente_email=agendamento.cliente_email,
        barbearia_nome=agendamento.barbearia.nome,
        barbearia_id=agendamento.barbearia_id,
        slug=agendamento.barbearia.slug,
        servico_nome=agendamento.servico.nome,
        barbeiro_nome=agendamento.barbeiro.nome,
        data_hora_inicio=agendamento.data_hora_inicio,
    )


def _tipos_de_lembrete_devidos(agendamento: Agendamento, agora: datetime) -> list[int]:
    diferenca = agendamento.data_hora_inicio - agora
    tolerancia = timedelta(minutes=_REMINDER_GRACE_MINUTES)
    devidos: list[int] = []

    if (
        not agendamento.lembrete_24h_enviado
        and timedelta(hours=24) - tolerancia <= diferenca <= timedelta(hours=24) + tolerancia
    ):
        devidos.append(24)
    if (
        not agendamento.lembrete_2h_enviado
        and timedelta(hours=2) - tolerancia <= diferenca <= timedelta(hours=2) + tolerancia
    ):
        devidos.append(2)

    return devidos


def _processar_notificacoes_pendentes():
    from app.services.notificacao_inapp_service import processar_pendentes_confirmacao
    db = SessionLocal()
    try:
        processar_pendentes_confirmacao(db)
    finally:
        db.close()


def processar_lembretes_email_pendentes(limite: int = 200) -> dict[str, int]:
    db = SessionLocal()
    try:
        agora = datetime.now()
        janela_final = agora + timedelta(hours=24, minutes=_REMINDER_GRACE_MINUTES)

        agendamentos = (
            db.query(Agendamento)
            .options(
                joinedload(Agendamento.barbearia),
                joinedload(Agendamento.barbeiro),
                joinedload(Agendamento.servico),
            )
            .filter(
                Agendamento.cliente_email.isnot(None),
                Agendamento.cliente_email != "",
                Agendamento.status.in_(["pendente", "confirmado"]),
                Agendamento.data_hora_inicio >= agora,
                Agendamento.data_hora_inicio <= janela_final,
            )
            .order_by(Agendamento.data_hora_inicio.asc(), Agendamento.id.asc())
            .limit(limite)
            .all()
        )

        processados = 0
        enviados = 0
        falhas = 0

        for agendamento in agendamentos:
            tipos = _tipos_de_lembrete_devidos(agendamento, agora)
            if not tipos:
                continue

            contexto = _montar_contexto_email(agendamento)
            if not contexto:
                continue

            for horas in tipos:
                processados += 1
                payload = build_reminder_email(contexto, hours_before=horas)
                ok = send_email_payload(payload)
                if ok:
                    if horas == 24:
                        agendamento.lembrete_24h_enviado = True
                    if horas == 2:
                        agendamento.lembrete_2h_enviado = True
                    enviados += 1
                else:
                    falhas += 1

        if processados:
            db.commit()

        if processados:
            logger.info(
                "Scheduler de lembretes processou %s lembretes (%s enviados, %s falhas).",
                processados,
                enviados,
                falhas,
            )
        return {"processados": processados, "enviados": enviados, "falhas": falhas}
    except Exception:
        logger.exception("Falha ao processar lembretes de email.")
        return {"processados": 0, "enviados": 0, "falhas": 1}
    finally:
        db.close()


def start_scheduler():
    global _scheduler

    if BackgroundScheduler is None:
        logger.warning("APScheduler nao esta instalado. Scheduler de email nao sera iniciado.")
        return None

    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            return _scheduler

        scheduler = BackgroundScheduler(timezone="America/Maceio")
        scheduler.add_job(
            processar_lembretes_email_pendentes,
            "interval",
            minutes=1,
            id="email-reminders",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        scheduler.add_job(
            _processar_notificacoes_pendentes,
            "interval",
            minutes=1,
            id="inapp-notifications",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        scheduler.start()
        _scheduler = scheduler
        logger.info("Scheduler de lembretes de email iniciado.")
        return _scheduler


def stop_scheduler():
    global _scheduler

    with _scheduler_lock:
        if _scheduler:
            _scheduler.shutdown(wait=False)
            logger.info("Scheduler de lembretes de email finalizado.")
            _scheduler = None
