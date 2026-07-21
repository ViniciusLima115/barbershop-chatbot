from datetime import date, datetime, time, timedelta

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


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
    pagamento_adiantado_obrigatorio: bool = False
    pagamento_adiantado_obrigatorio_efetivo: bool = False
    advance_payment_type: str | None = None
    advance_payment_amount: float | None = None


class PublicHorarioItem(BaseModel):
    hora: str
    disponivel: bool


class PublicEstabelecimentoLookupResponse(BaseModel):
    estabelecimento_id: int
    nome: str
    slug: str
    barbeiros: list[PublicBarbeiroItem]
    servicos: list[PublicServicoItem]
    horarios_disponiveis: list[str]
    horarios_grade: list[PublicHorarioItem] = []
    # Tema por tenant
    accent_color: str = "#d4930a"
    bg_color: str = "#ffffff"
    logo_url: str | None = None


class PublicClienteLookupResponse(BaseModel):
    nome: str
    email: str | None = None
    telefone: str


class PublicAgendamentoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    estabelecimento_id: int | None = Field(default=None, gt=0)
    cliente_nome: str = Field(min_length=2, max_length=120)
    cliente_telefone: str = Field(min_length=8, max_length=30, pattern=r"^[0-9+().\s-]+$")
    cliente_email: str | None = Field(
        default=None,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    barbeiro_id: int = Field(gt=0)
    servico_id: int = Field(gt=0)
    data: date
    hora_inicio: time

    @field_validator("cliente_nome")
    @classmethod
    def validar_nome(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value) or "<" in value or ">" in value:
            raise ValueError("Nome contem caracteres invalidos.")
        return value

    @model_validator(mode="after")
    def validar_tenant_identificador(self):
        if bool(self.slug) == bool(self.estabelecimento_id):
            raise ValueError("Informe apenas slug ou estabelecimento_id para identificar o estabelecimento.")
        if self.data > date.today() + timedelta(days=730):
            raise ValueError("Data fora da janela permitida para agendamento.")
        return self


class PublicAgendamentoResponse(BaseModel):
    id: int
    tenant_id: int
    estabelecimento_id: int
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


class PublicPagamentoInitResponse(BaseModel):
    agendamento_id: int
    external_reference: str
    preference_id: str
    checkout_url: str
    amount: float
    pagamento_status: str
    agendamento_status: str
    expires_at: datetime | None = None


class PublicPagamentoStatusResponse(BaseModel):
    external_reference: str
    agendamento_id: int
    pagamento_status: str
    agendamento_status: str
    amount: float
