from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import synonym
from app.database import Base
from app.time_utils import utcnow_naive


class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    duracao_minutos = Column(Integer, nullable=False)
    preco = Column(Numeric(12, 2), nullable=False)
    pagamento_adiantado_obrigatorio = Column(Boolean, nullable=False, default=False)
    advance_payment_type = Column(String(20), nullable=True)
    advance_payment_amount = Column(Numeric(12, 2), nullable=True)
    payment_description_override = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)

    # Aliases de compatibilidade com código legado
    tenant_id = synonym("estabelecimento_id")
    require_advance_payment = synonym("pagamento_adiantado_obrigatorio")
