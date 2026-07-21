import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

import requests


logger = logging.getLogger(__name__)

EMAIL_PROVIDER = (os.getenv("EMAIL_PROVIDER", "auto").strip().lower() or "auto")
EMAIL_FROM = (
    os.getenv("EMAIL_FROM")
    or os.getenv("SMTP_FROM_EMAIL")
    or os.getenv("RESEND_FROM_EMAIL")
    or "noreply@localhost"
).strip()
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Hagendei")
EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "").strip() or None
EMAIL_ACTION_BASE_URL = (
    os.getenv("EMAIL_ACTION_BASE_URL")
    or os.getenv("BOOKING_PUBLIC_BASE_URL")
    or "http://127.0.0.1:3000"
).rstrip("/")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_API_URL = os.getenv("RESEND_API_URL", "https://api.resend.com/emails").strip()
HTTP_TIMEOUT_SECONDS = int(os.getenv("EMAIL_HTTP_TIMEOUT_SECONDS", "10"))
EMAIL_TEMPLATE_PATH = os.getenv("EMAIL_TEMPLATE_PATH", "frontend/public/template.html").strip()
REPO_DIR = Path(__file__).resolve().parents[3]


@dataclass
class AgendamentoEmailContext:
    agendamento_id: int
    confirmation_token: str
    cliente_nome: str
    cliente_email: str
    barbearia_nome: str
    estabelecimento_id: int
    slug: str | None
    servico_nome: str
    barbeiro_nome: str
    data_hora_inicio: datetime


def _formatar_data_hora(data_hora_inicio: datetime) -> tuple[str, str]:
    return data_hora_inicio.strftime("%d/%m/%Y"), data_hora_inicio.strftime("%H:%M")


def _montar_link_acao(acao: str, token: str) -> str:
    return f"{EMAIL_ACTION_BASE_URL}/{acao}/{token}"


def _montar_link_reagendamento(contexto: AgendamentoEmailContext) -> str:
    return _montar_link_acao("reagendar", contexto.confirmation_token)


def _montar_link_botao(label: str, url: str, *, accent: str, text_color: str) -> str:
    return (
        f'<a href="{escape(url, quote=True)}" '
        "style="
        f'"display:inline-block;padding:12px 18px;margin:0 8px 8px 0;border-radius:999px;'
        f'background:{accent};color:{text_color};font-weight:700;text-decoration:none;">'
        f"{escape(label)}</a>"
    )


def _carregar_template_html() -> str | None:
    if not EMAIL_TEMPLATE_PATH:
        return None

    template_path = Path(EMAIL_TEMPLATE_PATH)
    if not template_path.is_absolute():
        template_path = REPO_DIR / template_path

    if not template_path.exists():
        logger.warning("Template de email nao encontrado em %s", template_path)
        return None

    try:
        return template_path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Falha ao ler template de email em %s", template_path)
        return None


