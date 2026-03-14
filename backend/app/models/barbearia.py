from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Barbearia(Base):
    __tablename__ = "barbearias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    slug = Column(String(120), nullable=True, unique=True, index=True)
    endereco = Column(String(255), nullable=True, default="")
    mega_instance_key = Column(String(255), nullable=True, unique=True, index=True)
    mega_token = Column(String(255), nullable=True)
    whatsapp_number = Column(String(30), nullable=True, unique=True, index=True)

    # Campos administrativos usados pelo painel /admin.
    login = Column(String(255), nullable=True, unique=True)
    senha = Column(String(255), nullable=True)
    plano = Column(String(50), nullable=True, default="basico")
    status_manual = Column(String(50), nullable=True, default="ativo")
    vencimento_em = Column(Date, nullable=True)
    trial_ativo = Column(Boolean, nullable=False, default=False)
    trial_fim_em = Column(Date, nullable=True)
    ultimo_acesso_em = Column(DateTime, nullable=True)
    pagamento_recusado = Column(Boolean, nullable=False, default=False)
    horarios_funcionamento = Column(JSON, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)

    barbeiros = relationship("Barbeiro", back_populates="barbearia")
