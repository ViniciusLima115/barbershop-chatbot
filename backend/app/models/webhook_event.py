from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="ux_webhook_events_provider_event_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    event_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
