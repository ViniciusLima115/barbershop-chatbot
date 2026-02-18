from pydantic import BaseModel

class ServicoCreate(BaseModel):
    nome: str
    duracao_minutos: int
    preco: float
    


class ServicoResponse(BaseModel):
    id: int
    nome: str
    duracao_minutos: int
    preco: float
    

    class Config:
        from_attributes = True
