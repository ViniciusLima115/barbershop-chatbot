from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    __table_args__ = (
        UniqueConstraint(
            "establishment_id",
            "provider",
            name="ux_payment_accounts_establishment_provider",
        ),
        UniqueConstraint(
            "provider",
            "external_user_id",
            name="ux_payment_accounts_provider_external_user_id",
        ),
        Index("ix_payment_accounts_establishment_id", "establishment_id"),
        Index("ix_payment_accounts_provider", "provider"),
        Index("ix_payment_accounts_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False)
    provider = Column(String(50), nullable=False, default="mercadopago")
    account_name = Column(String(120), nullable=True)
    client_id_encrypted = Column(Text, nullable=True)
    client_secret_encrypted = Column(Text, nullable=True)
    external_user_id = Column(String(120), nullable=True)
    external_account_email = Column(String(255), nullable=True)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)
    public_key_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    internal_notes = Column(Text, nullable=True)
    created_by_admin_id = Column(String(120), nullable=True)
    updated_by_admin_id = Column(String(120), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    checkout_hold_minutes = Column(Integer, nullable=False, default=10)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
