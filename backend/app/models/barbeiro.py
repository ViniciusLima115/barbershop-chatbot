from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, synonym

from app.database import Base


class Barbeiro(Base):
    __tablename__ = "barbeiros"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    barbershop_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    tempo_por_servico = Column(JSON, nullable=True)

    # Compatibilidade com codigo legado que ainda usa `barbearia_id`.
    barbearia_id = synonym("barbershop_id")
    tenant_id = synonym("barbershop_id")

    barbearia = relationship("Barbearia", back_populates="barbeiros")
