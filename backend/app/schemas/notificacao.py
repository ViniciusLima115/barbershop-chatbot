from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


TipoNotificacao = Literal["novo_agendamento", "agendamento_confirmado", "pendente_confirmacao"]


class NotificacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agendamento_id: int | None
    tipo: TipoNotificacao
    titulo: str
    corpo: str | None
    lida: bool
    criada_em: datetime
    lida_em: datetime | None


class ConfirmarPresencaPayload(BaseModel):
    compareceu: bool
