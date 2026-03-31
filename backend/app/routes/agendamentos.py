from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agendamento import Agendamento as AgendamentoModel
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import tenant_id_from_header
from app.schemas.agendamento import (
    AgendamentoCreate,
    AgendamentoPatch,
    AgendamentoRemarcacaoRequest,
    AgendamentoResponse,
    AgendamentoStatusUpdate,
    AgendamentoTokenDataResponse,
    AgendamentoUpdate,
)
from app.services.agendamento_service import (
    _serializar_agendamento,
    aplicar_patch_agendamento,
    atualizar_agendamento,
    atualizar_status_agendamento,
    atualizar_status_agendamento_por_token,
    criar_agendamento,
    listar_agendamentos,
    obter_dados_agendamento_por_token,
    obter_payload_email_confirmacao,
    obter_payload_email_status,
    remarcar_agendamento_por_token,
    remover_agendamento,
)
from app.services.email_service import send_email_payload
from app.services.notificacao_inapp_service import (
    task_notificacao_novo_agendamento,
    task_notificacao_confirmado,
)
from datetime import datetime as _datetime, timezone as _timezone

from app.repositories import notificacao_repository as notif_repo
from app.schemas.notificacao import ConfirmarPresencaPayload


router = APIRouter(prefix="/agendamentos")


LIMITE_AGENDAMENTOS_GRATIS = 30


@router.post("/", response_model=AgendamentoResponse)
def criar(
    dados: AgendamentoCreate,
    background_tasks: BackgroundTasks,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    # Verificar limite mensal para plano Gratis
    estab = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if estab and (estab.plano or "gratis").lower() == "gratis":
        hoje = date.today()
        inicio_mes = hoje.replace(day=1)
        total_mes = (
            db.query(AgendamentoModel)
            .filter(
                AgendamentoModel.barbearia_id == tenant_id,
                AgendamentoModel.data >= inicio_mes,
            )
            .count()
        )
        if total_mes >= LIMITE_AGENDAMENTOS_GRATIS:
            raise HTTPException(
                status_code=403,
                detail=f"Limite de {LIMITE_AGENDAMENTOS_GRATIS} agendamentos por mes atingido no plano Gratis. Faca o upgrade para continuar.",
            )

    try:
        agendamento = criar_agendamento(db, dados, tenant_id=tenant_id)
        payload = obter_payload_email_confirmacao(db, agendamento_id=agendamento["id"])
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        background_tasks.add_task(task_notificacao_novo_agendamento, agendamento["id"])
        return agendamento
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=list[AgendamentoResponse])
def listar(
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    return listar_agendamentos(
        db,
        tenant_id=tenant_id,
        data=data,
        barbeiro_id=barbeiro_id,
    )


@router.get("/{token}/dados", response_model=AgendamentoTokenDataResponse)
def dados_por_token(
    token: str,
    db: Session = Depends(get_db),
):
    try:
        return obter_dados_agendamento_por_token(db, token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{token}/confirmar", response_model=AgendamentoTokenDataResponse)
def confirmar_por_token(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        dados = atualizar_status_agendamento_por_token(db, token, "confirmado")
        payload = obter_payload_email_status(db, token=token, tipo="confirmado")
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        # obtém o id do agendamento para a task
        ag = db.query(AgendamentoModel).filter(AgendamentoModel.confirmation_token == token).first()
        if ag:
            background_tasks.add_task(task_notificacao_confirmado, ag.id)
        return dados
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "inválido" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.post("/{token}/cancelar", response_model=AgendamentoTokenDataResponse)
def cancelar_por_token(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        dados = atualizar_status_agendamento_por_token(db, token, "cancelado")
        payload = obter_payload_email_status(db, token=token, tipo="cancelado")
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        return dados
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "inválido" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.post("/{token}/reagendar", response_model=AgendamentoTokenDataResponse)
def reagendar_por_token(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        dados = atualizar_status_agendamento_por_token(db, token, "reagendamento_solicitado")
        payload = obter_payload_email_status(db, token=token, tipo="reagendamento_solicitado")
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        return dados
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "inválido" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.put("/{token}/remarcar", response_model=AgendamentoTokenDataResponse)
def remarcar_por_token(
    token: str,
    dados: AgendamentoRemarcacaoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        resultado = remarcar_agendamento_por_token(db, token, dados.data_hora_inicio)
        payload = obter_payload_email_status(db, token=token, tipo="confirmado")
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        return resultado
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "inválido" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.put("/{agendamento_id}", response_model=AgendamentoResponse)
def atualizar(
    agendamento_id: int,
    dados: AgendamentoUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return atualizar_agendamento(db, agendamento_id, dados, tenant_id=tenant_id)
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "não encontrado" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.patch("/{agendamento_id}/status", response_model=AgendamentoResponse)
def atualizar_status(
    agendamento_id: int,
    dados: AgendamentoStatusUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return atualizar_status_agendamento(db, agendamento_id, dados.status, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{agendamento_id}", response_model=AgendamentoResponse)
def patch_agendamento(
    agendamento_id: int,
    dados: AgendamentoPatch,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        return aplicar_patch_agendamento(
            db,
            agendamento_id=agendamento_id,
            dados=dados,
            tenant_id=tenant_id,
        )
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "não encontrado" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc


@router.post("/{agendamento_id}/confirmar-presenca", response_model=AgendamentoResponse)
def confirmar_presenca(
    agendamento_id: int,
    dados: ConfirmarPresencaPayload,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    agendamento = (
        db.query(AgendamentoModel)
        .filter(AgendamentoModel.id == agendamento_id, AgendamentoModel.estabelecimento_id == tenant_id)
        .first()
    )
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    agendamento.status = "compareceu" if dados.compareceu else "no_show"
    agendamento.compareceu_em = _datetime.now(_timezone.utc)

    notif_repo.marcar_lida_por_agendamento_e_tipo(
        db, agendamento_id=agendamento_id, tipo="pendente_confirmacao"
    )

    db.commit()
    db.refresh(agendamento)
    return _serializar_agendamento(agendamento)


@router.delete("/{agendamento_id}", status_code=204)
def remover(
    agendamento_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    try:
        remover_agendamento(db, agendamento_id, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
