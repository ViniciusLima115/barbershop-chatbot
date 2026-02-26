from datetime import date, datetime, time

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PublicBarbeiroItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    nome: str
    tempo_por_servico: dict[str, int] | None = None


class PublicServicoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    nome: str
    duracao: int = Field(validation_alias=AliasChoices("duracao", "duracao_minutos"))


class PublicBarbeariaLookupResponse(BaseModel):
    nome: str
    slug: str
    barbeiros: list[PublicBarbeiroItem]
    servicos: list[PublicServicoItem]
    horarios_disponiveis: list[str]


class PublicAgendamentoCreate(BaseModel):
    slug: str
    cliente_nome: str
    cliente_telefone: str
    barbeiro_id: int
    servico_id: int
    data: date
    hora_inicio: time


class PublicAgendamentoResponse(BaseModel):
    id: int
    tenant_id: int
    slug: str
    cliente_nome: str
    cliente_telefone: str
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: str
    lembretes_agendados: int
