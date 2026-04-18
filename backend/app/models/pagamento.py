from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship, synonym

from app.database import Base


class Pagamento(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (
        Index("ix_pagamentos_estabelecimento_id", "estabelecimento_id"),
        Index("ix_pagamentos_provider", "provider"),
        Index("ix_pagamentos_status", "status"),
        Index("ix_pagamentos_provider_payment_id", "provider_payment_id"),
        Index("ix_pagamentos_preference_id", "preference_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"), nullable=False, unique=True, index=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)
    payment_account_id = Column(Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    provider = Column(String(50), nullable=False, default="mercado_pago")
    idempotency_key = Column(String(120), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    provider_payment_id = Column(String(120), nullable=True, unique=True)
    preference_id = Column(String(120), nullable=True, unique=True)
    external_merchant_order_id = Column(String(120), nullable=True, index=True)
    external_status = Column(String(80), nullable=True)
    external_reference = Column(String(120), nullable=False, unique=True, index=True)
    amount = Column(Float, nullable=False)
    platform_fee_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="BRL")
    payment_method = Column(String(80), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    checkout_url = Column(String(700), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    # Aliases de compatibilidade e nomenclatura futura
    booking_id = synonym("agendamento_id")
    establishment_id = synonym("estabelecimento_id")
    external_preference_id = synonym("preference_id")
    external_payment_id = synonym("provider_payment_id")
    raw_last_payload = synonym("raw_payload")

    agendamento = relationship("Agendamento")
