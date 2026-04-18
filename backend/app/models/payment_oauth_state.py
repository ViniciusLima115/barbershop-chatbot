from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint

from app.database import Base


class PaymentOAuthState(Base):
    __tablename__ = "payment_oauth_states"
    __table_args__ = (
        UniqueConstraint("provider", "state", name="ux_payment_oauth_states_provider_state"),
        Index("ix_payment_oauth_states_expires_at", "expires_at"),
        Index("ix_payment_oauth_states_establishment_id", "establishment_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, default="mercadopago")
    establishment_id = Column(Integer, nullable=False)
    user_sub = Column(String(255), nullable=True)
    state = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
