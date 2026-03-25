from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.database import init_db
from app.routes import (
    agenda,
    agendamentos,
    auth,
    barbearia_funcionamento,
    barbearias,
    barbeiros,
    chatbot,
    clientes,
    dashboard,
    estabelecimento_funcionamento,
    estabelecimentos,
    internal,
    profissionais,
    public,
    servicos,
    webhook,
    webhooks,
    whatsapp,
)
import secrets
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from app.services.scheduler import start_scheduler, stop_scheduler


security = HTTPBasic()


def _str_to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_cors_allow_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]

    return [
        "https://virtualbarber.shop",
        "https://app.virtualbarber.shop",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def _get_cors_allow_origin_regex() -> str | None:
    configured = os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip()
    if configured:
        return configured

    app_env = os.getenv("APP_ENV", "").strip().lower()
    allow_private_networks = _str_to_bool(
        os.getenv("CORS_ALLOW_PRIVATE_NETWORKS"),
        default=app_env not in {"prod", "production"},
    )
    if not allow_private_networks:
        return None

    return (
        r"^https?://("
        r"localhost|127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    )


def verify_docs(credentials: HTTPBasicCredentials = Depends(security)):
    DOCS_USER = os.getenv("DOCS_USER")
    DOCS_PASS = os.getenv("DOCS_PASS")

    correct_username = secrets.compare_digest(
        credentials.username,
        DOCS_USER or ""
    )
    correct_password = secrets.compare_digest(
        credentials.password,
        DOCS_PASS or ""
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/docs", response_class=HTMLResponse)
def custom_swagger_ui(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Barbearia Chatbot API - Documentação"
    )
@app.get("/openapi.json")
def openapi(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return app.openapi()


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_allow_origins(),
    allow_origin_regex=_get_cors_allow_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agendamentos.router)
app.include_router(clientes.router)
app.include_router(barbearias.router)
app.include_router(barbearia_funcionamento.router)
app.include_router(barbeiros.router)
app.include_router(servicos.router)
app.include_router(agenda.router)
app.include_router(dashboard.router)
app.include_router(chatbot.router)
app.include_router(whatsapp.router, prefix="/whatsapp")
app.include_router(webhooks.router)
app.include_router(webhook.router)
app.include_router(public.router)
app.include_router(internal.router)
app.include_router(auth.router)
app.include_router(estabelecimentos.router)
app.include_router(profissionais.router)
app.include_router(estabelecimento_funcionamento.router)

@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "barbearia-api"
    }
