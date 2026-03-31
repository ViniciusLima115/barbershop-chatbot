import os
import re
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.servico import Servico
from app.repositories.booking_repository import BookingRepository
from app.repositories.tenant_repository import TenantRepository
from app.services.agenda_service import gerar_horarios_disponiveis
from app.services.barbershop_hours_service import build_day_slots, is_within_working_hours
from app.services.notificacao_service import (
    agendar_lembretes_agendamento,
    enviar_mensagem_whatsapp,
    montar_mensagem_confirmacao,
)


BOOKING_PUBLIC_BASE_URL = os.getenv("BOOKING_PUBLIC_BASE_URL", "https://app.virtualbarber.shop")
STATUS_VALIDOS = {"pendente", "confirmado", "cancelado", "reagendamento_solicitado", "compareceu", "no_show"}


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


def montar_link_agendamento_por_id(barbearia_id: int) -> str:
    base = BOOKING_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/agendar/{barbearia_id}"


def montar_mensagem_link_agendamento(nome_barbearia: str, slug: str) -> str:
    return (
        f"Oi. Para agendar na {nome_barbearia}, use este link:\n"
        f"{montar_link_agendamento(slug)}"
    )


def montar_mensagem_link_agendamento_por_id(nome_barbearia: str, barbearia_id: int) -> str:
    return (
        f"Oi. Para agendar na {nome_barbearia}, use este link:\n"
        f"{montar_link_agendamento_por_id(barbearia_id)}"
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
    barbearia_id: int | None = None,
) -> Barbearia | None:
    tenant_repo = TenantRepository(db)
    if barbearia_id:
        return tenant_repo.get_by_id(barbearia_id)
    if slug:
        return tenant_repo.get_by_slug(slug)
    return None


def listar_barbeiros_publico(db: Session, *, barbearia_id: int) -> list[Barbeiro]:
    return BookingRepository(db).list_public_barbeiros(barbearia_id, only_active=True)


def listar_servicos_publico(db: Session, *, barbearia_id: int) -> list[Servico]:
    return BookingRepository(db).list_public_servicos(barbearia_id)


def listar_horarios_disponiveis_publico(
    db: Session,
    *,
    barbearia_id: int,
    barbeiro_id: int,
    servico_id: int,
    data_referencia: date,
) -> dict:
    repo = BookingRepository(db)
    barbeiro = repo.get_barbeiro(barbearia_id, barbeiro_id, only_active=True)
    servico = repo.get_servico(barbearia_id, servico_id)
    if not barbeiro or not servico:
        return {"horarios_disponiveis": [], "horarios_grade": []}

    duracao = _duracao_servico(barbeiro=barbeiro, servico=servico)
    horarios = gerar_horarios_disponiveis(
        db=db,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data=datetime.combine(data_referencia, time(0, 0)),
        tenant_id=barbearia_id,
    )
    horarios_set = set(horarios)
    grade = [
        {"hora": slot.strftime("%H:%M"), "disponivel": slot.strftime("%H:%M") in horarios_set}
        for slot in build_day_slots(
            _obter_barbearia(db, barbearia_id=barbearia_id),
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
        raise ValueError("Barbearia nao encontrada.")
    return obter_lookup_publico_por_id(
        db,
        barbearia_id=barbearia.id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_referencia=data_referencia,
    )


def obter_lookup_publico_por_id(
    db: Session,
    *,
    barbearia_id: int,
    barbeiro_id: int | None = None,
    servico_id: int | None = None,
    data_referencia: date | None = None,
) -> dict:
    barbearia = _obter_barbearia(db, barbearia_id=barbearia_id)
    if not barbearia:
        raise ValueError("Barbearia nao encontrada.")

    barbeiros = listar_barbeiros_publico(db, barbearia_id=barbearia.id)
    servicos = listar_servicos_publico(db, barbearia_id=barbearia.id)

    if not data_referencia:
        data_referencia = datetime.now().date()

    horarios_disponiveis: list[str] = []
    horarios_grade: list[dict[str, str | bool]] = []
    if barbeiro_id and servico_id:
        disponibilidade = listar_horarios_disponiveis_publico(
            db,
            barbearia_id=barbearia.id,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
            data_referencia=data_referencia,
        )
        horarios_disponiveis = disponibilidade["horarios_disponiveis"]
        horarios_grade = disponibilidade["horarios_grade"]

    return {
        "barbearia_id": barbearia.id,
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


def buscar_cliente_publico(db: Session, *, barbearia_id: int, telefone: str) -> dict | None:
    telefone_norm = _normalizar_telefone_storage(telefone)
    cliente = BookingRepository(db).get_cliente_by_telefone(
        tenant_id=barbearia_id,
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
    barbearia_id: int | None = None,
    cliente_nome: str,
    cliente_telefone: str,
    cliente_email: str | None = None,
    barbeiro_id: int,
    servico_id: int,
    data: date,
    hora_inicio: time,
) -> dict:
    barbearia = _obter_barbearia(db, slug=slug, barbearia_id=barbearia_id)
    if not barbearia:
        raise ValueError("Barbearia nao encontrada.")

    repo = BookingRepository(db)
    barbeiro = repo.get_barbeiro(barbearia.id, barbeiro_id, only_active=True)
    if not barbeiro:
        raise ValueError("Barbeiro nao encontrado.")

    servico = repo.get_servico(barbearia.id, servico_id)
    if not servico:
        raise ValueError("Servico nao encontrado.")

    inicio = datetime.combine(data, hora_inicio.replace(second=0, microsecond=0))
    if inicio < datetime.now():
        raise ValueError("Horario no passado nao permitido.")

    duracao = _duracao_servico(barbeiro=barbeiro, servico=servico)
    fim = inicio + timedelta(minutes=duracao)
    if not is_within_working_hours(barbearia, inicio, fim):
        raise ValueError("Horario fora do funcionamento da barbearia.")
    if not is_within_working_hours(barbearia, inicio, fim, barbeiro=barbeiro):
        raise ValueError("Horario fora do funcionamento do barbeiro.")

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
        status="pendente",
    )

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
        "barbearia_id": barbearia.id,
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
