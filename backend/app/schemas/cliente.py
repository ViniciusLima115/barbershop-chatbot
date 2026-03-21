from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClienteCreate(BaseModel):
    telefone: str
    nome: str
    etapa_atual: str = "inicio"


class ClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telefone: str
    nome: str
    etapa_atual: str
    data_criacao: datetime


class ClienteUpdate(BaseModel):
    telefone: str
    nome: str
    etapa_atual: str | None = None
