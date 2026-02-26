import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.routes.deps import require_admin
from app.schemas.barbearia import (
    BarbeariaAdminCreate,
    BarbeariaAdminResponse,
    BarbeariaAdminUpdate,
)

router = APIRouter(prefix="/barbearias", dependencies=[Depends(require_admin)])


def _normalizar_ou_none(valor: str | None) -> str | None:
    if valor is None:
        return None
    texto = valor.strip()
    return texto or None


def _slugify(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.strip().lower()).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "barbearia"


def _gerar_slug_unico(db: Session, nome: str, slug_informado: str | None, *, excluir_id: int | None = None) -> str:
    base = _slugify(slug_informado or nome)
    slug = base
    idx = 2

    while True:
        query = db.query(Barbearia).filter(Barbearia.slug == slug)
        if excluir_id is not None:
            query = query.filter(Barbearia.id != excluir_id)
        conflito = query.first()
        if not conflito:
            return slug
        slug = f"{base}-{idx}"
        idx += 1


@router.get("/", response_model=list[BarbeariaAdminResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Barbearia).order_by(Barbearia.criado_em.desc(), Barbearia.id.desc()).all()


@router.post("/", response_model=BarbeariaAdminResponse)
def criar(dados: BarbeariaAdminCreate, db: Session = Depends(get_db)):
    slug = _gerar_slug_unico(db, dados.nome, dados.slug)
    login = dados.login.strip().lower()
    mega_instance_key = _normalizar_ou_none(dados.mega_instance_key)
    mega_token = _normalizar_ou_none(dados.mega_token)
    whatsapp_number = _normalizar_ou_none(dados.whatsapp_number)

    login_existente = db.query(Barbearia).filter(Barbearia.login == login).first()
    if login_existente:
        raise HTTPException(status_code=400, detail="Ja existe uma barbearia com esse login.")

    if mega_instance_key:
        instance_existente = (
            db.query(Barbearia)
            .filter(Barbearia.mega_instance_key == mega_instance_key)
            .first()
        )
        if instance_existente:
            raise HTTPException(status_code=400, detail="Ja existe barbearia com essa instance_key.")

    if whatsapp_number:
        whatsapp_existente = (
            db.query(Barbearia)
            .filter(Barbearia.whatsapp_number == whatsapp_number)
            .first()
        )
        if whatsapp_existente:
            raise HTTPException(status_code=400, detail="Ja existe barbearia com esse whatsapp_number.")

    barbearia = Barbearia(
        nome=dados.nome.strip(),
        slug=slug,
        login=login,
        senha=dados.senha,
        mega_instance_key=mega_instance_key,
        mega_token=mega_token,
        whatsapp_number=whatsapp_number,
        plano=dados.plano,
        status_manual=dados.status_manual,
        vencimento_em=dados.vencimento_em,
        trial_ativo=dados.trial_ativo,
        trial_fim_em=dados.trial_fim_em if dados.trial_ativo else None,
        ultimo_acesso_em=dados.ultimo_acesso_em,
        pagamento_recusado=dados.pagamento_recusado,
        endereco=dados.endereco.strip(),
    )
    db.add(barbearia)
    db.commit()
    db.refresh(barbearia)
    return barbearia


@router.put("/{barbearia_id}", response_model=BarbeariaAdminResponse)
def atualizar(barbearia_id: int, dados: BarbeariaAdminUpdate, db: Session = Depends(get_db)):
    barbearia = db.query(Barbearia).filter(Barbearia.id == barbearia_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")

    slug = _gerar_slug_unico(db, dados.nome, dados.slug, excluir_id=barbearia_id)
    login = dados.login.strip().lower()
    mega_instance_key = _normalizar_ou_none(dados.mega_instance_key)
    mega_token = _normalizar_ou_none(dados.mega_token)
    whatsapp_number = _normalizar_ou_none(dados.whatsapp_number)

    conflito_login = (
        db.query(Barbearia)
        .filter(Barbearia.login == login, Barbearia.id != barbearia_id)
        .first()
    )
    if conflito_login:
        raise HTTPException(status_code=400, detail="Ja existe outra barbearia com esse login.")

    if mega_instance_key:
        conflito_instance = (
            db.query(Barbearia)
            .filter(
                Barbearia.mega_instance_key == mega_instance_key,
                Barbearia.id != barbearia_id,
            )
            .first()
        )
        if conflito_instance:
            raise HTTPException(status_code=400, detail="Ja existe outra barbearia com essa instance_key.")

    if whatsapp_number:
        conflito_whatsapp = (
            db.query(Barbearia)
            .filter(
                Barbearia.whatsapp_number == whatsapp_number,
                Barbearia.id != barbearia_id,
            )
            .first()
        )
        if conflito_whatsapp:
            raise HTTPException(status_code=400, detail="Ja existe outra barbearia com esse whatsapp_number.")

    barbearia.nome = dados.nome.strip()
    barbearia.slug = slug
    barbearia.login = login
    barbearia.senha = dados.senha
    barbearia.mega_instance_key = mega_instance_key
    barbearia.mega_token = mega_token
    barbearia.whatsapp_number = whatsapp_number
    barbearia.plano = dados.plano
    barbearia.status_manual = dados.status_manual
    barbearia.vencimento_em = dados.vencimento_em
    barbearia.trial_ativo = dados.trial_ativo
    barbearia.trial_fim_em = dados.trial_fim_em if dados.trial_ativo else None
    barbearia.ultimo_acesso_em = dados.ultimo_acesso_em
    barbearia.pagamento_recusado = dados.pagamento_recusado
    barbearia.endereco = dados.endereco.strip()
    db.commit()
    db.refresh(barbearia)
    return barbearia


@router.delete("/{barbearia_id}", status_code=204)
def remover(barbearia_id: int, db: Session = Depends(get_db)):
    barbearia = db.query(Barbearia).filter(Barbearia.id == barbearia_id).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia nao encontrada.")

    db.delete(barbearia)
    db.commit()
