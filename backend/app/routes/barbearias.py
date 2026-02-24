from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.barbearia import Barbearia
from app.schemas.barbearia import (
    BarbeariaAdminCreate,
    BarbeariaAdminResponse,
    BarbeariaAdminUpdate,
)

router = APIRouter(prefix="/barbearias")


@router.get("/", response_model=list[BarbeariaAdminResponse])
def listar(db: Session = Depends(get_db)):
    return db.query(Barbearia).order_by(Barbearia.criado_em.desc(), Barbearia.id.desc()).all()


@router.post("/", response_model=BarbeariaAdminResponse)
def criar(dados: BarbeariaAdminCreate, db: Session = Depends(get_db)):
    login = dados.login.strip().lower()
    login_existente = db.query(Barbearia).filter(Barbearia.login == login).first()
    if login_existente:
        raise HTTPException(status_code=400, detail="Ja existe uma barbearia com esse login.")

    barbearia = Barbearia(
        nome=dados.nome.strip(),
        login=login,
        senha=dados.senha,
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

    login = dados.login.strip().lower()
    conflito_login = (
        db.query(Barbearia)
        .filter(Barbearia.login == login, Barbearia.id != barbearia_id)
        .first()
    )
    if conflito_login:
        raise HTTPException(status_code=400, detail="Ja existe outra barbearia com esse login.")

    barbearia.nome = dados.nome.strip()
    barbearia.login = login
    barbearia.senha = dados.senha
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
