from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    telefone = Column(String, index=True)
   