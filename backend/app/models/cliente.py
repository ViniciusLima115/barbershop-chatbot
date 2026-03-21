from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
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
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=True)
