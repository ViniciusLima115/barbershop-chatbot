# Deploy VPS Google Cloud — Design Spec

**Data:** 2026-05-02  
**Status:** Aprovado

---

## Visão Geral

Configurar uma instância Google Compute Engine do zero para hospedar o projeto barbearia-chatbot, com deploy automático via webhook do GitHub.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| VM | Google Compute Engine e2-small (2 vCPU compartilhada, 2 GB RAM) |
| SO | Ubuntu 22.04 LTS |
| Containerização | Docker + Docker Compose |
| Reverse proxy / SSL | Caddy (container) |
| Backend | FastAPI + uvicorn (container) |
| Frontend | Next.js (container) |
| Banco de dados | Neon (externo, sem container na VM) |
| Deploy automático | adnanh/webhook (container) |

---

## Arquitetura

```
Google Cloud Compute Engine (e2-small, Ubuntu 22.04)
├── Firewall GCP: 22 (SSH), 80 (HTTP), 443 (HTTPS)
└── Docker Compose
    ├── caddy       → portas 80/443, reverse proxy + SSL automático (Let's Encrypt)
    ├── backend     → FastAPI + uvicorn, porta interna 8000
    ├── frontend    → Next.js, porta interna 3000
    └── webhook     → adnanh/webhook, porta interna 9000

DNS:
  virtualbarber.shop       → A → IP externo da VM  (frontend)
  api.virtualbarber.shop   → A → IP externo da VM  (backend + webhook)

Banco: Neon Serverless PostgreSQL (via DATABASE_URL no .env.production)
```

### Roteamento Caddy

```
virtualbarber.shop {
    reverse_proxy frontend:3000
}

api.virtualbarber.shop {
    reverse_proxy /deploy webhook:9000
    reverse_proxy backend:8000
}
```

---

## Arquivos a Criar

```
barbearia-chatbot/
├── docker-compose.yml
├── Caddyfile
├── backend/
│   └── Dockerfile
└── frontend/
    └── Dockerfile
```

### `backend/Dockerfile`
- Imagem base: `python:3.11-slim`
- Copia e instala `requirements.txt`
- Comando: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Env vars via `backend/.env.production` (montado como volume ou copiado)

### `frontend/Dockerfile`
- Build multi-stage: `node:20-alpine` para build, imagem enxuta para runtime
- `NEXT_PUBLIC_API_URL=https://api.virtualbarber.shop` injetado no build
- Comando: `node server.js` (output standalone do Next.js)

### `docker-compose.yml`
- 4 serviços: caddy, backend, frontend, webhook
- Rede interna Docker compartilhada entre todos
- Volume para dados do Caddy (certificados SSL persistem entre restarts)
- Bind mount do socket Docker no container webhook (para rodar `docker compose` dentro dele)

---

## Deploy Automático (Webhook)

**Fluxo:**
```
git push origin main
  → GitHub POST https://api.virtualbarber.shop/deploy (com HMAC-SHA256 secret)
  → container webhook valida token
  → executa script: git pull && docker compose up -d --build
```

**Segurança:**
- Secret token configurado em variável de ambiente `WEBHOOK_SECRET` na VM
- Mesmo secret cadastrado no GitHub (Settings → Webhooks)
- Requisições sem token válido são rejeitadas com 403

**Script de deploy** (`scripts/deploy.sh`):
```bash
#!/bin/bash
cd /home/<user>/barbearia-chatbot
git pull origin main
docker compose up -d --build
```

---

## Setup da VM (Passo a Passo)

### 1. Criar instância no GCP Console
- Tipo: `e2-small`
- Região: `southamerica-east1` (São Paulo) ou `us-central1` (mais barata)
- SO: Ubuntu 22.04 LTS
- Disco: 20 GB SSD (padrão)
- Firewall: habilitar HTTP e HTTPS

### 2. Firewall GCP
Regras de entrada: TCP 80, TCP 443, TCP 22 (já existe por padrão)

### 3. Na VM via SSH
```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# (reconectar SSH após isso)

# Clonar repositório
git clone <URL_DO_REPO> barbearia-chatbot
cd barbearia-chatbot

# Criar arquivos de env de produção
cp backend/.env.example backend/.env.production
# editar backend/.env.production com valores reais

# Subir os containers
docker compose up -d --build
```

### 4. DNS
No provedor do domínio, criar registros A:
- `virtualbarber.shop` → IP externo da VM
- `api.virtualbarber.shop` → IP externo da VM

### 5. GitHub Webhook
Settings → Webhooks → Add webhook:
- Payload URL: `https://api.virtualbarber.shop/deploy`
- Content type: `application/json`
- Secret: valor de `WEBHOOK_SECRET`
- Evento: `push` → branch `main`

---

## Variáveis de Ambiente em Produção

### `backend/.env.production` (valores a preencher)
```
APP_ENV=production
DATABASE_URL=<neon-connection-string>
JWT_SECRET=<segredo-forte>
ENCRYPTION_KEY=<chave-fernet>
CORS_ALLOWED_ORIGINS=https://virtualbarber.shop
FRONTEND_URL=https://virtualbarber.shop
BACKEND_PUBLIC_BASE_URL=https://api.virtualbarber.shop
BOOKING_PUBLIC_BASE_URL=https://virtualbarber.shop
MERCADOPAGO_WEBHOOK_SECRET=<valor>
MERCADOPAGO_WEBHOOK_TOKEN=<valor>
INTERNAL_REMINDER_TOKEN=<valor>
EMAIL_FROM=noreply@virtualbarber.shop
SMTP_HOST=<smtp>
SMTP_PORT=587
SMTP_USER=<usuario>
SMTP_PASSWORD=<senha>
DOCS_USER=admin
DOCS_PASS=<senha-forte>
```

### `frontend/.env.production`
```
NEXT_PUBLIC_API_URL=https://api.virtualbarber.shop
```

---

## Troca de Domínio no Futuro

1. Atualizar registros DNS no novo domínio
2. Editar `Caddyfile` (2 linhas)
3. Atualizar `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `BOOKING_PUBLIC_BASE_URL` no `.env.production`
4. Atualizar `NEXT_PUBLIC_API_URL` no `.env.production` do frontend
5. `docker compose up -d --build`
6. Atualizar URL do webhook no GitHub

---

## Fora do Escopo

- Configuração de SMTP (depende do provedor escolhido)
- Configuração de MegaAPI/WhatsApp (credenciais externas)
- Monitoramento/alertas (pode ser adicionado depois)
- Backups automáticos (Neon gerencia o banco; arquivos da VM não são críticos)
