# Spec: Segurança + Generalização do SaaS

**Data:** 2026-03-23
**Projeto:** barbearia-chatbot (SaaS de agendamentos)
**Escopo:** Spec 1 de 2 — Segurança (Fase 1) + Generalização (Fase 2)

---

## Contexto

O sistema é um SaaS multi-tenant de agendamentos, atualmente focado em barbearias. Está em produção numa VPS com banco PostgreSQL no Neon. O objetivo deste spec é:

1. Corrigir vulnerabilidades de segurança críticas antes de escalar a venda
2. Tornar o sistema genérico para qualquer serviço com agendamento (salão de beleza, estética automotiva, etc.)

A abordagem escolhida é **Fase 1 antes da Fase 2**: segurança primeiro (deploy independente), renomeação depois (deploy independente). Isso garante que senhas em plaintext sejam corrigidas o mais rápido possível.

---

## Fase 1: Segurança

### 1.1 Hashing de Senhas com bcrypt

**Problema atual:** A coluna `senha` na tabela `barbearias` armazena texto puro. Qualquer acesso indevido ao banco expõe todas as credenciais dos clientes.

**Solução:**

- Adicionar `passlib[bcrypt]` ao `backend/requirements.txt`
- Criar funções `hash_senha(plain: str) -> str` e `verificar_senha(plain: str, hashed: str) -> bool` em `backend/app/security.py`
- Sem alteração de schema: a coluna `senha String(255)` comporta o hash bcrypt (`$2b$...`, ~60 chars)
- Script de migração one-shot: lê todos os registros de `barbearias`, aplica `hash_senha()` e salva — executado uma única vez no deploy da Fase 1
- `backend/app/routers/auth.py`: login passa a usar `verificar_senha()` em vez de comparação direta
- Criação de novo estabelecimento (`POST /estabelecimentos/`) também passa a usar `hash_senha()`

**Impacto:** Nenhuma mudança de interface. Usuários continuam logando normalmente.

---

### 1.2 JWT com PyJWT + Suporte a Logout Real

**Problema atual:** O JWT é implementado manualmente (HMAC + base64 hand-rolled em `security.py`). Não há suporte a revogação — logout no frontend apenas apaga o cookie/localStorage, mas o token continua válido até expirar.

**Solução:**

- Adicionar `PyJWT` ao `backend/requirements.txt`
- Refatorar `backend/app/security.py`: `create_access_token()` e `decode_access_token()` passam a usar `jwt.encode()` / `jwt.decode()` — mesma interface pública, apenas a implementação interna muda
- Adicionar campo `jti` (JWT ID, UUID v4) ao payload de cada token
- Nova tabela `token_blacklist`:
  ```
  token_blacklist(
    jti       VARCHAR(36) PRIMARY KEY,
    expires_at TIMESTAMP NOT NULL,
    INDEX(expires_at)
  )
  ```
- `decode_access_token()` verifica se o `jti` está na blacklist antes de aceitar o token
- Novo endpoint `POST /auth/logout`: insere o `jti` na blacklist e retorna 200
- Job de limpeza periódica: deleta registros com `expires_at < now()` (pode ser uma rota interna chamada por cron no VPS, similar ao `ReminderJob` existente)

**Impacto:** Interface de login/logout inalterada. Tokens existentes continuam válidos até expirar (sem blacklist retroativa).

---

### 1.3 Rate Limiting

**Problema atual:** Sem limitação de requisições. Endpoints de login e agendamento público estão expostos a brute-force e abuso.

**Solução:**

- Adicionar `slowapi` ao `backend/requirements.txt`
- Configurar `Limiter` global no `backend/app/main.py`
- Limites:
  - `POST /auth/login`: **5 req/minuto por IP**
  - Endpoints públicos de agendamento (`POST /public/agendar`, `GET /public/[slug]`): **30 req/minuto por IP**
  - Demais endpoints autenticados: sem limite adicional (JWT já é barreira suficiente)
- Valores configuráveis via env vars: `RATE_LIMIT_LOGIN=5/minute`, `RATE_LIMIT_PUBLIC=30/minute`
- Resposta em caso de limite excedido: `429 Too Many Requests` com header `Retry-After`

---

### 1.4 Auditoria de Isolamento de Tenant

