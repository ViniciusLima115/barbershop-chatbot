import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.servico import Servico
from app.routes.deps import tenant_id_from_header
from app.schemas.servico import ServicoCreate, ServicoResponse, ServicoUpdate

router = APIRouter(prefix="/servicos")
logger = logging.getLogger(__name__)


@router.post("/", response_model=ServicoResponse)
def criar(
    dados: ServicoCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    servico = Servico(**dados.model_dump(), estabelecimento_id=tenant_id)

    try:
        db.add(servico)
        db.commit()
        db.refresh(servico)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Erro ao criar servico (tenant_id=%s)", tenant_id)
        raise HTTPException(status_code=500, detail="Erro interno ao salvar servico.") from exc

    return servico


@router.get("/", response_model=list[ServicoResponse])
def listar(tenant_id: int = Depends(tenant_id_from_header), db: Session = Depends(get_db)):
    try:
        return (
            db.query(Servico)
            .filter(Servico.estabelecimento_id == tenant_id)
            .order_by(Servico.id.asc())
            .all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Erro ao listar servicos (tenant_id=%s)", tenant_id)
        raise HTTPException(status_code=500, detail="Erro interno ao listar servicos.") from exc


@router.put("/{servico_id}", response_model=ServicoResponse)
def atualizar(
    servico_id: int,
    dados: ServicoUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    servico = (
        db.query(Servico)
        .filter(Servico.id == servico_id, Servico.estabelecimento_id == tenant_id)
        .first()
    )
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    servico.nome = dados.nome
    servico.duracao_minutos = dados.duracao_minutos
    servico.preco = dados.preco
    servico.pagamento_adiantado_obrigatorio = dados.pagamento_adiantado_obrigatorio
    servico.advance_payment_type = dados.advance_payment_type
    servico.advance_payment_amount = dados.advance_payment_amount
    servico.payment_description_override = dados.payment_description_override
    db.commit()
    db.refresh(servico)
    return servico


@router.delete("/{servico_id}", status_code=204)
def remover(
    servico_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    servico = (
        db.query(Servico)
        .filter(Servico.id == servico_id, Servico.estabelecimento_id == tenant_id)
        .first()
    )
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    db.delete(servico)
    db.commit()
