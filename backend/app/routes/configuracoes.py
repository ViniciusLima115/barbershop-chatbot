from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import get_current_claims
from app.schemas.configuracoes import NotificacoesUpdate, PerfilUpdate, SenhaUpdate, TemaUpdate
from app.security import TokenClaims, hash_senha, verificar_senha

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])


def _get_tenant_estabelecimento(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> tuple[TokenClaims, Estabelecimento, Session]:
    if claims.is_admin:
        raise HTTPException(status_code=403, detail="Endpoint exclusivo para tenants.")
    est = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return claims, est, db


@router.patch("/perfil")
def atualizar_perfil(
    dados: PerfilUpdate,
    pair: tuple[TokenClaims, Estabelecimento, Session] = Depends(_get_tenant_estabelecimento),
):
    _, est, db = pair
    if dados.slug is not None and dados.slug != est.slug:
        existente = db.query(Estabelecimento).filter(
            Estabelecimento.slug == dados.slug,
            Estabelecimento.id != est.id,
        ).first()
        if existente:
            raise HTTPException(status_code=409, detail="Slug já está em uso.")
        est.slug = dados.slug
    if dados.nome is not None:
        est.nome = dados.nome
    if dados.endereco is not None:
        est.endereco = dados.endereco
    if dados.whatsapp_number is not None:
        est.whatsapp_number = dados.whatsapp_number
    db.commit()
    return {"detail": "Perfil atualizado."}


@router.patch("/senha")
def trocar_senha(
    dados: SenhaUpdate,
    pair: tuple[TokenClaims, Estabelecimento, Session] = Depends(_get_tenant_estabelecimento),
):
    _, est, db = pair
    if not est.senha or not verificar_senha(dados.senha_atual, est.senha):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    est.senha = hash_senha(dados.nova_senha)
    db.commit()
    return {"detail": "Senha alterada com sucesso."}


@router.patch("/tema")
def atualizar_tema(
    dados: TemaUpdate,
    pair: tuple[TokenClaims, Estabelecimento, Session] = Depends(_get_tenant_estabelecimento),
):
    _, est, db = pair
    if dados.accent_color is not None:
        est.accent_color = dados.accent_color
    if dados.bg_color is not None:
        est.bg_color = dados.bg_color
    if dados.logo_url is not None:
        est.logo_url = dados.logo_url
    db.commit()
    return {"detail": "Tema atualizado."}


@router.patch("/notificacoes")
def atualizar_notificacoes(
    dados: NotificacoesUpdate,
    pair: tuple[TokenClaims, Estabelecimento, Session] = Depends(_get_tenant_estabelecimento),
):
    _, est, db = pair
    if dados.notif_ativo is not None:
        est.notif_ativo = dados.notif_ativo
    if dados.notif_horas_antes is not None:
        est.notif_horas_antes = dados.notif_horas_antes
    db.commit()
    return {"detail": "Preferências de notificação atualizadas."}
