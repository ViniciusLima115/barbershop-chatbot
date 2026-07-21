# Shim de compatibilidade — sera removido junto com routes/barbearia_funcionamento.py
# (rota morta, nao registrada em main.py).
from app.services.estabelecimento_hours_service import (
    build_day_slots,
    default_working_hours,
    get_barbeiro_working_hours,
    get_working_hours,
    get_working_window,
    is_within_working_hours,
    normalize_working_hours,
)

__all__ = [
    "build_day_slots",
    "default_working_hours",
    "get_barbeiro_working_hours",
    "get_working_hours",
    "get_working_window",
    "is_within_working_hours",
    "normalize_working_hours",
]
