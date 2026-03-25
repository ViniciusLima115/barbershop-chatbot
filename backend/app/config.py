import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


def _env_candidates(app_env: str) -> list[str]:
    if app_env in {"prod", "production"}:
        return [".env.production", ".env.prod", "env.production", "env.prod", ".env"]
    if app_env in {"stage", "staging"}:
        return [".env.staging", ".env.stage", "env.staging", "env.stage", ".env"]
    return [".env", ".env.production", ".env.prod"]


def _resolve_env_files() -> list[Path]:
    env_file_override = os.getenv("ENV_FILE", "").strip()
    if env_file_override:
        env_path = Path(env_file_override)
        return [env_path if env_path.is_absolute() else BACKEND_DIR / env_path]

    app_env = os.getenv("APP_ENV", "").strip().lower()
    resolved: list[Path] = []
    for base_dir in (REPO_DIR, BACKEND_DIR):
        for name in _env_candidates(app_env):
            candidate = base_dir / name
            if candidate.exists():
                resolved.append(candidate)
                break

    return resolved or [BACKEND_DIR / ".env"]


def _get_database_url() -> str:
    for key in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "NEON_DATABASE_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return _normalize_database_url(value)

    return "postgresql+psycopg2://postgres:postgres@localhost:5432/barbearia"


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)

    if normalized.startswith("postgresql+psycopg://"):
        normalized = normalized.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    elif normalized.startswith("postgresql://"):
        normalized = normalized.replace("postgresql://", "postgresql+psycopg2://", 1)

    if not normalized.startswith("postgresql+psycopg2://"):
        return normalized

    parsed = urlsplit(normalized)
    hostname = (parsed.hostname or "").lower()
    is_local = hostname in {"", "localhost", "127.0.0.1"}
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if not is_local and "sslmode" not in query:
        query["sslmode"] = "require"
        normalized = urlunsplit(parsed._replace(query=urlencode(query)))

    return normalized


ENV_FILE_PATHS = _resolve_env_files()
for env_path in ENV_FILE_PATHS:
    load_dotenv(env_path, override=False)

DATABASE_URL = _get_database_url()

HORARIO_ABERTURA = int(os.getenv("HORARIO_ABERTURA", "8"))
HORARIO_FECHAMENTO = int(os.getenv("HORARIO_FECHAMENTO", "19"))
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "30"))
