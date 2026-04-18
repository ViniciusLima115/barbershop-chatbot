from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_event_id",
            name="ux_payment_webhook_events_provider_external_event_id",
        ),
        Index("ix_payment_webhook_events_provider", "provider"),
        Index("ix_payment_webhook_events_establishment_id", "establishment_id"),
        Index("ix_payment_webhook_events_payment_id", "payment_id"),
        Index("ix_payment_webhook_events_processing_status", "processing_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("pagamentos.id"), nullable=True)
    external_event_id = Column(String(255), nullable=True, index=True)
    external_topic = Column(String(120), nullable=True)
    signature_valid = Column(Boolean, nullable=True)
    payload = Column(JSON, nullable=False)
    processing_status = Column(String(30), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
