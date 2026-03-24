# Fase 1 — Security Hardening: Changelog

**Data:** 2026-03-23
**Branch:** claude/priceless-faraday
**Status:** Concluído

---

## Resumo Executivo

A Fase 1 do projeto de security hardening cobriu as tarefas 1–9 com foco em três pilares: proteção de credenciais em repouso (bcrypt), autenticação stateful com suporte a revogação de tokens (PyJWT + blacklist), e limitação de taxa no endpoint de autenticação (slowapi). Além disso, foram consolidados testes unitários para as primitivas de segurança e testes de isolamento de tenant para garantir que nenhum tenant consiga acessar dados de outro.

O resultado é um sistema em que senhas jamais são armazenadas em plaintext, tokens emitidos podem ser revogados imediatamente via logout, ataques de brute-force no `/auth/login` são contidos por rate limiting ciente de proxy reverso, e o perímetro de autorização multi-tenant é coberto por testes automatizados reproduzíveis.

---

## Mudanças por Área

### 1. Hashing de Senhas (bcrypt)

**Antes:** senhas armazenadas em plaintext no campo `barbearia.senha`.

**Depois:** toda senha é hasheada com bcrypt (custo padrão do passlib) via `hash_senha()`. A função `verificar_senha()` suporta transição transparente: se o hash começa com `$2b$` usa `CryptContext.verify`; caso contrário aplica `secrets.compare_digest` contra o valor plaintext legado e emite um `logging.warning`. Esse fallback deve ser removido após a execução do script de migração em produção.

Os endpoints de criação (`POST /barbearias/`) e atualização (`PUT /barbearias/{id}`) foram alterados para chamar `hash_senha()` antes de persistir a senha. O endpoint de login de tenant já usa `verificar_senha()`.

**Arquivos:** `backend/app/security.py`, `backend/app/routes/barbearias.py`, `backend/app/routes/auth.py`

---

### 2. JWT com PyJWT + Blacklist

**Antes:** implementação JWT hand-rolled sem biblioteca de validação formal e sem suporte a revogação.

**Depois:**

- `PyJWT 2.10.1` substitui a implementação manual. `create_access_token()` emite um campo `jti` (UUID v4) em cada token. `decode_access_token()` lança `ValueError` com mensagens tipadas para tokens expirados (`pyjwt.ExpiredSignatureError`) e inválidos (`pyjwt.InvalidTokenError`).
- A model `TokenBlacklist` (tabela `token_blacklist`) armazena pares `(jti, expires_at)` com chave primária no `jti` e índice em `expires_at` para facilitar limpeza futura de registros expirados.
- O endpoint `POST /auth/logout` extrai o `jti` do token autenticado e insere na blacklist usando `db.merge()` para idempotência. Tokens sem campo `jti` (emitidos antes da atualização) são aceitos normalmente — compatibilidade retroativa.
- A dependência `get_current_claims()` em `deps.py` consulta a blacklist antes de retornar as claims; se o `jti` estiver presente, retorna HTTP 401 com `"Token revogado."`.

**Arquivos:** `backend/app/security.py`, `backend/app/models/token_blacklist.py`, `backend/app/routes/auth.py`, `backend/app/routes/deps.py`

---

### 3. Rate Limiting (slowapi)

`backend/app/limiter.py` instancia um `Limiter` com key function customizada (`_get_real_ip`) que lê, em ordem de prioridade:

1. Header `X-Real-IP` (configuração padrão nginx `proxy_set_header X-Real-IP $remote_addr`)
2. Primeiro IP de `X-Forwarded-For`
3. Fallback para o peer TCP via `get_remote_address` do slowapi

O limite padrão é controlado pela variável de ambiente `RATE_LIMIT_LOGIN` (default: `5/minute`). O decorator `@limiter.limit(RATE_LIMIT_LOGIN)` é aplicado diretamente ao handler `POST /auth/login`. Uma segunda constante `RATE_LIMIT_PUBLIC` (`30/minute`) está definida para uso futuro nos endpoints públicos do chatbot.

**Arquivo:** `backend/app/limiter.py`, `backend/app/routes/auth.py`

---

### 4. Testes de Segurança (test_security.py)

`backend/tests/test_security.py` cobre as primitivas do módulo `security.py`:

