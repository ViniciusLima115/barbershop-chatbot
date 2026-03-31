from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.database import Base


class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        Index("ix_notificacoes_tenant_lida_criada", "estabelecimento_id", "lida", "criada_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    estabelecimento_id = Column(Integer, nullable=False, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id", ondelete="CASCADE"), nullable=True, index=True)
    tipo = Column(String(40), nullable=False)
    titulo = Column(String(255), nullable=False)
    corpo = Column(Text, nullable=True)
    lida = Column(Boolean, nullable=False, default=False)
    criada_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    lida_em = Column(DateTime, nullable=True)
