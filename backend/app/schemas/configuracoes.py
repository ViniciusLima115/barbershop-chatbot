import re
from pydantic import BaseModel, field_validator


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PerfilUpdate(BaseModel):
    nome: str | None = None
    endereco: str | None = None
    whatsapp_number: str | None = None
    slug: str | None = None


class SenhaUpdate(BaseModel):
    senha_atual: str
    nova_senha: str

    @field_validator("nova_senha")
    @classmethod
    def nova_senha_minima(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("A nova senha deve ter pelo menos 8 caracteres.")
        return v


class TemaUpdate(BaseModel):
    accent_color: str | None = None
    bg_color: str | None = None
    logo_url: str | None = None

    @field_validator("accent_color", "bg_color")
    @classmethod
    def validar_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Cor deve estar no formato hexadecimal #rrggbb.")
        return v

    @field_validator("logo_url")
    @classmethod
    def validar_logo_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("logo_url deve começar com https://")
        return v


class NotificacoesUpdate(BaseModel):
    notif_ativo: bool | None = None
    notif_horas_antes: int | None = None

    @field_validator("notif_horas_antes")
    @classmethod
    def validar_horas(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v not in [1, 2, 4, 8, 24]:
            raise ValueError("notif_horas_antes deve ser um de: 1, 2, 4, 8, 24.")
        return v
