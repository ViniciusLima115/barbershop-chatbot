from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.barbearia import BarbeariaFuncionamento

class BarbeiroCreate(BaseModel):
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: BarbeariaFuncionamento | None = None


class BarbeiroUpdate(BaseModel):
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: BarbeariaFuncionamento | None = None


class BarbeiroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: BarbeariaFuncionamento | None = None
    barbershop_id: int = Field(validation_alias=AliasChoices("barbershop_id", "barbearia_id"))
    barbearia_id: int = Field(validation_alias=AliasChoices("barbearia_id", "barbershop_id"))
