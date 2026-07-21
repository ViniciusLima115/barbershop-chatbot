from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estabelecimento import Estabelecimento
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
    # Chatbot nao disponivel no plano Gratis
    barbearia = db.query(Estabelecimento.plano).filter(Estabelecimento.id == tenant_id).first()
    plano = (barbearia.plano or "gratis").lower() if barbearia else "gratis"
    if plano == "gratis":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="O chatbot automatico nao esta disponivel no plano Gratis. Faca o upgrade para o plano Basico ou Premium.",
        )

    resposta = responder_mensagem(
        db,
        dados.telefone,
        dados.mensagem,
        tenant_id=tenant_id,
    )

    return {"resposta": resposta}