def _renderizar_template_html(
    *,
    contexto: AgendamentoEmailContext,
    email_title: str,
    email_subtitle: str,
    headline: str,
    intro: str,
    help_text: str,
) -> str | None:
    template = _carregar_template_html()
    if not template:
        return None

    data_str, hora_str = _formatar_data_hora(contexto.data_hora_inicio)
    link_confirmar = _montar_link_acao("confirmar", contexto.confirmation_token)
    link_cancelar = _montar_link_acao("cancelar", contexto.confirmation_token)
    link_reagendar = _montar_link_acao("reagendar", contexto.confirmation_token)

    substitutions = {
        "{{email_title}}": escape(email_title),
        "{{email_subtitle}}": escape(email_subtitle),
        "{{headline}}": escape(headline),
        "{{intro}}": intro,
        "{{help_text}}": escape(help_text),
        "{{cliente_nome}}": escape(contexto.cliente_nome),
        "{{barbearia_nome}}": escape(contexto.barbearia_nome),
        "{{servico_nome}}": escape(contexto.servico_nome),
        "{{barbeiro_nome}}": escape(contexto.barbeiro_nome),
        "{{data}}": escape(data_str),
        "{{horario}}": escape(hora_str),
        "{{confirmar_link}}": escape(link_confirmar, quote=True),
        "{{cancelar_link}}": escape(link_cancelar, quote=True),
        "{{reagendar_link}}": escape(link_reagendar, quote=True),
        "{{link_agendamento}}": escape(link_reagendar),
        "{{ano}}": str(contexto.data_hora_inicio.year),
    }

    rendered = template
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _montar_html_base(
    *,
    titulo: str,
    subtitulo: str,
    contexto: AgendamentoEmailContext,
    destaque: str,
    botoes_html: str,
) -> str:
    data_str, hora_str = _formatar_data_hora(contexto.data_hora_inicio)
    return f"""
    <html>
      <body style="margin:0;padding:24px;background:#f5efe7;font-family:Arial,sans-serif;color:#1f1b16;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;margin:0 auto;">
          <tr>
            <td style="padding:0;">
              <div style="background:linear-gradient(135deg,#16120f,#34261c);border-radius:24px;padding:32px;color:#fff7ef;">
                <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,0.12);font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">
                  {escape(EMAIL_FROM_NAME)}
                </div>
                <h1 style="margin:18px 0 8px;font-size:28px;line-height:1.15;">{escape(titulo)}</h1>
                <p style="margin:0;color:#ead9cb;font-size:15px;line-height:1.6;">{escape(subtitulo)}</p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 0 0;">
              <div style="background:#fffdfa;border:1px solid rgba(79,52,28,0.10);border-radius:24px;padding:28px;box-shadow:0 18px 48px rgba(67,42,22,0.08);">
                <p style="margin:0 0 18px;font-size:15px;">Ola, {escape(contexto.cliente_nome)}.</p>
                <div style="margin:0 0 22px;padding:18px;border-radius:18px;background:{destaque};">
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size:15px;line-height:1.7;">
                    <tr><td><strong>Estabelecimento:</strong> {escape(contexto.barbearia_nome)}</td></tr>
                    <tr><td><strong>Servico:</strong> {escape(contexto.servico_nome)}</td></tr>
                    <tr><td><strong>Profissional:</strong> {escape(contexto.barbeiro_nome)}</td></tr>
                    <tr><td><strong>Data:</strong> {data_str}</td></tr>
                    <tr><td><strong>Horario:</strong> {hora_str}</td></tr>
                  </table>
                </div>
                <div style="margin:0 0 16px;">{botoes_html}</div>
                <p style="margin:18px 0 0;color:#6a5848;font-size:13px;line-height:1.6;">
                  Se algum botao nao abrir, use este link para reagendar:
                  <a href="{escape(_montar_link_reagendamento(contexto), quote=True)}" style="color:#8a4215;text-decoration:none;">
                    {escape(_montar_link_reagendamento(contexto))}
                  </a>
                </p>
              </div>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """.strip()


def build_confirmation_email(contexto: AgendamentoEmailContext) -> dict[str, str]:
    botoes = "".join(
        [
            _montar_link_botao(
                "Confirmar presenca",
                _montar_link_acao("confirmar", contexto.confirmation_token),
                accent="#1f8b62",
                text_color="#fffdfa",
            ),
            _montar_link_botao(
                "Cancelar agendamento",
                _montar_link_acao("cancelar", contexto.confirmation_token),
                accent="#bf4a45",
                text_color="#fffdfa",
            ),
            _montar_link_botao(
                "Reagendar",
                _montar_link_acao("reagendar", contexto.confirmation_token),
                accent="#c36b2d",
                text_color="#fffdfa",
            ),
        ]
    )
    html_template = _renderizar_template_html(
        contexto=contexto,
        email_title="Agendamento confirmado",
        email_subtitle="Confirmacao de Agendamento",
        headline="Seu agendamento foi confirmado!",
        intro=f"Ola <strong>{escape(contexto.cliente_nome)}</strong>, seu horario foi reservado com sucesso.",
        help_text="Se precisar alterar algo, voce pode confirmar presenca, cancelar ou reagendar usando os botoes abaixo.",
    )
    return {
        "to_email": contexto.cliente_email,
        "subject": "Agendamento confirmado",
        "html_content": html_template
        or _montar_html_base(
            titulo="Seu agendamento foi confirmado.",
            subtitulo="Use os atalhos abaixo para confirmar sua presenca, cancelar ou pedir reagendamento.",
            contexto=contexto,
            destaque="#f5ede4",
            botoes_html=botoes,
        ),
    }


