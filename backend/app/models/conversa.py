from sqlalchemy import Column, Integer, String, JSON
from app.database import Base


class Conversa(Base):
    __tablename__ = "conversas"

    id = Column(Integer, primary_key=True)
    telefone = Column(String, unique=True, index=True)

    estado = Column(String)
    contexto = Column(JSON)