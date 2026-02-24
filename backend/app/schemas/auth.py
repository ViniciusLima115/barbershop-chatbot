from pydantic import BaseModel


class AdminCheckRequest(BaseModel):
    usuario: str
    senha: str


class AdminCheckResponse(BaseModel):
    is_admin: bool
