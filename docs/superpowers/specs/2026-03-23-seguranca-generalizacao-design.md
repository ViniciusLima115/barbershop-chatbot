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
- `backend/app/routers/auth.py`: login passa a usar `verificar_senha()` em vez de comparação direta
- Paths de escrita que precisam usar `hash_senha()`:
  - `POST /barbearias/` (criação)
  - `PUT /barbearias/{id}` (atualização — campo `senha` opcional; só hashear se enviado)

**Script de migração one-shot de senhas existentes:**

- Executar **após** o deploy do código (para que `hash_senha` já exista no ambiente), **antes** de qualquer login novo
- Ordem exata de deploy:
  1. Deploy do código com `passlib`, `hash_senha`, `verificar_senha`, login usando `verificar_senha`
  2. Executar script de migração: lê cada registro de `barbearias`, aplica `hash_senha()`, salva
  3. A partir deste ponto, todos os logins passam pela verificação bcrypt
- O script deve processar registros em transação individual por registro — se falhar em um, os demais já migrados continuam válidos (bcrypt hash não conflita com a nova lógica de login)
- O script deve registrar em log quais IDs foram migrados com sucesso e quais falharam
- Antes de executar: criar snapshot/branch do banco Neon via `neonctl branch create` para rollback seguro se necessário

**Credencial admin (`ADMIN_SENHA`):** A senha do admin é uma variável de ambiente plaintext no VPS. Esse é um vetor de ataque diferente (acesso ao servidor, não ao banco). Está **fora do escopo** deste spec — mitigação recomendada é garantir que o VPS só seja acessível via SSH com chave e que o `.env` de produção tenha permissões restritas (chmod 600).

**Impacto:** Nenhuma mudança de interface. Usuários continuam logando normalmente.

---

### 1.2 JWT com PyJWT + Suporte a Logout Real

**Problema atual:** O JWT é implementado manualmente (HMAC + base64 hand-rolled em `security.py`). Não há suporte a revogação — logout no frontend apenas apaga o cookie/localStorage, mas o token continua válido até expirar.

**Solução:**

- Adicionar `PyJWT` ao `backend/requirements.txt`
- Refatorar `backend/app/security.py`: `create_access_token()` e `decode_access_token()` passam a usar `jwt.encode()` / `jwt.decode()` — mesma interface pública, apenas a implementação interna muda
- Adicionar campo `jti` (JWT ID, UUID v4) ao payload de cada token novo
- Nova tabela `token_blacklist` (modelo SQLAlchemy):

  ```python
  class TokenBlacklist(Base):
      __tablename__ = "token_blacklist"
      __table_args__ = (Index("ix_token_blacklist_expires_at", "expires_at"),)

      jti = Column(String(36), primary_key=True)
      expires_at = Column(DateTime, nullable=False)
  ```

- `decode_access_token()`:
  - Se o token não tiver campo `jti` (tokens emitidos antes do deploy), **ignorar a checagem de blacklist** e aceitar o token normalmente — sem quebrar usuários já logados no momento do deploy
  - Se tiver `jti`, verificar na blacklist antes de aceitar
- Novo endpoint `POST /auth/logout`: insere o `jti` do token corrente na blacklist e retorna 200
- Job de limpeza periódica: deleta registros com `expires_at < now()` via rota interna (padrão similar ao `ReminderJob` existente), chamada por cron no VPS

**Impacto:** Tokens emitidos antes do deploy continuam válidos até expirar (sem blacklist retroativa). Novos tokens terão suporte a logout real.

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

**Configuração para proxy reverso (nginx no VPS):**

O sistema roda atrás de nginx, então `request.client.host` retornaria `127.0.0.1` para todas as requisições, tornando o rate limit ineficaz. Solução:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

# Configurar o Limiter para ler X-Forwarded-For / X-Real-IP:
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# No nginx.conf, garantir que o header é passado:
# proxy_set_header X-Real-IP $remote_addr;
# proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

A configuração do nginx deve ser verificada/atualizada no deploy da Fase 1.

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

Uma única migration Alembic encadeada ao `head` atual com as seguintes renomeações:

| De | Para |
|---|---|
| Tabela `barbearias` | `estabelecimentos` |
| Tabela `barbeiros` | `profissionais` |
| Coluna `barbearia_id` (todas as tabelas) | `estabelecimento_id` |
| Coluna `barbeiro_id` (em `agendamentos`) | `profissional_id` |
| Coluna `barbershop_id` (em `profissionais`) | `estabelecimento_id` |

