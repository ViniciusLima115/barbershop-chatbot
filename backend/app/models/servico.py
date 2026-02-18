from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.database import Base

class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    duracao_minutos = Column(Integer)
    preco = Column(Float)
    