from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.profissional import Profissional
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import tenant_id_from_header
from app.schemas.barbeiro import BarbeiroCreate, BarbeiroResponse, BarbeiroUpdate
from app.services.estabelecimento_hours_service import get_working_hours

router = APIRouter(prefix="/profissionais")
MAX_BARBEIROS_BASICO = 1
MAX_BARBEIROS_PREMIUM = 3


def _get_estabelecimento(db: Session, tenant_id: int) -> Estabelecimento:
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return estabelecimento


@router.post("/", response_model=BarbeiroResponse)
def criar(
    dados: BarbeiroCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    estabelecimento = _get_estabelecimento(db, tenant_id)

    total = db.query(Profissional).filter(Profissional.estabelecimento_id == tenant_id).count()
    plano = (estabelecimento.plano or "basico").lower()
    limite = MAX_BARBEIROS_PREMIUM if plano == "premium" else MAX_BARBEIROS_BASICO

    if total >= limite and plano != "premium":
        raise HTTPException(
            status_code=403,
            detail="Deseja adicionar mais profissionais? Faca o upgrade para o plano premium.",
        )

    if total >= limite and plano == "premium":
        raise HTTPException(status_code=400, detail="Limite de 3 profissionais ativos atingido.")

    payload = {
        "nome": dados.nome.strip(),
        "estabelecimento_id": tenant_id,
        "ativo": dados.ativo,
        "tempo_por_servico": dados.tempo_por_servico,
        "horarios_funcionamento": (
            dados.horarios_funcionamento.model_dump()
            if dados.horarios_funcionamento is not None
            else get_working_hours(estabelecimento)
        ),
    }

    profissional = Profissional(**payload)

    db.add(profissional)
    db.commit()
    db.refresh(profissional)

    return profissional


@router.get("/", response_model=list[BarbeiroResponse])
def listar(tenant_id: int = Depends(tenant_id_from_header), db: Session = Depends(get_db)):
    _get_estabelecimento(db, tenant_id)
    query = db.query(Profissional).filter(Profissional.estabelecimento_id == tenant_id)
    return query.order_by(Profissional.id.asc()).all()


@router.put("/{profissional_id}", response_model=BarbeiroResponse)
def atualizar(
    profissional_id: int,
    dados: BarbeiroUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _get_estabelecimento(db, tenant_id)
    query = db.query(Profissional).filter(Profissional.id == profissional_id, Profissional.estabelecimento_id == tenant_id)

    profissional = query.first()
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado.")

    profissional.nome = dados.nome.strip()
    profissional.ativo = dados.ativo
    profissional.tempo_por_servico = dados.tempo_por_servico
    profissional.horarios_funcionamento = (
        dados.horarios_funcionamento.model_dump()
        if dados.horarios_funcionamento is not None
        else None
    )
    db.commit()
    db.refresh(profissional)

    return profissional


@router.delete("/{profissional_id}", status_code=204)
def remover(
    profissional_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _get_estabelecimento(db, tenant_id)
    query = db.query(Profissional).filter(Profissional.id == profissional_id, Profissional.estabelecimento_id == tenant_id)

    profissional = query.first()
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado.")

    db.delete(profissional)
    db.commit()
