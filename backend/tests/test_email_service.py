from datetime import datetime

from app.services.email_service import (
    AgendamentoEmailContext,
    build_confirmation_email,
    build_reminder_email,
    build_status_email,
)


def _contexto() -> AgendamentoEmailContext:
    return AgendamentoEmailContext(
        agendamento_id=1,
        confirmation_token="token-teste",
        cliente_nome="Cliente Teste",
        cliente_email="cliente@example.com",
        barbearia_nome="Studio Central",
        estabelecimento_id=1,
        slug="studio-central",
        servico_nome="Consulta inicial",
        barbeiro_nome="Profissional Teste",
        data_hora_inicio=datetime(2026, 7, 14, 9, 0),
    )


def test_email_de_confirmacao_usa_identidade_e_rotulos_genericos():
    email = build_confirmation_email(_contexto())

    assert email["subject"] == "Agendamento confirmado"
    assert "Hagendei" in email["html_content"]
    assert "Estabelecimento:" in email["html_content"]
    assert "Profissional:" in email["html_content"]
    assert "Barbearia:" not in email["html_content"]
    assert "Barbeiro:" not in email["html_content"]
    assert "✂" not in email["html_content"]


def test_assuntos_de_lembrete_e_status_nao_usam_icone_de_barbearia():
    contexto = _contexto()
    emails = [
        build_reminder_email(contexto, hours_before=24),
        build_status_email(contexto, tipo="confirmado"),
        build_status_email(contexto, tipo="reagendamento_solicitado"),
    ]

    assert all("✂" not in email["subject"] for email in emails)
