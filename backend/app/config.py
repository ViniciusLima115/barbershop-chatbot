import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

HORARIO_ABERTURA = 8
HORARIO_FECHAMENTO = 19
INTERVALO_MINUTOS = 40