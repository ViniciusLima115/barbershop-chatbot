import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.notificacao_service import processar_lembretes_pendentes


router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/reminders/process")
def processar_reminders(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    limite: int = 100,
    db: Session = Depends(get_db),
):
    token_esperado = os.getenv("INTERNAL_REMINDER_TOKEN")
    if token_esperado and x_internal_token != token_esperado:
        raise HTTPException(status_code=401, detail="Token interno invalido.")

    return processar_lembretes_pendentes(db, limite=limite)
