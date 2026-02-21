from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    telefone = Column(String(20), unique=True, nullable=False)
    etapa_atual = Column(String(100), nullable=False, default="inicio")
    data_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=True)
