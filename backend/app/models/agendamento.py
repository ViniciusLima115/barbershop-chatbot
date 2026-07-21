from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Time
from sqlalchemy.orm import relationship, synonym
from app.database import Base
from app.time_utils import utcnow_naive


class Agendamento(Base):
    __tablename__ = "agendamentos"
    __table_args__ = (
        Index("ix_agendamentos_tenant_data_barbeiro", "estabelecimento_id", "data", "profissional_id"),
        Index("ix_agendamentos_payment_status", "payment_status"),
        Index("ix_agendamentos_payment_hold_expires_at", "payment_hold_expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    profissional_id = Column(Integer, ForeignKey("profissionais.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)
    cliente_nome = Column(String(255), nullable=True)
    cliente_telefone = Column(String(30), nullable=True, index=True)
    cliente_email = Column(String(255), nullable=True, index=True)
    data = Column(Date, nullable=True, index=True)
    hora_inicio = Column(Time, nullable=True)

    data_hora_inicio = Column(DateTime, nullable=False)
    data_hora_fim = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="pendente")
    confirmation_token = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    confirmation_token_expires_at = Column(DateTime, nullable=True)
    lembrete_24h_enviado = Column(Boolean, nullable=False, default=False)
    lembrete_2h_enviado = Column(Boolean, nullable=False, default=False)
    compareceu_em = Column(DateTime, nullable=True)
    pagamento_adiantado_exigido = Column(Boolean, nullable=False, default=False, index=True)
    payment_type_snapshot = Column(String(20), nullable=True)
    payment_amount_snapshot = Column(Numeric(12, 2), nullable=True)
    payment_status = Column(String(30), nullable=False, default="not_required")
    payment_hold_expires_at = Column(DateTime, nullable=True)
    provider_checkout_reference = Column(String(255), nullable=True)
    provider_preference_id = Column(String(255), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)

    # Aliases de compatibilidade com código legado (colunas físicas renomeadas)
    barbeiro_id = synonym("profissional_id")
    tenant_id = synonym("estabelecimento_id")
    booking_status = synonym("status")
    payment_required_snapshot = synonym("pagamento_adiantado_exigido")

    cliente = relationship("Cliente")
    profissional = relationship("Profissional", foreign_keys=[profissional_id])
    servico = relationship("Servico")
    estabelecimento = relationship("Estabelecimento", foreign_keys=[estabelecimento_id])

    # Alias de relacionamento para código legado que acessa .barbeiro
    barbeiro = relationship("Profissional", foreign_keys=[profissional_id], overlaps="profissional")
