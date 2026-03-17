from datetime import date, datetime, time

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


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
    preco: float


class PublicHorarioItem(BaseModel):
    hora: str
    disponivel: bool


class PublicBarbeariaLookupResponse(BaseModel):
    barbearia_id: int
    nome: str
    slug: str
    barbeiros: list[PublicBarbeiroItem]
    servicos: list[PublicServicoItem]
    horarios_disponiveis: list[str]
    horarios_grade: list[PublicHorarioItem] = []


class PublicClienteLookupResponse(BaseModel):
    nome: str
    email: str | None = None
    telefone: str


class PublicAgendamentoCreate(BaseModel):
    slug: str | None = None
    barbearia_id: int | None = None
    cliente_nome: str
    cliente_telefone: str
    cliente_email: str | None = None
    barbeiro_id: int
    servico_id: int
    data: date
    hora_inicio: time

    @model_validator(mode="after")
    def validar_tenant_identificador(self):
        if not self.slug and not self.barbearia_id:
            raise ValueError("Informe slug ou barbearia_id para identificar a barbearia.")
        return self


class PublicAgendamentoResponse(BaseModel):
    id: int
    tenant_id: int
    barbearia_id: int
    slug: str
    cliente_nome: str
    cliente_telefone: str
    cliente_email: str | None = None
    barbeiro_id: int
    servico_id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: str
    confirmation_token: str
    lembretes_agendados: int
