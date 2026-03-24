from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String

from app.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    __table_args__ = (Index("ix_token_blacklist_expires_at", "expires_at"),)

    jti = Column(String(36), primary_key=True)
    expires_at = Column(DateTime, nullable=False)
