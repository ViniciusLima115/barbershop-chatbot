from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.servico import Servico
from app.schemas.servico import ServicoCreate, ServicoResponse

router = APIRouter(prefix="/servicos")


@router.post("/", response_model=ServicoResponse)
def criar(dados: ServicoCreate, db: Session = Depends(get_db)):
    servico = Servico(**dados.dict())

    db.add(servico)
    db.commit()
    db.refresh(servico)

    return servico


@router.get("/", response_model=list[ServicoResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Servico).all()