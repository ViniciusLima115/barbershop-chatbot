import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _resolve_env_file() -> Path:
    env_file_override = os.getenv("ENV_FILE", "").strip()
    if env_file_override:
        env_path = Path(env_file_override)
        return env_path if env_path.is_absolute() else BACKEND_DIR / env_path

    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in {"prod", "production"}:
        candidates = [".env.production", ".env.prod", "env.production", "env.prod", ".env"]
    elif app_env in {"stage", "staging"}:
        candidates = [".env.staging", ".env.stage", "env.staging", "env.stage", ".env"]
    else:
        candidates = [".env", ".env.production", ".env.prod"]

    for name in candidates:
        candidate = BACKEND_DIR / name
        if candidate.exists():
            return candidate

    return BACKEND_DIR / ".env"


ENV_FILE_PATH = _resolve_env_file()
load_dotenv(ENV_FILE_PATH)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://chatbot:chatbot@localhost:3306/chatbot",
)

HORARIO_ABERTURA = int(os.getenv("HORARIO_ABERTURA", "8"))
HORARIO_FECHAMENTO = int(os.getenv("HORARIO_FECHAMENTO", "19"))
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "40"))
