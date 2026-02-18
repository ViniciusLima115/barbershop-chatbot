from pydantic import BaseModel
from datetime import datetime

class AgendamentoCreate(BaseModel):
    telefone: str
    nome_cliente: str
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime

class AgendamentoResponse(BaseModel):
    id: int

    cliente_nome: str
    telefone: str

    barbeiro_nome: str
    servico_nome: str

    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: str

    class Config:
        from_attributes = True