from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.agendamento import AgendamentoCreate, AgendamentoResponse
from app.services.agendamento_service import criar_agendamento

router = APIRouter(prefix="/agendamentos")


@router.post("/", response_model=AgendamentoResponse)
def criar(dados: AgendamentoCreate, db: Session = Depends(get_db)):
    return criar_agendamento(db, dados)