| Teste | O que verifica |
|---|---|
| `test_hash_senha_retorna_bcrypt` | hash gerado começa com `$2b$` |
| `test_verificar_senha_correta` | bcrypt verifica senha correta |
| `test_verificar_senha_errada` | bcrypt rejeita senha errada |
| `test_hashes_diferentes_para_mesma_senha` | salt distinto a cada chamada |
| `test_verificar_senha_plaintext_correto` | fallback plaintext aceita credencial correta |
| `test_verificar_senha_plaintext_errado` | fallback plaintext rejeita credencial errada |
| `test_create_and_decode_token_tenant` | token de tenant carrega `sub`, `tenant_id`, `is_admin=False`, `jti` não nulo |
| `test_create_and_decode_token_admin` | token admin carrega `is_admin=True`, `tenant_id=None` |
| `test_token_expirado_levanta_erro` | token com `expires_minutes=-1` levanta `ValueError` |
| `test_token_adulterado_levanta_erro` | payload adulterado levanta `ValueError` |

---

### 5. Testes de Isolamento de Tenant (test_tenant_isolation.py)

`backend/tests/test_tenant_isolation.py` cria dois tenants independentes via fixture `dois_tenants` e valida que o perímetro de autorização via `tenant_id_from_header` bloqueia cross-tenant access:

| Teste | Cenário | HTTP esperado |
|---|---|---|
| `test_tenant_nao_ve_agenda_do_outro` | token de T1 + `X-Barbearia-Id` de T2 em `GET /agendamentos/` | 403 |
| `test_tenant_nao_ve_clientes_do_outro` | token de T1 + `X-Barbearia-Id` de T2 em `GET /clientes/` | 403 |
| `test_tenant_nao_ve_servicos_do_outro` | token de T1 + `X-Barbearia-Id` de T2 em `GET /servicos/` | 403 |
| `test_tenant_nao_cria_agendamento_em_outro_tenant` | token de T1 + `X-Barbearia-Id` de T2 em `POST /agendamentos/` | 403 |
| `test_endpoint_admin_bloqueia_tenant` | token de tenant em `GET /barbearias/` (rota admin) | 403 |

---

### 6. Script de Migração (migrate_senhas.py)

Script one-shot para migrar senhas plaintext existentes no banco de produção para bcrypt. Funciona em modo real (commit) ou `--dry-run` (apenas log). Itera sobre todos os registros de `Barbearia`, ignora senhas vazias e senhas já hasheadas (`$2b$`), e faz rollback por registro em caso de erro, reportando contadores ao final. Encerra com `sys.exit(1)` se qualquer erro ocorrer.

**Arquivo:** `backend/scripts/migrate_senhas.py`

---

## Arquivos Modificados / Criados

| Arquivo | Operação | Descrição |
|---|---|---|
| `backend/app/security.py` | Modificado | Adicionado `hash_senha`, `verificar_senha` com bcrypt + fallback plaintext; substituída implementação JWT por PyJWT; adicionado campo `jti` em `create_access_token` e `TokenClaims` |
| `backend/app/limiter.py` | Criado | Instância `Limiter` slowapi com resolução de IP real via proxy reverso; constantes `RATE_LIMIT_LOGIN` e `RATE_LIMIT_PUBLIC` configuráveis por env |
| `backend/app/models/token_blacklist.py` | Criado | Model SQLAlchemy `TokenBlacklist` (tabela `token_blacklist`) com PK em `jti` e índice em `expires_at` |
| `backend/app/routes/auth.py` | Modificado | Adicionado `POST /auth/logout` com invalidação por blacklist; `POST /auth/login` decorado com `@limiter.limit(RATE_LIMIT_LOGIN)` |
| `backend/app/routes/deps.py` | Modificado | `get_current_claims` consulta `TokenBlacklist`; tokens com `jti` na blacklist retornam HTTP 401 |
| `backend/app/routes/barbearias.py` | Modificado | Endpoints `POST /barbearias/` e `PUT /barbearias/{id}` chamam `hash_senha()` antes de persistir; campo senha removido do schema de resposta |
| `backend/tests/test_security.py` | Criado | 10 testes unitários cobrindo bcrypt, fallback plaintext e JWT (emissão, decode, expiração, adulteração) |
| `backend/tests/test_tenant_isolation.py` | Criado | 5 testes de isolamento de tenant verificando que cross-tenant access retorna HTTP 403 |
| `backend/scripts/migrate_senhas.py` | Criado | Script one-shot de migração de senhas plaintext para bcrypt, com suporte a `--dry-run` |
| `backend/requirements.txt` | Modificado | Adicionados `passlib[bcrypt]==1.7.4`, `bcrypt==4.0.1`, `PyJWT==2.10.1`, `slowapi==0.1.9` |