def build_reminder_email(contexto: AgendamentoEmailContext, *, hours_before: int) -> dict[str, str]:
    botoes = "".join(
        [
            _montar_link_botao(
                "Confirmar presenca",
                _montar_link_acao("confirmar", contexto.confirmation_token),
                accent="#1f8b62",
                text_color="#fffdfa",
            ),
            _montar_link_botao(
                "Cancelar",
                _montar_link_acao("cancelar", contexto.confirmation_token),
                accent="#bf4a45",
                text_color="#fffdfa",
            ),
            _montar_link_botao(
                "Reagendar",
                _montar_link_acao("reagendar", contexto.confirmation_token),
                accent="#c36b2d",
                text_color="#fffdfa",
            ),
        ]
    )
    html_template = _renderizar_template_html(
        contexto=contexto,
        email_title="Lembrete de agendamento",
        email_subtitle="Lembrete de Agendamento",
        headline="Seu horario esta chegando!",
        intro=(
            f"Ola <strong>{escape(contexto.cliente_nome)}</strong>, este e um lembrete enviado "
            f"{hours_before}h antes do seu atendimento."
        ),
        help_text="Se precisar ajustar algo, use os botoes abaixo.",
    )
    return {
        "to_email": contexto.cliente_email,
        "subject": "Lembrete de agendamento",
        "html_content": html_template
        or _montar_html_base(
            titulo="Seu horario esta chegando.",
            subtitulo=f"Este e um lembrete enviado {hours_before}h antes do seu atendimento.",
            contexto=contexto,
            destaque="#fbf3e3",
            botoes_html=botoes,
        ),
    }


def build_status_email(contexto: AgendamentoEmailContext, *, tipo: str) -> dict[str, str]:
    configuracao = {
        "confirmado": (
            "Presenca confirmada",
            "Sua presenca foi confirmada com sucesso.",
            "Nos vemos no horario agendado.",
            "#e9f5ef",
        ),
        "cancelado": (
            "Agendamento cancelado",
            "Seu agendamento foi cancelado.",
            "Se quiser, voce pode voltar e escolher um novo horario.",
            "#fdeceb",
        ),
        "reagendamento_solicitado": (
            "Reagendamento solicitado",
            "Recebemos seu pedido de reagendamento.",
            "Use o link abaixo para escolher um novo horario.",
            "#fbf3e3",
        ),
    }
    subject, titulo, subtitulo, destaque = configuracao[tipo]
    botoes = _montar_link_botao(
        "Abrir agendamento",
        _montar_link_reagendamento(contexto),
        accent="#c36b2d",
        text_color="#fffdfa",
    )
    return {
        "to_email": contexto.cliente_email,
        "subject": subject,
        "html_content": _montar_html_base(
            titulo=titulo,
            subtitulo=subtitulo,
            contexto=contexto,
            destaque=destaque,
            botoes_html=botoes,
        ),
    }


def _send_via_resend(to_email: str, subject: str, html_content: str) -> bool:
    if not RESEND_API_KEY:
        return False

    payload = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }
    if EMAIL_REPLY_TO:
        payload["reply_to"] = EMAIL_REPLY_TO

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code >= 300:
        logger.warning(
            "Resend recusou o email (status=%s).",
            response.status_code,
        )
    return response.status_code < 300


def _send_via_smtp(to_email: str, subject: str, html_content: str) -> bool:
    if not SMTP_HOST:
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = EMAIL_FROM
    message["To"] = to_email
    if EMAIL_REPLY_TO:
        message["Reply-To"] = EMAIL_REPLY_TO
    message.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=HTTP_TIMEOUT_SECONDS) as server:
        server.ehlo()
        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, [to_email], message.as_string())
    return True


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    destinatario = (to_email or "").strip()
    if not destinatario:
        logger.info("Envio de email ignorado: destinatario vazio.")
        return False

    provider = EMAIL_PROVIDER
    if provider == "auto":
        provider = "resend" if RESEND_API_KEY else "smtp"

    try:
        if provider == "resend":
            ok = _send_via_resend(destinatario, subject, html_content)
        elif provider == "smtp":
            ok = _send_via_smtp(destinatario, subject, html_content)
        else:
            logger.warning("EMAIL_PROVIDER invalido: %s", provider)
            return False
    except Exception:
        logger.exception("Falha ao enviar email com provider %s", provider)
        return False

    if ok:
        logger.info("Email enviado com sucesso via %s.", provider)
    else:
        logger.warning("Email nao enviado via %s.", provider)
    return ok


def send_email_payload(payload: dict[str, str]) -> bool:
    return send_email(
        payload["to_email"],
        payload["subject"],
        payload["html_content"],
    )