Synonyms SQLAlchemy (`barbearia_id`, `barbeiro_id`, `barbershop_id`) — já usados parcialmente no modelo `Barbeiro` — mantidos nos modelos durante o deploy da Fase 2 para não quebrar código interno que ainda referencia os nomes antigos. Serão removidos em um commit de cleanup **na mesma PR da Fase 2**, após confirmar que nenhum código usa os nomes antigos diretamente.

---

### 2.2 Campo `tipo_servico`

Nova coluna adicionada na mesma migration da 2.1:

```python
tipo_servico = Column(String(50), nullable=False, server_default="barbearia")
```

Migration seta `tipo_servico = 'barbearia'` para todos os registros existentes via `op.execute("UPDATE estabelecimentos SET tipo_servico = 'barbearia' WHERE tipo_servico IS NULL")`.

Valores iniciais suportados (extensível, sem enum forçado no BD):

| Valor | Profissional | Exemplo de serviço |
|---|---|---|
| `barbearia` | Barbeiro | Corte |
| `salao_beleza` | Atendente | Serviço |
| `estetica_automotiva` | Detailer | Serviço |

---

### 2.3 Vocabulário Adaptativo no Frontend

**Decisão:** `tipo_servico` será retornado em um **endpoint de perfil** (`GET /auth/me`), não embutido no JWT. Motivo: um admin pode alterar o `tipo_servico` de um tenant a qualquer momento; embutir no JWT exigiria re-login para refletir a mudança. O endpoint de perfil é chamado uma vez no carregamento do app e armazenado no contexto React — o custo de rede é mínimo.

- Novo arquivo `frontend/lib/vocab.ts`:
  ```ts
  export const vocab: Record<string, { profissional: string; estabelecimento: string }> = {
    barbearia: { profissional: "Barbeiro", estabelecimento: "Barbearia" },
    salao_beleza: { profissional: "Atendente", estabelecimento: "Salão" },
    estetica_automotiva: { profissional: "Detailer", estabelecimento: "Estética" },
  }
  export function getVocab(tipo: string) {
    return vocab[tipo] ?? vocab["barbearia"]
  }
  ```
- Componentes que exibem "Barbeiro", "Barbearia" etc. passam a consultar `getVocab(tipo_servico)`
- `GET /auth/me` retorna `{ id, nome, tipo_servico, plano, ... }` — novo endpoint leve no backend

---

### 2.4 Inventário Completo de Arquivos a Renomear/Atualizar

**Backend — models:**
- `backend/app/models/barbearia.py` → `estabelecimento.py` (classe `Barbearia` → `Estabelecimento`)
- `backend/app/models/barbeiro.py` → `profissional.py` (classe `Barbeiro` → `Profissional`)

**Backend — routers:**
- `backend/app/routes/barbearias.py` → `estabelecimentos.py`
- `backend/app/routes/barbeiros.py` → `profissionais.py`
- `backend/app/routes/barbearia_funcionamento.py` → `estabelecimento_funcionamento.py`

**Backend — services:**
- `backend/app/services/barbershop_hours_service.py` → `estabelecimento_hours_service.py`

**Backend — deps, schemas, main:**
- `backend/app/routes/deps.py`: `get_current_barbearia` → `get_current_estabelecimento`
- Todos os schemas Pydantic em `backend/app/schemas/` com prefixo `Barbearia`/`Barbeiro`
- `backend/app/main.py`: atualizar includes de routers

**Frontend:**
- Chamadas de API: `/barbearias/` → `/estabelecimentos/`, `/barbeiros/` → `/profissionais/`
- Labels e textos: usar `vocab.ts`
- Rotas de páginas (`/admin`, `/gestao`, etc.) não mudam

---

## Relatório de Mudanças

Ao fim de cada fase, gerar arquivo em `docs/superpowers/reports/YYYY-MM-DD-fase-N-changelog.md` com:
- Lista de arquivos modificados
- Migrations executadas (revision IDs Alembic)
- Dependências adicionadas ao `requirements.txt`
- Endpoints novos/modificados/removidos
- Env vars novas e seus valores padrão
- Instruções de deploy (ordem de execução)

---

## Fora de Escopo deste Spec

- Rebrand (novo nome/identidade visual) — spec futuro
- Página de Configurações (senha, tema) — Spec 2
- Proteção da credencial `ADMIN_SENHA` (env var plaintext no VPS) — mitigação via hardening do servidor, fora do escopo de código
- Integração com gateway de pagamento
- Sistema de notificações além do WhatsApp existente
