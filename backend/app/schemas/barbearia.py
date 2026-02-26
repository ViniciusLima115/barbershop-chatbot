from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


PlanoBarbearia = Literal["basico", "premium"]
StatusManualBarbearia = Literal["ativo", "inativo"]


class BarbeariaAdminCreate(BaseModel):
    nome: str
    slug: str | None = None
    login: str
    senha: str
    mega_instance_key: str | None = None
    mega_token: str | None = None
    whatsapp_number: str | None = None
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
    mega_instance_key: str | None = None
    mega_token: str | None = None
    whatsapp_number: str | None = None
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
    mega_instance_key: str | None = None
    mega_token: str | None = None
    whatsapp_number: str | None = None
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
