from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import notificacao_repository as repo
from app.routes.deps import tenant_id_from_header
from app.schemas.notificacao import NotificacaoResponse

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


@router.get("/", response_model=list[NotificacaoResponse])
def listar_notificacoes(
    apenas_nao_lidas: bool = False,
    limite: int = 30,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    return repo.listar(db, estabelecimento_id=tenant_id, apenas_nao_lidas=apenas_nao_lidas, limite=limite)


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_lida(
    notificacao_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    notif = repo.marcar_lida(db, notificacao_id=notificacao_id, estabelecimento_id=tenant_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/marcar-todas-lidas")
def marcar_todas_lidas(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    count = repo.marcar_todas_lidas(db, estabelecimento_id=tenant_id)
    db.commit()
    return {"marcadas": count}
