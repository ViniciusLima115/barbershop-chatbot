from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


StatusAgendamento = Literal["pending_payment", "payment_review_required", "pendente", "confirmado", "cancelado", "failed", "reagendamento_solicitado", "compareceu", "no_show", "expired"]
StatusPagamento = Literal["not_required", "pending", "approved", "rejected", "cancelled", "refunded", "charged_back", "expired"]


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgendamentoCreate(StrictRequestModel):
    telefone: str = Field(min_length=8, max_length=30, pattern=r"^[0-9+().\s-]+$")
    nome_cliente: str = Field(min_length=2, max_length=120)
    cliente_email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    barbeiro_id: int = Field(gt=0)
    servico_id: int = Field(gt=0)
    data_hora_inicio: datetime
    status: StatusAgendamento = "pendente"


class AgendamentoStatusUpdate(StrictRequestModel):
    status: StatusAgendamento


class AgendamentoPatch(StrictRequestModel):
    barbeiro_id: int | None = Field(default=None, gt=0)
    servico_id: int | None = Field(default=None, gt=0)
    data_hora_inicio: datetime | None = None
    cliente_email: str | None = None
    status: StatusAgendamento | None = None


class AgendamentoUpdate(StrictRequestModel):
    barbeiro_id: int = Field(gt=0)
    servico_id: int = Field(gt=0)
    data_hora_inicio: datetime
    cliente_email: str | None = None
    status: StatusAgendamento = "confirmado"


class AgendamentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    cliente_nome: str
    telefone: str
    cliente_email: str | None = None

    barbeiro_nome: str
    servico_nome: str

    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: StatusAgendamento
    payment_status: StatusPagamento = "not_required"
    payment_required: bool = False
    payment_amount: float | None = None
    payment_type: str | None = None


class AgendamentoRemarcacaoRequest(StrictRequestModel):
    data_hora_inicio: datetime


class AgendamentoTokenDataResponse(BaseModel):
    id: int
    estabelecimento_id: int
    slug: str | None = None
    confirmation_token: str
    cliente_nome: str
    cliente_email: str | None = None
    barbeiro_id: int
    barbeiro_nome: str
    servico_id: int
    servico_nome: str
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: StatusAgendamento