---

## Dependências Adicionadas

| Pacote | Versão | Motivo |
|---|---|---|
| `passlib[bcrypt]` | 1.7.4 | Hash bcrypt para senhas via `CryptContext`; provê API de alto nível com suporte a `deprecated="auto"` |
| `bcrypt` | 4.0.1 | Pinado explicitamente para garantir compatibilidade com passlib (versões mais recentes do bcrypt quebraram a ABI) |
| `PyJWT` | 2.10.1 | Substituição da implementação JWT hand-rolled; validação formal de assinatura, expiração e claims |
| `slowapi` | 0.1.9 | Rate limiting para FastAPI/Starlette; integração nativa via decorator e middleware |

---

## Roteiro de Deploy

1. **Snapshot do banco de produção** antes de qualquer alteração:
   ```bash
   neonctl branch create --name pre-bcrypt-migration
   ```
2. **Deploy do código** (branch `claude/priceless-faraday` → main → Railway/Render).
   Neste ponto o sistema já aceita login com senhas plaintext (fallback ativo) e novas senhas já são criadas com bcrypt.
3. **Criar tabela `token_blacklist`** via Alembic ou DDL manual:
   ```sql
   CREATE TABLE token_blacklist (
       jti VARCHAR(36) PRIMARY KEY,
       expires_at TIMESTAMP NOT NULL
   );
   CREATE INDEX ix_token_blacklist_expires_at ON token_blacklist (expires_at);
   ```
4. **Executar o script de migração** de senhas:
   ```bash
   # Validar antes (sem commit):
   python backend/scripts/migrate_senhas.py --dry-run

   # Executar em produção:
   python backend/scripts/migrate_senhas.py
   ```
5. **Remover o fallback plaintext** em `security.py` após confirmar que todos os registros foram migrados (verificar log do script: `Erros: 0`).
6. **Configurar variáveis de ambiente** no serviço de produção:
   - `JWT_SECRET` — segredo forte, nunca o default `change-me-in-production`
   - `RATE_LIMIT_LOGIN` — ajustar conforme tráfego esperado (default: `5/minute`)
   - `JWT_EXPIRES_MINUTES` — opcional, default `480` (8 horas)
7. **Verificar nginx** com `proxy_set_header X-Real-IP $remote_addr` para que o rate limiter use o IP correto do cliente, não o IP do proxy.

---

## Notas Técnicas

**Transição bcrypt (fallback plaintext):** A função `verificar_senha` detecta hashes bcrypt pelo prefixo `$2b$`. Senhas ainda não migradas são comparadas com `secrets.compare_digest` (timing-safe). Um `logging.warning` é emitido a cada verificação plaintext para rastrear contas não migradas nos logs de produção. O fallback deve ser removido assim que `migrate_senhas.py` reportar `Erros: 0` em produção.

**Compatibilidade retroativa de tokens (jti):** O campo `jti` em `TokenClaims` é tipado como `jti: str | None = None`. Tokens emitidos antes desta atualização não possuem o campo e são aceitos normalmente — a consulta à blacklist em `get_current_claims` é executada apenas se `claims.jti` for não nulo. Isso evita interrupção de sessões ativas no momento do deploy.

**Idempotência do logout:** O endpoint de logout usa `db.merge()` ao inserir na blacklist, o que evita erro de chave duplicada caso o mesmo token seja enviado duas vezes para `/auth/logout`.

**Limpeza da blacklist:** A tabela `token_blacklist` acumula registros até que sejam removidos manualmente. O índice em `expires_at` permite uma query de limpeza eficiente a ser agendada periodicamente:
```sql
DELETE FROM token_blacklist WHERE expires_at < NOW();
```
Essa tarefa de manutenção não foi implementada na Fase 1 e deve ser adicionada na Fase 2 (ex: via APScheduler, que já é dependência do projeto).

**Rate limiter e ambiente de testes:** O `SlowAPIMiddleware` deve ser registrado no app FastAPI de produção. Em ambiente de testes, o limiter pode ser desabilitado ou o state inicializado manualmente para evitar `AttributeError` no `request.state`.
