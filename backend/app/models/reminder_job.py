from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


class ReminderJob(Base):
    __tablename__ = "reminder_jobs"
    __table_args__ = (
        UniqueConstraint("agendamento_id", "tipo", name="ux_reminder_jobs_agendamento_tipo"),
        Index("ix_reminder_jobs_status_enviar_em", "status", "enviar_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)  # reminder_24h | reminder_2h
    canal = Column(String(20), nullable=False, default="whatsapp")
    destinatario = Column(String(30), nullable=False)
    mensagem = Column(Text, nullable=False)
    enviar_em = Column(DateTime, nullable=False, index=True)
    enviado_em = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pendente")
    tentativas = Column(Integer, nullable=False, default=0)
    ultimo_erro = Column(String(255), nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
