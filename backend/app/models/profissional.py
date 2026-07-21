from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, synonym

from app.database import Base


class Profissional(Base):
    __tablename__ = "profissionais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    tempo_por_servico = Column(JSON, nullable=True)
    horarios_funcionamento = Column(JSON, nullable=True)

    # Compatibilidade com codigo legado que ainda usa `tenant_id`.
    tenant_id = synonym("estabelecimento_id")

    estabelecimento = relationship("Estabelecimento", back_populates="profissionais")
