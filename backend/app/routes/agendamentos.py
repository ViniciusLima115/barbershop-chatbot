from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.agendamento import (
    AgendamentoCreate,
    AgendamentoResponse,
    AgendamentoStatusUpdate,
)
from app.services.agendamento_service import criar_agendamento, atualizar_status_agendamento

router = APIRouter(prefix="/agendamentos")


@router.post("/", response_model=AgendamentoResponse)
def criar(dados: AgendamentoCreate, db: Session = Depends(get_db)):
    try:
        return criar_agendamento(db, dados)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{agendamento_id}/status", response_model=AgendamentoResponse)
def atualizar_status(
    agendamento_id: int,
    dados: AgendamentoStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        return atualizar_status_agendamento(db, agendamento_id, dados.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
