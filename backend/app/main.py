from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import barbeiros, servicos, agendamentos, agenda, chatbot, whatsapp, clientes, auth
import secrets
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


security = HTTPBasic()


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

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

@app.get("/docs", response_class=HTMLResponse)
def custom_swagger_ui(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Barbearia Chatbot API - Documentação"
    )
@app.get("/openapi.json")
def openapi(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return app.openapi()

@app.on_event("startup")
def startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # depois você restringe
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agendamentos.router)
app.include_router(clientes.router)
app.include_router(barbeiros.router)
app.include_router(servicos.router)
app.include_router(agenda.router)
app.include_router(chatbot.router)
app.include_router(whatsapp.router, prefix="/whatsapp")
app.include_router(auth.router)

@app.get("/")
def home():
    return {"status": "ok"}
