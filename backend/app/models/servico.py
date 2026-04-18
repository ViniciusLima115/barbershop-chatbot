from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import synonym
from app.database import Base


class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    duracao_minutos = Column(Integer, nullable=False)
    preco = Column(Float, nullable=False)
    pagamento_adiantado_obrigatorio = Column(Boolean, nullable=False, default=False)
    advance_payment_type = Column(String(20), nullable=True)
    advance_payment_amount = Column(Float, nullable=True)
    payment_description_override = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)

    # Aliases de compatibilidade com código legado
    barbearia_id = synonym("estabelecimento_id")
    tenant_id = synonym("estabelecimento_id")
    require_advance_payment = synonym("pagamento_adiantado_obrigatorio")
