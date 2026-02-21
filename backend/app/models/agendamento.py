from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)

    data_hora_inicio = Column(DateTime, nullable=False)
    data_hora_fim = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="pendente")

    cliente = relationship("Cliente")
    barbeiro = relationship("Barbeiro")
    servico = relationship("Servico")
