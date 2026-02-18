from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.barbeiro import Barbeiro
from app.schemas.barbeiro import BarbeiroCreate, BarbeiroResponse

router = APIRouter(prefix="/barbeiros")


@router.post("/", response_model=BarbeiroResponse)
def criar(dados: BarbeiroCreate, db: Session = Depends(get_db)):
    barbeiro = Barbeiro(**dados.dict())

    db.add(barbeiro)
    db.commit()
    db.refresh(barbeiro)

    return barbeiro


@router.get("/", response_model=list[BarbeiroResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Barbeiro).all()