# Barbearia Chatbot

Mini documentação para rodar o projeto localmente do zero.

## Visão geral

O projeto tem duas partes:

- `backend`: API FastAPI + SQLAlchemy + MySQL
- `frontend`: painel em Next.js para visualizar a agenda

## Pré-requisitos

- Python 3.11+ (recomendado usar `venv`)
- Node.js 20+ e npm
- MySQL 8+ rodando localmente

## 1) Clonar e entrar no projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd barbearia-chatbot
```

## 2) Subir banco MySQL

Crie um banco e usuário (ajuste senha se quiser):

```sql
CREATE DATABASE chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'chatbot'@'localhost' IDENTIFIED BY 'chatbot';
GRANT ALL PRIVILEGES ON chatbot.* TO 'chatbot'@'localhost';
FLUSH PRIVILEGES;
```

## 3) Configurar e rodar backend

Entre na pasta:

```bash
cd backend
```

Crie o ambiente virtual e instale dependências:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie um `.env` em `backend/.env`:

```env
DATABASE_URL=mysql+pymysql://chatbot:chatbot@localhost:3306/chatbot
HORARIO_ABERTURA=8
HORARIO_FECHAMENTO=19
INTERVALO_MINUTOS=40

# Opcional (integração WhatsApp)
WHATSAPP_TOKEN=
PHONE_NUMBER_ID=
```

Rode a API:

```bash
uvicorn app.main:app --reload
```

API disponível em:

- `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

## 4) Configurar e rodar frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend disponível em:

- `http://localhost:3000`

Observação: o frontend já está apontando para `http://127.0.0.1:8000`.

## 5) Carga inicial (dados mínimos)

Sem dados, a agenda abre vazia. Cadastre pelo menos 1 barbeiro e 1 serviço.

### Criar barbeiros

```bash
curl -X POST http://127.0.0.1:8000/barbeiros/ \
  -H "Content-Type: application/json" \
  -d '{"nome":"João"}'
```

```bash
curl -X POST http://127.0.0.1:8000/barbeiros/ \
  -H "Content-Type: application/json" \
  -d '{"nome":"Carlos"}'
```

### Criar serviços

```bash
curl -X POST http://127.0.0.1:8000/servicos/ \
  -H "Content-Type: application/json" \
  -d '{"nome":"Corte","duracao_minutos":40,"preco":45}'
```

```bash
curl -X POST http://127.0.0.1:8000/servicos/ \
  -H "Content-Type: application/json" \
  -d '{"nome":"Barba","duracao_minutos":30,"preco":35}'
```

### Criar agendamento de teste

```bash
curl -X POST http://127.0.0.1:8000/agendamentos/ \
  -H "Content-Type: application/json" \
  -d '{
    "telefone":"11999999999",
    "nome_cliente":"Cliente Teste",
    "barbeiro_id":1,
    "servico_id":1,
    "data_hora_inicio":"2026-02-20T10:00:00"
  }'
```

Depois abra `http://localhost:3000/agenda`.

## Endpoints principais

- `GET /` status da API
- `GET /agenda/dia?data=YYYY-MM-DDTHH:MM:SS`
- `GET /agenda/horarios-disponiveis?barbeiro_id=1&servico_id=1&data=YYYY-MM-DDTHH:MM:SS`
- `POST /barbeiros/`
- `GET /barbeiros/`
- `POST /servicos/`
- `GET /servicos/`
- `POST /agendamentos/`
- `POST /chatbot/mensagem`
- `GET /whatsapp/webhook` e `POST /whatsapp/webhook`

## Problemas comuns

- Erro de conexão com banco:
  - conferir se MySQL está ativo e se `DATABASE_URL` está correta.
- Frontend mostra erro ao carregar agenda:
  - conferir se backend está rodando em `127.0.0.1:8000`.
- Agenda vazia:
  - cadastrar barbeiros, serviços e agendamentos.

## Estrutura resumida

```text
barbearia-chatbot/
  backend/
    app/
      main.py
      routes/
      services/
      models/
  frontend/
    app/
    services/
```
