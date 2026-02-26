from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.routes.deps import tenant_id_from_header
from app.schemas.barbeiro import BarbeiroCreate, BarbeiroResponse, BarbeiroUpdate

router = APIRouter(prefix="/barbeiros")
MAX_BARBEIROS_BASICO = 1
MAX_BARBEIROS_PREMIUM = 3


def _get_barbearia(db: Session, tenant_id: int) -> Barbearia:
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")
    return barbearia


@router.post("/", response_model=BarbeiroResponse)
def criar(
    dados: BarbeiroCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    barbearia = _get_barbearia(db, tenant_id)

    total = db.query(Barbeiro).filter(Barbeiro.barbershop_id == tenant_id).count()
    plano = (barbearia.plano or "basico").lower()
    limite = MAX_BARBEIROS_PREMIUM if plano == "premium" else MAX_BARBEIROS_BASICO

    if total >= limite and plano != "premium":
        raise HTTPException(
            status_code=403,
            detail="Deseja adicionar mais barbeiros? Faca o upgrade para o plano premium.",
        )

    if total >= limite and plano == "premium":
        raise HTTPException(status_code=400, detail="Limite de 3 barbeiros ativos atingido.")

    payload = {
        "nome": dados.nome.strip(),
        "barbershop_id": tenant_id,
        "ativo": dados.ativo,
        "tempo_por_servico": dados.tempo_por_servico,
    }

    barbeiro = Barbeiro(**payload)

    db.add(barbeiro)
    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.get("/", response_model=list[BarbeiroResponse])
def listar(tenant_id: int = Depends(tenant_id_from_header), db: Session = Depends(get_db)):
    _get_barbearia(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.barbershop_id == tenant_id)
    return query.order_by(Barbeiro.id.asc()).all()


@router.put("/{barbeiro_id}", response_model=BarbeiroResponse)
def atualizar(
    barbeiro_id: int,
    dados: BarbeiroUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _get_barbearia(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id, Barbeiro.barbershop_id == tenant_id)

    barbeiro = query.first()
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro nao encontrado.")

    barbeiro.nome = dados.nome.strip()
    barbeiro.ativo = dados.ativo
    barbeiro.tempo_por_servico = dados.tempo_por_servico
    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.delete("/{barbeiro_id}", status_code=204)
def remover(
    barbeiro_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _get_barbearia(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id, Barbeiro.barbershop_id == tenant_id)

    barbeiro = query.first()
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro nao encontrado.")

    db.delete(barbeiro)
    db.commit()
