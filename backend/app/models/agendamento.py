from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import relationship, synonym
from app.database import Base


class Agendamento(Base):
    __tablename__ = "agendamentos"
    __table_args__ = (
        Index("ix_agendamentos_tenant_data_barbeiro", "barbearia_id", "data", "barbeiro_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=True, index=True)
    cliente_nome = Column(String(255), nullable=True)
    cliente_telefone = Column(String(30), nullable=True, index=True)
    data = Column(Date, nullable=True, index=True)
    hora_inicio = Column(Time, nullable=True)

    data_hora_inicio = Column(DateTime, nullable=False)
    data_hora_fim = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="pendente")
    tenant_id = synonym("barbearia_id")

    cliente = relationship("Cliente")
    barbeiro = relationship("Barbeiro")
    servico = relationship("Servico")
