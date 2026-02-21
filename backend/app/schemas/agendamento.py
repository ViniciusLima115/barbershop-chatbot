from typing import Literal

from pydantic import BaseModel
from datetime import datetime


StatusAgendamento = Literal["pendente", "confirmado", "cancelado"]


class AgendamentoCreate(BaseModel):
    telefone: str
    nome_cliente: str
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    status: StatusAgendamento = "pendente"


class AgendamentoStatusUpdate(BaseModel):
    status: StatusAgendamento

class AgendamentoResponse(BaseModel):
    id: int

    cliente_nome: str
    telefone: str

    barbeiro_nome: str
    servico_nome: str

    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: StatusAgendamento

    class Config:
        from_attributes = True
