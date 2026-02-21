from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import barbeiros, servicos, agendamentos, agenda, chatbot, whatsapp, clientes

app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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

@app.get("/")
def home():
    return {"status": "ok"}
