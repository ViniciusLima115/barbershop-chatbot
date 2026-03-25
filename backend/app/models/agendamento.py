from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import relationship, synonym
from app.database import Base


class Agendamento(Base):
    __tablename__ = "agendamentos"
    __table_args__ = (
        Index("ix_agendamentos_tenant_data_barbeiro", "estabelecimento_id", "data", "profissional_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    profissional_id = Column(Integer, ForeignKey("profissionais.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)
    cliente_nome = Column(String(255), nullable=True)
    cliente_telefone = Column(String(30), nullable=True, index=True)
    cliente_email = Column(String(255), nullable=True, index=True)
    data = Column(Date, nullable=True, index=True)
    hora_inicio = Column(Time, nullable=True)

    data_hora_inicio = Column(DateTime, nullable=False)
    data_hora_fim = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="pendente")
    confirmation_token = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    lembrete_24h_enviado = Column(Boolean, nullable=False, default=False)
    lembrete_2h_enviado = Column(Boolean, nullable=False, default=False)

    # Aliases de compatibilidade com código legado (colunas físicas renomeadas)
    barbearia_id = synonym("estabelecimento_id")
    barbeiro_id = synonym("profissional_id")
    tenant_id = synonym("estabelecimento_id")

    cliente = relationship("Cliente")
    profissional = relationship("Profissional", foreign_keys=[profissional_id])
    servico = relationship("Servico")
    estabelecimento = relationship("Estabelecimento", foreign_keys=[estabelecimento_id])

    # Aliases de relacionamento para código legado que acessa .barbeiro / .barbearia
    barbeiro = relationship("Profissional", foreign_keys=[profissional_id], overlaps="profissional")
    barbearia = relationship("Estabelecimento", foreign_keys=[estabelecimento_id], overlaps="estabelecimento")
