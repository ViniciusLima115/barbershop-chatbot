from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database import Base

class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"))
    servico_id = Column(Integer, ForeignKey("servicos.id"))

    data_hora_inicio = Column(DateTime)
    data_hora_fim = Column(DateTime)

    status = Column(String, default="agendado")

    barbeiro = relationship("Barbeiro")
    servico = relationship("Servico")
    cliente = relationship("Cliente")