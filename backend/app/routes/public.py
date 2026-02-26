from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public import (
    PublicAgendamentoCreate,
    PublicAgendamentoResponse,
    PublicBarbeariaLookupResponse,
)
from app.services.public_booking_service import criar_agendamento_publico, obter_lookup_publico


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/barbearia/{slug}", response_model=PublicBarbeariaLookupResponse)
def lookup_barbearia_publica(
    slug: str,
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    servico_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return obter_lookup_publico(
            db,
            slug=slug,
            data_referencia=data,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agendamentos", response_model=PublicAgendamentoResponse)
def criar_agendamento_public(
    dados: PublicAgendamentoCreate,
    db: Session = Depends(get_db),
):
    try:
        return criar_agendamento_publico(
            db,
            slug=dados.slug,
            cliente_nome=dados.cliente_nome,
            cliente_telefone=dados.cliente_telefone,
            barbeiro_id=dados.barbeiro_id,
            servico_id=dados.servico_id,
            data=dados.data,
            hora_inicio=dados.hora_inicio,
        )
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "nao encontrada" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc
