from datetime import date, datetime
import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import RATE_LIMIT_PAYMENT_STATUS, RATE_LIMIT_PUBLIC, limiter
from app.models.agendamento import Agendamento as AgendamentoModel
from app.models.pagamento import Pagamento
from app.models.servico import Servico
from app.schemas.public import (
    PublicAgendamentoCreate,
    PublicAgendamentoResponse,
    PublicBarbeiroItem,
    PublicEstabelecimentoLookupResponse,
    PublicPagamentoInitResponse,
    PublicPagamentoStatusResponse,
    PublicServicoItem,
)
from app.services.public_booking_service import (
    criar_agendamento_publico,
    listar_barbeiros_publico,
    listar_horarios_disponiveis_publico,
    listar_servicos_publico,
    obter_lookup_publico,
    obter_lookup_publico_por_id,
    servico_exige_pagamento_adiantado_publico,
)
from app.time_utils import utcnow_naive
from app.services.agendamento_service import obter_payload_email_confirmacao
from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_PENDING,
)
from app.services.payments.payment_service import (
    apply_payment_snapshot_from_service,
    start_checkout_for_booking,
    validate_service_advance_payment_config,
)
from app.services.payments.webhook_service import sync_payment_status_from_provider
from app.services.email_service import send_email_payload
from app.services.notificacao_inapp_service import task_notificacao_novo_agendamento


router = APIRouter(prefix="/public", tags=["public"])
logger = logging.getLogger(__name__)


def _normalizar_telefone_storage(telefone: str) -> str:
    digits = re.sub(r"\D", "", telefone or "")
    if len(digits) >= 12 and digits.startswith("55"):
        digits = digits[2:]
    return digits


