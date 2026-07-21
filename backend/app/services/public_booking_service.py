import os
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.barbeiro import Barbeiro
from app.models.estabelecimento import Estabelecimento
from app.models.servico import Servico
from app.repositories.booking_repository import BookingRepository
from app.repositories.tenant_repository import TenantRepository
from app.services.agenda_service import gerar_horarios_disponiveis
from app.services.estabelecimento_hours_service import build_day_slots, is_within_working_hours
from app.services.notificacao_service import (
    agendar_lembretes_agendamento,
    enviar_mensagem_whatsapp,
    montar_mensagem_confirmacao,
)


BOOKING_PUBLIC_BASE_URL = os.getenv("BOOKING_PUBLIC_BASE_URL", "http://127.0.0.1:3000")
_TZ_BRASIL = ZoneInfo("America/Sao_Paulo")
STATUS_VALIDOS = {"pending_payment", "pendente", "confirmado", "cancelado", "failed", "reagendamento_solicitado", "compareceu", "no_show", "expired"}


def _normalizar_texto(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def _normalizar_telefone_storage(telefone: str) -> str:
    """Normaliza para armazenamento: remove caracteres não numéricos e DDI brasileiro (55)."""
    digits = re.sub(r"\D", "", telefone or "")
    if len(digits) >= 12 and digits.startswith("55"):
        digits = digits[2:]
    return digits


def _normalizar_telefone_whatsapp(telefone: str) -> str:
    """Normaliza para WhatsApp: garante DDI brasileiro (55)."""
    digits = re.sub(r"\D", "", telefone or "")
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits


def _eh_saudacao(texto: str) -> bool:
    return _normalizar_texto(texto) in {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "menu"}


def _normalizar_status_saida(status: str | None) -> str:
    valor = (status or "").strip().lower()
    if valor in STATUS_VALIDOS:
        return valor
    return "pendente"


def montar_link_agendamento(slug: str) -> str:
    base = BOOKING_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{slug}"


def montar_link_agendamento_por_id(estabelecimento_id: int) -> str:
    base = BOOKING_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/agendar/{estabelecimento_id}"


def montar_mensagem_link_agendamento(nome_barbearia: str, slug: str) -> str:
    return (
        f"Oi. Para agendar na {nome_barbearia}, use este link:\n"
        f"{montar_link_agendamento(slug)}"
    )


def montar_mensagem_link_agendamento_por_id(nome_barbearia: str, estabelecimento_id: int) -> str:
    return (
        f"Oi. Para agendar na {nome_barbearia}, use este link:\n"
        f"{montar_link_agendamento_por_id(estabelecimento_id)}"
    )


def deve_responder_com_link(texto: str) -> bool:
    msg = _normalizar_texto(texto)
    if _eh_saudacao(msg):
        return True
    return len(msg) <= 20


def _duracao_servico(
    *,
    barbeiro: Barbeiro,
    servico: Servico,
) -> int:
    mapa = barbeiro.tempo_por_servico if isinstance(barbeiro.tempo_por_servico, dict) else {}
    custom = mapa.get(str(servico.id))
    if isinstance(custom, int) and custom > 0:
        return custom
    return servico.duracao_minutos


def _obter_barbearia(
    db: Session,
    *,
    slug: str | None = None,
    estabelecimento_id: int | None = None,
) -> Estabelecimento | None:
    tenant_repo = TenantRepository(db)
    if estabelecimento_id:
        return tenant_repo.get_by_id(estabelecimento_id)
    if slug:
        return tenant_repo.get_by_slug(slug)
    return None


def listar_barbeiros_publico(db: Session, *, estabelecimento_id: int) -> list[Barbeiro]:
    return BookingRepository(db).list_public_barbeiros(estabelecimento_id, only_active=True)


def listar_servicos_publico(db: Session, *, estabelecimento_id: int) -> list[dict]:
    barbearia = _obter_barbearia(db, estabelecimento_id=estabelecimento_id)
    if not barbearia:
        return []
    servicos = BookingRepository(db).list_public_servicos(estabelecimento_id)
    return [_serializar_servico_publico(servico, barbearia) for servico in servicos]


def _servico_exige_pagamento_adiantado(servico: Servico, barbearia: Estabelecimento) -> bool:
    return bool(getattr(servico, "pagamento_adiantado_obrigatorio", False))


def _serializar_servico_publico(servico: Servico, barbearia: Estabelecimento) -> dict:
    return {
        "id": servico.id,
        "nome": servico.nome,
        "duracao": servico.duracao_minutos,
        "preco": float(servico.preco),
        "pagamento_adiantado_obrigatorio": bool(getattr(servico, "pagamento_adiantado_obrigatorio", False)),
        "pagamento_adiantado_obrigatorio_efetivo": _servico_exige_pagamento_adiantado(servico, barbearia),
        "advance_payment_type": getattr(servico, "advance_payment_type", None),
        "advance_payment_amount": (
            float(servico.advance_payment_amount)
            if getattr(servico, "advance_payment_amount", None) is not None
            else None
        ),
    }


def listar_horarios_disponiveis_publico(
    db: Session,
    *,
    estabelecimento_id: int,
    barbeiro_id: int,
    servico_id: int,
    data_referencia: date,
) -> dict:
    repo = BookingRepository(db)
    barbeiro = repo.get_barbeiro(estabelecimento_id, barbeiro_id, only_active=True)
    servico = repo.get_servico(estabelecimento_id, servico_id)
    if not barbeiro or not servico:
        return {"horarios_disponiveis": [], "horarios_grade": []}

    duracao = _duracao_servico(barbeiro=barbeiro, servico=servico)
    horarios = gerar_horarios_disponiveis(
        db=db,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data=datetime.combine(data_referencia, time(0, 0)),
        tenant_id=estabelecimento_id,
    )
    horarios_set = set(horarios)
    agora_br = datetime.now(_TZ_BRASIL).replace(tzinfo=None)
    grade = [
        {
            "hora": slot.strftime("%H:%M"),
            "disponivel": slot.strftime("%H:%M") in horarios_set and slot >= agora_br,
        }
        for slot in build_day_slots(
            _obter_barbearia(db, estabelecimento_id=estabelecimento_id),
            data_referencia,
            duracao,
            barbeiro=barbeiro,
        )
    ]
    return {"horarios_disponiveis": horarios, "horarios_grade": grade}


def obter_lookup_publico(
    db: Session,
    *,
    slug: str,
    barbeiro_id: int | None = None,
    servico_id: int | None = None,
    data_referencia: date | None = None,
) -> dict:
    barbearia = _obter_barbearia(db, slug=slug)
    if not barbearia:
        raise ValueError("Estabelecimento nao encontrado.")
    return obter_lookup_publico_por_id(
        db,
        estabelecimento_id=barbearia.id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_referencia=data_referencia,
    )


def obter_lookup_publico_por_id(
    db: Session,
    *,
    estabelecimento_id: int,
    barbeiro_id: int | None = None,
    servico_id: int | None = None,
    data_referencia: date | None = None,
) -> dict:
    barbearia = _obter_barbearia(db, estabelecimento_id=estabelecimento_id)
    if not barbearia:
        raise ValueError("Estabelecimento nao encontrado.")

    barbeiros = listar_barbeiros_publico(db, estabelecimento_id=barbearia.id)
    servicos_model = BookingRepository(db).list_public_servicos(barbearia.id)
    servicos = [_serializar_servico_publico(servico, barbearia) for servico in servicos_model]

    if not data_referencia:
        data_referencia = datetime.now().date()

    horarios_disponiveis: list[str] = []
    horarios_grade: list[dict[str, str | bool]] = []
    if barbeiro_id and servico_id:
        disponibilidade = listar_horarios_disponiveis_publico(
            db,
            estabelecimento_id=barbearia.id,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
            data_referencia=data_referencia,
        )
        horarios_disponiveis = disponibilidade["horarios_disponiveis"]
        horarios_grade = disponibilidade["horarios_grade"]

    return {
        "estabelecimento_id": barbearia.id,
        "nome": barbearia.nome,
        "slug": barbearia.slug,
        "barbeiros": barbeiros,
        "servicos": servicos,
        "horarios_disponiveis": horarios_disponiveis,
        "horarios_grade": horarios_grade,
        "accent_color": getattr(barbearia, "accent_color", None) or "#d4930a",
        "bg_color": getattr(barbearia, "bg_color", None) or "#ffffff",
        "logo_url": getattr(barbearia, "logo_url", None),
    }


def buscar_cliente_publico(db: Session, *, estabelecimento_id: int, telefone: str) -> dict | None:
    telefone_norm = _normalizar_telefone_storage(telefone)
    cliente = BookingRepository(db).get_cliente_by_telefone(
        tenant_id=estabelecimento_id,
        telefone=telefone_norm,
    )
    if not cliente:
        return None
    return {
        "nome": cliente.nome,
        "email": getattr(cliente, "email", None),
        "telefone": cliente.telefone,
    }


def criar_agendamento_publico(
    db: Session,
    *,
    slug: str | None = None,
    estabelecimento_id: int | None = None,
    cliente_nome: str,
    cliente_telefone: str,
    cliente_email: str | None = None,
    barbeiro_id: int,
    servico_id: int,
    data: date,
    hora_inicio: time,
    status_inicial: str = "pendente",
    pagamento_adiantado_exigido: bool = False,
    enviar_confirmacao_apos_criacao: bool = True,
    agendar_lembretes: bool = True,
) -> dict:
    barbearia = _obter_barbearia(db, slug=slug, estabelecimento_id=estabelecimento_id)
    if not barbearia:
        raise ValueError("Estabelecimento nao encontrado.")

    repo = BookingRepository(db)
    barbeiro = repo.get_barbeiro(barbearia.id, barbeiro_id, only_active=True, for_update=True)
    if not barbeiro:
        raise ValueError("Profissional nao encontrado.")

    servico = repo.get_servico(barbearia.id, servico_id)
    if not servico:
        raise ValueError("Servico nao encontrado.")

    inicio = datetime.combine(data, hora_inicio.replace(second=0, microsecond=0))
    if inicio < datetime.now(_TZ_BRASIL).replace(tzinfo=None):
        raise ValueError("Horario no passado nao permitido.")

    duracao = _duracao_servico(barbeiro=barbeiro, servico=servico)
    fim = inicio + timedelta(minutes=duracao)
    if not is_within_working_hours(barbearia, inicio, fim):
        raise ValueError("Horario fora do funcionamento do estabelecimento.")
    if not is_within_working_hours(barbearia, inicio, fim, barbeiro=barbeiro):
        raise ValueError("Horario fora da disponibilidade do profissional.")

    conflito = repo.get_conflicting_agendamento(
        tenant_id=barbearia.id,
        barbeiro_id=barbeiro.id,
        inicio=inicio,
        fim=fim,
    )
    if conflito:
        raise ValueError("Horario indisponivel.")

    telefone = _normalizar_telefone_storage(cliente_telefone)
    email_normalizado = (cliente_email or "").strip().lower() or None
    cliente = repo.get_or_create_cliente(
        tenant_id=barbearia.id,
        telefone=telefone,
        nome=cliente_nome.strip(),
        email=email_normalizado,
    )
    agendamento = repo.create_agendamento(
        tenant_id=barbearia.id,
        cliente_id=cliente.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        cliente_email=(cliente_email or "").strip().lower() or None,
        barbeiro_id=barbeiro.id,
        servico_id=servico.id,
        inicio=inicio,
        fim=fim,
        status=status_inicial,
        pagamento_adiantado_exigido=pagamento_adiantado_exigido,
    )
    agendamento.payment_required_snapshot = bool(pagamento_adiantado_exigido)
    if pagamento_adiantado_exigido:
        payment_type = (servico.advance_payment_type or "full").strip().lower()
        amount_snapshot = servico.preco or 0
        if payment_type == "signal" and servico.advance_payment_amount is not None:
            amount_snapshot = servico.advance_payment_amount
        agendamento.payment_type_snapshot = payment_type
        agendamento.payment_amount_snapshot = amount_snapshot
        agendamento.payment_status = "pending"
    else:
        agendamento.payment_status = "not_required"

    lembretes = 0
    if agendar_lembretes:
        lembretes = agendar_lembretes_agendamento(
            db,
            tenant_id=barbearia.id,
            agendamento_id=agendamento.id,
            cliente_nome=cliente.nome,
            cliente_telefone=cliente.telefone,
            nome_barbearia=barbearia.nome,
            servico_nome=servico.nome,
            inicio=inicio,
        )
    db.commit()
    db.refresh(agendamento)

    if enviar_confirmacao_apos_criacao:
        mensagem_confirmacao = montar_mensagem_confirmacao(
            nome_barbearia=barbearia.nome,
            cliente_nome=cliente.nome,
            servico_nome=servico.nome,
            inicio=inicio,
        )
        enviar_mensagem_whatsapp(barbearia, _normalizar_telefone_whatsapp(cliente.telefone), mensagem_confirmacao)

    return {
        "id": agendamento.id,
        "tenant_id": barbearia.id,
        "estabelecimento_id": barbearia.id,
        "slug": barbearia.slug,
        "cliente_nome": agendamento.cliente_nome,
        "cliente_telefone": agendamento.cliente_telefone,
        "cliente_email": agendamento.cliente_email,
        "barbeiro_id": agendamento.barbeiro_id,
        "servico_id": agendamento.servico_id,
        "data_hora_inicio": agendamento.data_hora_inicio,
        "data_hora_fim": agendamento.data_hora_fim,
        "status": _normalizar_status_saida(agendamento.status),
        "confirmation_token": agendamento.confirmation_token,
        "lembretes_agendados": lembretes,
    }


def servico_exige_pagamento_adiantado_publico(
    db: Session,
    *,
    slug: str | None = None,
    estabelecimento_id: int | None = None,
    servico_id: int,
) -> tuple[bool, Decimal, int]:
    barbearia = _obter_barbearia(db, slug=slug, estabelecimento_id=estabelecimento_id)
    if not barbearia:
        raise ValueError("Estabelecimento nao encontrado.")

    servico = BookingRepository(db).get_servico(barbearia.id, servico_id)
    if not servico:
        raise ValueError("Servico nao encontrado.")

    return _servico_exige_pagamento_adiantado(servico, barbearia), Decimal(str(servico.preco)), int(barbearia.id)
