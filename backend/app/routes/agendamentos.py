from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.deps import tenant_id_from_header
from app.schemas.agendamento import (
    AgendamentoCreate,
    AgendamentoResponse,
    AgendamentoUpdate,
    AgendamentoStatusUpdate,
)
from app.services.agendamento_service import (
    criar_agendamento,
    listar_agendamentos,
    atualizar_agendamento,
    atualizar_status_agendamento,
    remover_agendamento,
)

router = APIRouter(prefix="/agendamentos")


@router.post("/", response_model=AgendamentoResponse)
def criar(
    dados: AgendamentoCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return criar_agendamento(db, dados, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=list[AgendamentoResponse])
def listar(tenant_id: int = Depends(tenant_id_from_header), db: Session = Depends(get_db)):
    return listar_agendamentos(db, tenant_id=tenant_id)


@router.put("/{agendamento_id}", response_model=AgendamentoResponse)
def atualizar(
    agendamento_id: int,
    dados: AgendamentoUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return atualizar_agendamento(db, agendamento_id, dados, tenant_id=tenant_id)
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "não encontrado" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.patch("/{agendamento_id}/status", response_model=AgendamentoResponse)
def atualizar_status(
    agendamento_id: int,
    dados: AgendamentoStatusUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return atualizar_status_agendamento(db, agendamento_id, dados.status, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{agendamento_id}", status_code=204)
def remover(
    agendamento_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        remover_agendamento(db, agendamento_id, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
