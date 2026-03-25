from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import synonym
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    etapa_atual = Column(String(100), nullable=False, default="inicio")
    contexto = Column(JSON, nullable=True)
    data_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)

    # Alias de compatibilidade com código legado
    barbearia_id = synonym("estabelecimento_id")
