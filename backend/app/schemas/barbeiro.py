from pydantic import AliasChoices, BaseModel, ConfigDict, Field

class BarbeiroCreate(BaseModel):
    nome: str


class BarbeiroUpdate(BaseModel):
    nome: str


class BarbeiroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    nome: str
    barbershop_id: int = Field(validation_alias=AliasChoices("barbershop_id", "barbearia_id"))
    barbearia_id: int = Field(validation_alias=AliasChoices("barbearia_id", "barbershop_id"))
