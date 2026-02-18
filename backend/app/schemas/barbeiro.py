from pydantic import BaseModel

class BarbeiroCreate(BaseModel):
    nome: str
    


class BarbeiroResponse(BaseModel):
    id: int
    nome: str
    

    class Config:
        from_attributes = True