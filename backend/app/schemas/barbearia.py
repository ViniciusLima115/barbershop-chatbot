from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


PlanoBarbearia = Literal["basico", "premium"]
StatusManualBarbearia = Literal["ativo", "inativo"]


class BarbeariaAdminCreate(BaseModel):
    nome: str
    slug: str | None = None
    login: str
    senha: str
    plano: PlanoBarbearia = "basico"
    status_manual: StatusManualBarbearia = "ativo"
    vencimento_em: date
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = ""


class BarbeariaAdminUpdate(BaseModel):
    nome: str
    slug: str | None = None
    login: str
    senha: str
    plano: PlanoBarbearia
    status_manual: StatusManualBarbearia
    vencimento_em: date
    trial_ativo: bool
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    endereco: str = ""


class BarbeariaAdminResponse(BaseModel):
    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    senha: str | None = None
    plano: PlanoBarbearia | None = "basico"
    status_manual: StatusManualBarbearia | None = "ativo"
    vencimento_em: date | None = None
    trial_ativo: bool = False
    trial_fim_em: date | None = None
    ultimo_acesso_em: datetime | None = None
    pagamento_recusado: bool = False
    criado_em: datetime

    class Config:
        from_attributes = True


class BarbeariaFuncionamentoDia(BaseModel):
    ativo: bool = True
    inicio: str = "08:00"
    fim: str = "18:00"

    @field_validator("inicio", "fim")
    @classmethod
    def validar_hora(cls, value: str) -> str:
        texto = value.strip()
        try:
            datetime.strptime(texto, "%H:%M")
        except ValueError as exc:
            raise ValueError("Horario deve estar no formato HH:MM.") from exc
        return texto


class BarbeariaFuncionamento(BaseModel):
    seg: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    ter: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    qua: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    qui: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    sex: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    sab: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()
    dom: BarbeariaFuncionamentoDia = BarbeariaFuncionamentoDia()

    @model_validator(mode="after")
    def validar_intervalos(self):
        for dia in ("seg", "ter", "qua", "qui", "sex", "sab", "dom"):
            item = getattr(self, dia)
            if item.ativo and item.inicio >= item.fim:
                raise ValueError(f"{dia}: horario inicial precisa ser menor que o final.")
        return self
