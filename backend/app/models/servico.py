from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import synonym
from app.database import Base


class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    duracao_minutos = Column(Integer, nullable=False)
    preco = Column(Float, nullable=False)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)

    # Aliases de compatibilidade com código legado
    barbearia_id = synonym("estabelecimento_id")
    tenant_id = synonym("estabelecimento_id")
