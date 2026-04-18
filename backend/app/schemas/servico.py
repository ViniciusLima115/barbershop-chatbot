from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


AdvancePaymentType = Literal["full", "signal"]


class _ServicoBase(BaseModel):
    nome: str
    duracao_minutos: int
    preco: float
    pagamento_adiantado_obrigatorio: bool = False
    advance_payment_type: AdvancePaymentType | None = None
    advance_payment_amount: float | None = None
    payment_description_override: str | None = None

    @model_validator(mode="after")
    def validar_pagamento_adiantado(self):
        if not self.pagamento_adiantado_obrigatorio:
            self.advance_payment_type = None
            self.advance_payment_amount = None
            return self

        self.advance_payment_type = self.advance_payment_type or "full"
        if self.advance_payment_type == "full":
            self.advance_payment_amount = None
            if self.preco <= 0:
                raise ValueError("Servico com pagamento adiantado deve ter preco maior que zero.")
            return self

        if self.advance_payment_type == "signal":
            if self.advance_payment_amount is None:
                raise ValueError("Informe o valor do sinal para este servico.")
            if self.advance_payment_amount <= 0:
                raise ValueError("O valor do sinal deve ser maior que zero.")
            if self.preco > 0 and self.advance_payment_amount > self.preco:
                raise ValueError("O valor do sinal nao pode ser maior que o preco do servico.")
            return self

        raise ValueError("Tipo de pagamento adiantado invalido.")


class ServicoCreate(_ServicoBase):
    pass


class ServicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    duracao_minutos: int
    preco: float
    pagamento_adiantado_obrigatorio: bool
    advance_payment_type: AdvancePaymentType | None = None
    advance_payment_amount: float | None = None
    payment_description_override: str | None = None
    updated_at: datetime | None = None


class ServicoUpdate(_ServicoBase):
    pass
