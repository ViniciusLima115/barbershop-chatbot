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
    pagamento_adiantado_obrigatorio: bool = False
    pagamento_adiantado_obrigatorio_efetivo: bool = False
    advance_payment_type: str | None = None
    advance_payment_amount: float | None = None


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
    # Tema por tenant
    accent_color: str = "#d4930a"
    bg_color: str = "#ffffff"
    logo_url: str | None = None


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
            raise ValueError("Informe slug ou estabelecimento_id para identificar o estabelecimento.")
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
