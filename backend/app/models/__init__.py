from app.models.estabelecimento import Estabelecimento
from app.models.profissional import Profissional
# Aliases de compatibilidade — manter enquanto o código legado não for atualizado
Barbearia = Estabelecimento
Barbeiro = Profissional

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente
from app.models.conversa import Conversa
from app.models.reminder_job import ReminderJob
from app.models.servico import Servico
from app.models.token_blacklist import TokenBlacklist
from app.models.webhook_event import WebhookEvent

__all__ = [
    "Estabelecimento", "Profissional",
    "Barbearia", "Barbeiro",  # aliases de compatibilidade
    "Agendamento", "Cliente", "Conversa", "ReminderJob",
    "Servico", "WebhookEvent", "TokenBlacklist",
]
