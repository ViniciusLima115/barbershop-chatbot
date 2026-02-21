from datetime import datetime

from pydantic import BaseModel


class ClienteCreate(BaseModel):
    telefone: str
    nome: str
    etapa_atual: str = "inicio"


class ClienteResponse(BaseModel):
    id: int
    telefone: str
    nome: str
    etapa_atual: str
    data_criacao: datetime

    class Config:
        from_attributes = True
