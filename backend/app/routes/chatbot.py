from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.deps import tenant_id_from_header
from app.schemas.chatbot import ChatbotMensagem
from app.services.chatbot_service import responder_mensagem

router = APIRouter(prefix="/chatbot")


@router.post("/mensagem")
def mensagem(
    dados: ChatbotMensagem,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    resposta = responder_mensagem(
        db,
        dados.telefone,
        dados.mensagem,
        tenant_id=tenant_id,
    )

    return {"resposta": resposta}
