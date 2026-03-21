from pydantic import BaseModel, ConfigDict

class ServicoCreate(BaseModel):
    nome: str
    duracao_minutos: int
    preco: float
    


class ServicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    duracao_minutos: int
    preco: float


class ServicoUpdate(BaseModel):
    nome: str
    duracao_minutos: int
    preco: float
