from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteResponse

router = APIRouter(prefix="/clientes")


@router.post("/", response_model=ClienteResponse)
def criar(dados: ClienteCreate, db: Session = Depends(get_db)):
    cliente_existente = db.query(Cliente).filter(Cliente.telefone == dados.telefone).first()
    if cliente_existente:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado")

    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    return cliente


@router.get("/", response_model=list[ClienteResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Cliente).order_by(Cliente.id.asc()).all()
