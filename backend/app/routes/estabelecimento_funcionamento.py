from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import tenant_id_from_header
from app.schemas.barbearia import BarbeariaFuncionamento
from app.services.estabelecimento_hours_service import normalize_working_hours


router = APIRouter(prefix="/estabelecimentos/me/funcionamento", tags=["estabelecimentos"])


@router.get("", response_model=BarbeariaFuncionamento)
def obter_funcionamento(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    result = normalize_working_hours(estabelecimento.horarios_funcionamento)
    result["intervalo_minutos"] = getattr(estabelecimento, "intervalo_minutos", 30) or 30
    return result


@router.put("", response_model=BarbeariaFuncionamento)
def atualizar_funcionamento(
    dados: BarbeariaFuncionamento,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

    if dados.intervalo_minutos is not None:
        valor = max(5, min(120, dados.intervalo_minutos))  # clamp 5–120
        estabelecimento.intervalo_minutos = valor

    estabelecimento.horarios_funcionamento = dados.model_dump(exclude={"intervalo_minutos"})
    db.commit()
    db.refresh(estabelecimento)
    result = normalize_working_hours(estabelecimento.horarios_funcionamento)
    result["intervalo_minutos"] = getattr(estabelecimento, "intervalo_minutos", 30) or 30
    return result