@router.get("/estabelecimento/{slug}", response_model=PublicEstabelecimentoLookupResponse)
@limiter.limit(RATE_LIMIT_PUBLIC)
def lookup_barbearia_publica(
    request: Request,
    slug: str,
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    servico_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return obter_lookup_publico(
            db,
            slug=slug,
            data_referencia=data,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro interno ao carregar estabelecimento.") from exc


@router.get("/estabelecimento-id/{estabelecimento_id}", response_model=PublicEstabelecimentoLookupResponse)
@limiter.limit(RATE_LIMIT_PUBLIC)
def lookup_barbearia_publica_por_id(
    request: Request,
    estabelecimento_id: int,
    data: date | None = Query(default=None),
    barbeiro_id: int | None = Query(default=None),
    servico_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return obter_lookup_publico_por_id(
            db,
            estabelecimento_id=estabelecimento_id,
            data_referencia=data,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro interno ao carregar estabelecimento.") from exc


@router.get("/servicos", response_model=list[PublicServicoItem])
@limiter.limit(RATE_LIMIT_PUBLIC)
def listar_servicos_public(
    request: Request,
    estabelecimento_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return listar_servicos_publico(db, estabelecimento_id=estabelecimento_id)


@router.get("/barbeiros", response_model=list[PublicBarbeiroItem])
@limiter.limit(RATE_LIMIT_PUBLIC)
def listar_barbeiros_public(
    request: Request,
    estabelecimento_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return listar_barbeiros_publico(db, estabelecimento_id=estabelecimento_id)


@router.get("/horarios-disponiveis")
@limiter.limit(RATE_LIMIT_PUBLIC)
def horarios_disponiveis_public(
    request: Request,
    estabelecimento_id: int = Query(...),
    barbeiro_id: int = Query(...),
    servico_id: int = Query(...),
    data: date = Query(...),
    db: Session = Depends(get_db),
):
    return listar_horarios_disponiveis_publico(
        db,
        estabelecimento_id=estabelecimento_id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_referencia=data,
    )


@router.post("/agendamentos", response_model=PublicAgendamentoResponse)
@limiter.limit(RATE_LIMIT_PUBLIC)
def criar_agendamento_public(
    request: Request,
    dados: PublicAgendamentoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        exige_pagamento, _, _ = servico_exige_pagamento_adiantado_publico(
            db,
            slug=dados.slug,
            estabelecimento_id=dados.estabelecimento_id,
            servico_id=dados.servico_id,
        )
        if exige_pagamento:
            raise HTTPException(
                status_code=409,
                detail="Este servico exige pagamento adiantado. Inicie o checkout para reservar o horario.",
            )
        agendamento = criar_agendamento_publico(
            db,
            slug=dados.slug,
            estabelecimento_id=dados.estabelecimento_id,
            cliente_nome=dados.cliente_nome,
            cliente_telefone=dados.cliente_telefone,
            cliente_email=dados.cliente_email,
            barbeiro_id=dados.barbeiro_id,
            servico_id=dados.servico_id,
            data=dados.data,
            hora_inicio=dados.hora_inicio,
        )
        payload = obter_payload_email_confirmacao(db, agendamento_id=agendamento["id"])
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        background_tasks.add_task(task_notificacao_novo_agendamento, agendamento["id"])
        return agendamento
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "nao encontrada" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro interno ao criar agendamento.") from exc


@router.post("/agendamentos/pagamento/iniciar", response_model=PublicPagamentoInitResponse)
@limiter.limit(RATE_LIMIT_PUBLIC)
def iniciar_pagamento_agendamento_public(
    request: Request,
    dados: PublicAgendamentoCreate,
    db: Session = Depends(get_db),
):
    try:
        exige_pagamento, _, tenant_id = servico_exige_pagamento_adiantado_publico(
            db,
            slug=dados.slug,
            estabelecimento_id=dados.estabelecimento_id,
            servico_id=dados.servico_id,
        )
        if not exige_pagamento:
            raise HTTPException(status_code=400, detail="Este servico nao exige pagamento adiantado.")

        servico = (
            db.query(Servico)
            .filter(
                Servico.id == dados.servico_id,
                Servico.estabelecimento_id == tenant_id,
            )
            .first()
        )
        if not servico:
            raise HTTPException(status_code=404, detail="Servico nao encontrado.")
        _, _, amount = validate_service_advance_payment_config(servico)
        if amount is None:
            raise HTTPException(status_code=400, detail="Configuracao de pagamento do servico invalida.")

        inicio = datetime.combine(dados.data, dados.hora_inicio.replace(second=0, microsecond=0))
        telefone_normalizado = _normalizar_telefone_storage(dados.cliente_telefone)
        existente = (
            db.query(AgendamentoModel)
            .filter(
                AgendamentoModel.estabelecimento_id == tenant_id,
                AgendamentoModel.profissional_id == dados.barbeiro_id,
                AgendamentoModel.servico_id == dados.servico_id,
                AgendamentoModel.cliente_telefone == telefone_normalizado,
                AgendamentoModel.data_hora_inicio == inicio,
                AgendamentoModel.status == "pending_payment",
            )
            .order_by(AgendamentoModel.id.desc())
            .with_for_update()
            .first()
        )
        if existente:
            if not existente.payment_required_snapshot:
                apply_payment_snapshot_from_service(existente, servico)
                db.commit()
                db.refresh(existente)
            pagamento_existente = db.query(Pagamento).filter(Pagamento.agendamento_id == existente.id).first()
            if (
                pagamento_existente
                and pagamento_existente.checkout_url
                and pagamento_existente.status == PAYMENT_STATUS_PENDING
                and pagamento_existente.expires_at
                and pagamento_existente.expires_at > utcnow_naive()
            ):
                return {
                    "agendamento_id": existente.id,
                    "external_reference": pagamento_existente.external_reference,
                    "preference_id": pagamento_existente.preference_id or "",
                    "checkout_url": pagamento_existente.checkout_url,
                    "amount": pagamento_existente.amount,
                    "pagamento_status": pagamento_existente.status,
                    "agendamento_status": existente.status,
                    "expires_at": pagamento_existente.expires_at,
                }
            pagamento_retentativa = start_checkout_for_booking(
                db,
                booking=existente,
                provider=PAYMENT_PROVIDER_MERCADO_PAGO,
                payer_name=existente.cliente_nome,
                payer_email=existente.cliente_email,
                payer_phone=existente.cliente_telefone,
            )
            return {
                "agendamento_id": existente.id,
                "external_reference": pagamento_retentativa.external_reference,
                "preference_id": pagamento_retentativa.preference_id or "",
                "checkout_url": pagamento_retentativa.checkout_url or "",
                "amount": float(pagamento_retentativa.amount or amount),
                "pagamento_status": pagamento_retentativa.status,
                "agendamento_status": existente.status,
                "expires_at": pagamento_retentativa.expires_at,
            }

        agendamento = criar_agendamento_publico(
            db,
            slug=dados.slug,
            estabelecimento_id=dados.estabelecimento_id,
            cliente_nome=dados.cliente_nome,
            cliente_telefone=dados.cliente_telefone,
            cliente_email=dados.cliente_email,
            barbeiro_id=dados.barbeiro_id,
            servico_id=dados.servico_id,
            data=dados.data,
            hora_inicio=dados.hora_inicio,
            status_inicial="pending_payment",
            pagamento_adiantado_exigido=True,
            enviar_confirmacao_apos_criacao=False,
            agendar_lembretes=False,
        )
        agendamento_model = (
            db.query(AgendamentoModel)
            .filter(AgendamentoModel.id == agendamento["id"])
            .first()
        )
        if not agendamento_model:
            raise HTTPException(status_code=500, detail="Falha ao carregar agendamento criado.")

        apply_payment_snapshot_from_service(agendamento_model, servico)
        db.commit()
        db.refresh(agendamento_model)

        pagamento = start_checkout_for_booking(
            db,
            booking=agendamento_model,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            payer_name=dados.cliente_nome,
            payer_email=dados.cliente_email,
            payer_phone=dados.cliente_telefone,
        )

        return {
            "agendamento_id": agendamento["id"],
            "external_reference": pagamento.external_reference,
            "preference_id": pagamento.preference_id or "",
            "checkout_url": pagamento.checkout_url or "",
            "amount": float(pagamento.amount or amount),
            "pagamento_status": pagamento.status,
            "agendamento_status": agendamento_model.status,
            "expires_at": pagamento.expires_at,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro interno ao iniciar pagamento.") from exc


@router.get("/pagamentos/status", response_model=PublicPagamentoStatusResponse)
@limiter.limit(RATE_LIMIT_PAYMENT_STATUS)
def consultar_status_pagamento(
    request: Request,
    external_reference: str = Query(...),
    db: Session = Depends(get_db),
):
    pagamento = db.query(Pagamento).filter(Pagamento.external_reference == external_reference).first()
    if not pagamento or not pagamento.agendamento:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    try:
        pagamento, _ = sync_payment_status_from_provider(db, payment=pagamento)
    except Exception as exc:
        logger.warning("Falha ao sincronizar status publico do pagamento %s: %s", pagamento.id, exc)
        db.rollback()

    return {
        "external_reference": pagamento.external_reference,
        "agendamento_id": pagamento.agendamento_id,
        "pagamento_status": pagamento.status,
        "agendamento_status": pagamento.agendamento.status,
        "amount": pagamento.amount,
    }
