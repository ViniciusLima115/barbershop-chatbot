from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.routes.deps import tenant_id_from_header
from app.schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate

router = APIRouter(prefix="/clientes")


@router.post("/", response_model=ClienteResponse)
def criar(
    dados: ClienteCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    cliente_existente = (
        db.query(Cliente)
        .filter(Cliente.telefone == dados.telefone, Cliente.barbearia_id == tenant_id)
        .first()
    )
    if cliente_existente:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")

    cliente = Cliente(**dados.model_dump(), barbearia_id=tenant_id)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    return cliente


@router.get("/", response_model=list[ClienteResponse])
def listar(tenant_id: int = Depends(tenant_id_from_header), db: Session = Depends(get_db)):
    return (
        db.query(Cliente)
        .filter(Cliente.barbearia_id == tenant_id)
        .order_by(Cliente.id.asc())
        .all()
    )


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar(
    cliente_id: int,
    dados: ClienteUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.id == cliente_id, Cliente.barbearia_id == tenant_id)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    conflito_telefone = (
        db.query(Cliente)
        .filter(
            Cliente.telefone == dados.telefone,
            Cliente.id != cliente_id,
            Cliente.barbearia_id == tenant_id,
        )
        .first()
    )
    if conflito_telefone:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")

    cliente.nome = dados.nome
    cliente.telefone = dados.telefone
    if dados.etapa_atual is not None:
        cliente.etapa_atual = dados.etapa_atual
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{cliente_id}", status_code=204)
def remover(
    cliente_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.id == cliente_id, Cliente.barbearia_id == tenant_id)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    db.delete(cliente)
    db.commit()