**Problema atual:** O isolamento de tenant é implementado via `X-Barbearia-Id` header + verificação no `deps.py`, mas não há testes automatizados que garantam que um tenant não acesse dados de outro.

**Solução:**

- Revisar todos os routers que recebem `barbearia_id` / `tenant_id` e garantir que a dependência `get_current_barbearia` (futuramente `get_current_estabelecimento`) é sempre usada — sem rotas que aceitam `barbearia_id` direto no body sem validação cruzada com o token
- Adicionar testes em `backend/tests/` cobrindo:
  - Tenant A não consegue ler agendamentos do Tenant B (espera 403)
  - Tenant A não consegue criar agendamentos no Tenant B (espera 403)
  - Token de admin não vaza dados de tenant específico sem `is_admin=True`
- Validar que todos os endpoints `admin` exigem `is_admin=True` no token

---

## Fase 2: Generalização

### 2.1 Renomeação no Banco de Dados

Uma única migration Alembic com as seguintes renomeações:

| De | Para |
|---|---|
| Tabela `barbearias` | `estabelecimentos` |
| Tabela `barbeiros` | `profissionais` |
| Coluna `barbearia_id` (todas as tabelas) | `estabelecimento_id` |
| Coluna `barbeiro_id` (em `agendamentos`) | `profissional_id` |
| Coluna `barbershop_id` (em `profissionais`) | `estabelecimento_id` |

Synonyms SQLAlchemy (`barbearia_id`, `barbeiro_id`, `barbershop_id`) mantidos no modelo durante a transição para não quebrar código legado durante o deploy, depois removidos em cleanup.

---

### 2.2 Campo `tipo_servico`

Nova coluna em `estabelecimentos`:

```
tipo_servico VARCHAR(50) NOT NULL DEFAULT 'barbearia'
```

Valores iniciais suportados (extensível, sem enum forçado no BD):

| Valor | Profissional | Exemplo de serviço |
|---|---|---|
| `barbearia` | Barbeiro | Corte |
| `salao_beleza` | Atendente | Serviço |
| `estetica_automotiva` | Detailer | Serviço |

A migration seta `tipo_servico = 'barbearia'` para todos os registros existentes.

---

### 2.3 Vocabulário Adaptativo no Frontend

- Novo arquivo `frontend/lib/vocab.ts` — único lugar para definir o vocabulário por `tipo_servico`:
  ```ts
  export const vocab = {
    barbearia: { profissional: "Barbeiro", servico: "Corte" },
    salao_beleza: { profissional: "Atendente", servico: "Serviço" },
    estetica_automotiva: { profissional: "Detailer", servico: "Serviço" },
  }
  ```
- O `tipo_servico` do estabelecimento logado é retornado no payload do JWT ou num endpoint de perfil
- Componentes que exibem "Barbeiro", "Barbearia" etc. passam a consultar `vocab[tipo_servico]`

---

### 2.4 Atualização de Código

**Backend:**

- Models: `Barbearia` → `Estabelecimento`, `Barbeiro` → `Profissional`
- Routers: `/barbearias/` → `/estabelecimentos/`, `/barbeiros/` → `/profissionais/`
- Schemas Pydantic: renomeados correspondentemente
- `deps.py`: `get_current_barbearia` → `get_current_estabelecimento`
- Variável de ambiente `ADMIN_USUARIO` permanece; apenas nomes internos mudam

**Frontend:**

- Chamadas de API para `/barbearias/` → `/estabelecimentos/`, `/barbeiros/` → `/profissionais/`
- Labels e textos passam a usar `vocab.ts`
- Rotas de páginas (`/admin`, `/gestao`, etc.) não mudam — são opacas ao tipo de serviço
- Nenhuma mudança visual além dos textos

---

## Relatório de Mudanças (a gerar no final da implementação)

Ao fim de cada fase, será gerado um relatório em texto com:
- Lista de arquivos modificados
- Migrations executadas
- Dependências adicionadas
- Endpoints novos/modificados
- Instruções de deploy (ordem de execução, env vars novas)

---

## Fora de Escopo deste Spec

- Rebrand (novo nome/identidade visual) — spec futuro
- Página de Configurações (senha, tema) — Spec 2
- Integração com gateway de pagamento
- Sistema de notificações além do WhatsApp existente
