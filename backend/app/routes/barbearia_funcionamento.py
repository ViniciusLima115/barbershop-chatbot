from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.routes.deps import tenant_id_from_header
from app.schemas.barbearia import BarbeariaFuncionamento
from app.services.barbershop_hours_service import normalize_working_hours


router = APIRouter(prefix="/barbearias/me/funcionamento", tags=["barbearias"])


@router.get("", response_model=BarbeariaFuncionamento)
def obter_funcionamento(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")
    result = normalize_working_hours(barbearia.horarios_funcionamento)
    result["intervalo_minutos"] = getattr(barbearia, "intervalo_minutos", 30) or 30
    return result


@router.put("", response_model=BarbeariaFuncionamento)
def atualizar_funcionamento(
    dados: BarbeariaFuncionamento,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")

    if dados.intervalo_minutos is not None:
        valor = max(5, min(120, dados.intervalo_minutos))  # clamp 5–120
        barbearia.intervalo_minutos = valor

    barbearia.horarios_funcionamento = dados.model_dump(exclude={"intervalo_minutos"})
    db.commit()
    db.refresh(barbearia)
    result = normalize_working_hours(barbearia.horarios_funcionamento)
    result["intervalo_minutos"] = getattr(barbearia, "intervalo_minutos", 30) or 30
    return result
