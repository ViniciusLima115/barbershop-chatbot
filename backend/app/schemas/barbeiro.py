from pydantic import BaseModel, ConfigDict

from app.schemas.estabelecimento import EstabelecimentoFuncionamento

class BarbeiroCreate(BaseModel):
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: EstabelecimentoFuncionamento | None = None


class BarbeiroUpdate(BaseModel):
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: EstabelecimentoFuncionamento | None = None


class BarbeiroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ativo: bool = True
    tempo_por_servico: dict[str, int] | None = None
    horarios_funcionamento: EstabelecimentoFuncionamento | None = None
    estabelecimento_id: int
