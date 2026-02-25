from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.schemas.barbeiro import BarbeiroCreate, BarbeiroResponse, BarbeiroUpdate

router = APIRouter(prefix="/barbeiros")
MAX_BARBEIROS_PREMIUM = 3


def _tenant_id_from_header(x_barbearia_id: Annotated[str | None, Header(alias="X-Barbearia-Id")] = None) -> int:
    if not x_barbearia_id:
        raise HTTPException(status_code=400, detail="X-Barbearia-Id obrigatorio.")
    try:
        return int(x_barbearia_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Barbearia-Id invalido.") from exc


def _ensure_premium(db: Session, tenant_id: int) -> Barbearia:
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")

    if (barbearia.plano or "basico").lower() != "premium":
        raise HTTPException(
            status_code=403,
            detail="Gestao de barbeiros disponivel apenas para plano premium.",
        )

    return barbearia


@router.post("/", response_model=BarbeiroResponse)
def criar(
    dados: BarbeiroCreate,
    tenant_id: int = Depends(_tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _ensure_premium(db, tenant_id)

    total = db.query(Barbeiro).filter(Barbeiro.barbershop_id == tenant_id).count()
    if total >= MAX_BARBEIROS_PREMIUM:
        raise HTTPException(status_code=400, detail="Limite de 3 barbeiros ativos atingido.")

    payload = {"nome": dados.nome.strip(), "barbershop_id": tenant_id}

    barbeiro = Barbeiro(**payload)

    db.add(barbeiro)
    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.get("/", response_model=list[BarbeiroResponse])
def listar(tenant_id: int = Depends(_tenant_id_from_header), db: Session = Depends(get_db)):
    _ensure_premium(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.barbershop_id == tenant_id)
    return query.order_by(Barbeiro.id.asc()).all()


@router.put("/{barbeiro_id}", response_model=BarbeiroResponse)
def atualizar(
    barbeiro_id: int,
    dados: BarbeiroUpdate,
    tenant_id: int = Depends(_tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _ensure_premium(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id, Barbeiro.barbershop_id == tenant_id)

    barbeiro = query.first()
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro nao encontrado.")

    barbeiro.nome = dados.nome.strip()
    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.delete("/{barbeiro_id}", status_code=204)
def remover(
    barbeiro_id: int,
    tenant_id: int = Depends(_tenant_id_from_header),
    db: Session = Depends(get_db),
):
    _ensure_premium(db, tenant_id)
    query = db.query(Barbeiro).filter(Barbeiro.id == barbeiro_id, Barbeiro.barbershop_id == tenant_id)

    barbeiro = query.first()
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro nao encontrado.")

    db.delete(barbeiro)
    db.commit()
