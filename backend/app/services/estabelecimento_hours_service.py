from datetime import date, datetime, time, timedelta

from app.config import HORARIO_ABERTURA, HORARIO_FECHAMENTO, INTERVALO_MINUTOS


DAY_KEYS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
WEEKDAY_TO_KEY = {
    0: "seg",
    1: "ter",
    2: "qua",
    3: "qui",
    4: "sex",
    5: "sab",
    6: "dom",
}


def default_working_hours() -> dict[str, dict[str, str | bool]]:
    inicio = f"{HORARIO_ABERTURA:02d}:00"
    fim = f"{HORARIO_FECHAMENTO:02d}:00"
    return {
        key: {
            "ativo": True,
            "inicio": inicio,
            "fim": fim,
        }
        for key in DAY_KEYS
    }


def _clone_working_hours(data: dict[str, dict[str, str | bool]]) -> dict[str, dict[str, str | bool]]:
    return {
        key: {
            "ativo": bool(value["ativo"]),
            "inicio": str(value["inicio"]),
            "fim": str(value["fim"]),
        }
        for key, value in data.items()
    }


def _parse_time(value: str, fallback: str) -> str:
    text = (value or "").strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        return fallback
    return text


def normalize_working_hours(
    raw: dict | None,
    *,
    fallback: dict[str, dict[str, str | bool]] | None = None,
) -> dict[str, dict[str, str | bool]]:
    normalized = _clone_working_hours(fallback or default_working_hours())
    if not isinstance(raw, dict):
        return normalized

    for key in DAY_KEYS:
        data = raw.get(key)
        if not isinstance(data, dict):
            continue
        normalized[key] = {
            "ativo": bool(data.get("ativo", normalized[key]["ativo"])),
            "inicio": _parse_time(str(data.get("inicio", normalized[key]["inicio"])), str(normalized[key]["inicio"])),
            "fim": _parse_time(str(data.get("fim", normalized[key]["fim"])), str(normalized[key]["fim"])),
        }

    return normalized


def get_working_hours(estabelecimento) -> dict[str, dict[str, str | bool]]:
    return normalize_working_hours(getattr(estabelecimento, "horarios_funcionamento", None))


def get_barbeiro_working_hours(estabelecimento, barbeiro) -> dict[str, dict[str, str | bool]]:
    base_schedule = get_working_hours(estabelecimento)
    raw = getattr(barbeiro, "horarios_funcionamento", None)
    if raw is None:
        return base_schedule
    return normalize_working_hours(raw, fallback=base_schedule)


def _get_window_from_schedule(
    schedule: dict[str, dict[str, str | bool]],
    target_date: date,
) -> tuple[time, time] | None:
    key = WEEKDAY_TO_KEY[target_date.weekday()]
    day = schedule[key]
    if not day["ativo"]:
        return None
    start = datetime.strptime(str(day["inicio"]), "%H:%M").time()
    end = datetime.strptime(str(day["fim"]), "%H:%M").time()
    if start >= end:
        return None
    return start, end


def get_working_window(estabelecimento, target_date: date, barbeiro=None) -> tuple[time, time] | None:
    base_schedule = get_working_hours(estabelecimento)
    base_window = _get_window_from_schedule(base_schedule, target_date)
    if not base_window:
        return None

    if barbeiro is None:
        return base_window

    barbeiro_window = _get_window_from_schedule(
        get_barbeiro_working_hours(estabelecimento, barbeiro),
        target_date,
    )
    if not barbeiro_window:
        return None

    start = max(base_window[0], barbeiro_window[0])
    end = min(base_window[1], barbeiro_window[1])
    if start >= end:
        return None
    return start, end


def build_day_slots(estabelecimento, target_date: date, duration_minutes: int, barbeiro=None) -> list[datetime]:
    window = get_working_window(estabelecimento, target_date, barbeiro=barbeiro)
    if not window:
        return []

    start, end = window
    current = datetime.combine(target_date, start)
    finish = datetime.combine(target_date, end)
    slots: list[datetime] = []

    while current + timedelta(minutes=duration_minutes) <= finish:
        slots.append(current)
        current += timedelta(minutes=INTERVALO_MINUTOS)

    return slots


def is_within_working_hours(estabelecimento, start_at: datetime, end_at: datetime, barbeiro=None) -> bool:
    window = get_working_window(estabelecimento, start_at.date(), barbeiro=barbeiro)
    if not window or start_at.date() != end_at.date():
        return False

    start, end = window
    day_start = datetime.combine(start_at.date(), start)
    day_end = datetime.combine(start_at.date(), end)
    return day_start <= start_at and end_at <= day_end
