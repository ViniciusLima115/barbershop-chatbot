# Segurança + Generalização do SaaS — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir vulnerabilidades críticas de segurança (senhas em plaintext, JWT hand-rolled, sem rate limiting) e generalizar o sistema para qualquer serviço de agendamento além de barbearia.

**Architecture:** Duas fases de deploy independentes. Fase 1 aplica segurança sem mudar nomes nem URLs. Fase 2 renomeia tabelas/modelos/rotas via funções `_ensure_*` em `database.py` (padrão já adotado no projeto — sem Alembic). Cada fase termina com um relatório de changelog.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL (Neon), `passlib[bcrypt]`, `PyJWT`, `slowapi`, Next.js, TypeScript

---

## Mapa de Arquivos

### Fase 1 — Segurança

| Ação | Arquivo |
|------|---------|
| Criar | `backend/app/limiter.py` (módulo compartilhado do slowapi) |
| Modificar | `backend/app/security.py` |
| Modificar | `backend/requirements.txt` |
| Modificar | `backend/app/routes/auth.py` |
| Modificar | `backend/app/routes/barbearias.py` |
| Modificar | `backend/app/database.py` |
| Modificar | `backend/app/routes/deps.py` |
| Modificar | `backend/app/main.py` |
| Criar | `backend/app/models/token_blacklist.py` |
| Modificar | `backend/app/models/__init__.py` |
| Criar | `backend/scripts/migrate_senhas.py` |
| Criar | `backend/tests/test_security.py` |
| Criar | `backend/tests/test_rate_limit.py` |
| Criar | `backend/tests/test_tenant_isolation.py` |
| Modificar | `backend/tests/conftest.py` |
| Modificar | `backend/tests/test_auth_barbearias.py` |

### Fase 2 — Generalização

| Ação | Arquivo |
|------|---------|
| Renomear/Modificar | `backend/app/models/barbearia.py` → `estabelecimento.py` |
| Renomear/Modificar | `backend/app/models/barbeiro.py` → `profissional.py` |
| Modificar | `backend/app/models/agendamento.py` (FKs + index) |
| Modificar | `backend/app/models/cliente.py` (FK) |
| Modificar | `backend/app/models/servico.py` (FK + synonym) |
| Modificar | `backend/app/models/__init__.py` |
| Modificar | `backend/app/database.py` |
| Renomear/Modificar | `backend/app/routes/barbearias.py` → `estabelecimentos.py` |
| Renomear/Modificar | `backend/app/routes/barbeiros.py` → `profissionais.py` |
| Renomear/Modificar | `backend/app/routes/barbearia_funcionamento.py` → `estabelecimento_funcionamento.py` |
| Renomear/Modificar | `backend/app/services/barbershop_hours_service.py` → `estabelecimento_hours_service.py` |
| Modificar | `backend/app/schemas/barbearia.py` (renomear classes) |
| Modificar | `backend/app/schemas/barbeiro.py` (renomear classes, se existir) |
| Modificar | `backend/app/routes/deps.py` |
| Modificar | `backend/app/main.py` |
| Modificar | `backend/app/routes/auth.py` |
| Modificar | `backend/tests/conftest.py` |
| Criar | `frontend/lib/vocab.ts` |
| Modificar | `frontend/services/api.ts` |
| Modificar | `frontend/services/barbershops-admin.ts` |
| Modificar | Componentes frontend que exibem textos "Barbeiro"/"Barbearia" |

---

## ═══════════════════════════════════════
## FASE 1: SEGURANÇA
## ═══════════════════════════════════════

---

## Task 1: Helpers de bcrypt em security.py

**Files:**
- Modify: `backend/app/security.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1.1: Adicionar dependência**

  Em `backend/requirements.txt`, adicionar:
  ```
  passlib[bcrypt]==1.7.4
  ```
  Rodar no virtualenv: `pip install passlib[bcrypt]==1.7.4`

- [ ] **Step 1.2: Escrever o teste que vai falhar**

  Criar `backend/tests/test_security.py`:
  ```python
  import pytest
  from app.security import hash_senha, verificar_senha


  def test_hash_senha_retorna_bcrypt():
      h = hash_senha("minha-senha")
      assert h.startswith("$2b$")


  def test_verificar_senha_correta():
      h = hash_senha("minha-senha")
      assert verificar_senha("minha-senha", h) is True


  def test_verificar_senha_errada():
      h = hash_senha("minha-senha")
      assert verificar_senha("senha-errada", h) is False


  def test_hashes_diferentes_para_mesma_senha():
      h1 = hash_senha("abc")
      h2 = hash_senha("abc")
      assert h1 != h2  # salt diferente a cada chamada
  ```

- [ ] **Step 1.3: Rodar e confirmar falha**

  ```bash
  cd backend && python -m pytest tests/test_security.py -v
  ```
  Esperado: `ImportError: cannot import name 'hash_senha'`

- [ ] **Step 1.4: Implementar em security.py**

  Adicionar no topo de `backend/app/security.py` (antes das funções JWT):
  ```python
  import secrets as _secrets
  from passlib.context import CryptContext

  _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


  def hash_senha(plain: str) -> str:
      return _pwd_context.hash(plain)


  def verificar_senha(plain: str, hashed: str) -> bool:
      """
      Verifica senha suportando transição: aceita bcrypt ($2b$) ou plaintext legado.
      O fallback plaintext é removido após rodar migrate_senhas.py em produção.
      """
      if hashed and hashed.startswith("$2b$"):
          return _pwd_context.verify(plain, hashed)
      # Fallback para senhas ainda não migradas (plaintext)
      return _secrets.compare_digest(plain, hashed or "")
  ```

  **Nota de deploy:** O fallback plaintext em `verificar_senha` garante que nenhum usuário fica bloqueado durante o deploy + migração. Após confirmar que `migrate_senhas.py` rodou com sucesso em produção (Erros: 0), remover o bloco `if hashed and hashed.startswith("$2b$")` e deixar apenas `return _pwd_context.verify(plain, hashed)`.

- [ ] **Step 1.5: Rodar e confirmar aprovação**

  ```bash
  cd backend && python -m pytest tests/test_security.py -v
  ```
  Esperado: 4 testes PASS

- [ ] **Step 1.6: Commit**

  ```bash
  git add backend/requirements.txt backend/app/security.py backend/tests/test_security.py
  git commit -m "feat(security): adicionar helpers hash_senha/verificar_senha com bcrypt"
  ```

---

## Task 2: Atualizar login para usar verificar_senha

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_auth_barbearias.py`

**Contexto:** O login atual usa `secrets.compare_digest(barbearia.senha, senha)` — comparação direta de plaintext. Após esta task, o login passa a usar `verificar_senha()`. Os testes que criam `Barbearia(senha="senha123")` precisam criar com a senha hasheada.

- [ ] **Step 2.1: Atualizar conftest para hashear senhas nos fixtures**

  Em `backend/tests/conftest.py`, no início do arquivo:
  ```python
  from app.security import hash_senha  # adicionar import
  ```

  No fixture `dados_base`, onde existe `Barbearia(nome="Barbearia Teste", ...)`, não há campo senha — ok, manter.

  No fixture `make_tenant_headers`, não mexe em senha — ok.

- [ ] **Step 2.2: Escrever teste que vai falhar para o novo login**

  Em `backend/tests/test_auth_barbearias.py`, encontrar `test_auth_login_tenant_sucesso_e_senha_invalida` e modificar a fixture de criação de barbearia para usar hash:

  ```python
  from app.security import hash_senha  # adicionar import no topo

  def test_auth_login_tenant_sucesso_e_senha_invalida(client, db_session):
      barbearia = Barbearia(
          nome="Barbearia Login",
          login="barbearia.login",
          senha=hash_senha("senha123"),  # <- hash aqui
          plano="basico",
          endereco="Rua A",
      )
      db_session.add(barbearia)
      db_session.commit()
      db_session.refresh(barbearia)

      sucesso = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "senha123"})
      assert sucesso.status_code == 200

      invalido = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "errada"})
      assert invalido.status_code == 401
  ```

- [ ] **Step 2.3: Rodar e confirmar falha**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py::test_auth_login_tenant_sucesso_e_senha_invalida -v
  ```
  Esperado: FAIL — login com senha correta retorna 401 (ainda compara plaintext hash com "senha123")

- [ ] **Step 2.4: Atualizar auth.py para usar verificar_senha**

  Em `backend/app/routes/auth.py`:

  ```python
  # Adicionar import
  from app.security import create_access_token, verificar_senha

  # Substituir no bloco do login de tenant:
  # ANTES:
  # if not secrets.compare_digest(barbearia.senha, senha):
  # DEPOIS:
  if not verificar_senha(senha, barbearia.senha):
      raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")
  ```

  Remover `import secrets` se não for mais usado em outro lugar do arquivo (checar — ainda é usado em `admin_check`).

- [ ] **Step 2.5: Rodar todos os testes de auth**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py -v
  ```
  Esperado: todos PASS

- [ ] **Step 2.6: Commit**

  ```bash
  git add backend/app/routes/auth.py backend/tests/test_auth_barbearias.py backend/tests/conftest.py
  git commit -m "feat(auth): usar verificar_senha bcrypt no login de tenant"
  ```

---

## Task 3: Hashear senha nos endpoints de criação/atualização de barbearia

**Files:**
- Modify: `backend/app/routes/barbearias.py`
- Modify: `backend/tests/test_auth_barbearias.py`

**Contexto:** `POST /barbearias/` salva `senha=dados.senha` diretamente. `PUT /barbearias/{id}` faz `barbearia.senha = dados.senha`. Ambos precisam hashear.

- [ ] **Step 3.1: Escrever teste que verifica que a senha salva é hash**

  Adicionar em `backend/tests/test_auth_barbearias.py`:
  ```python
  def test_barbearias_crud_cria_com_senha_hasheada(client, db_session, make_tenant_headers):
      from app.security import verificar_senha
      admin_headers = make_tenant_headers(is_admin=True)

      payload = {
          "nome": "Teste Hash",
          "login": "teste.hash",
          "senha": "senha_plain",
          "plano": "basico",
          "status_manual": "ativo",
          "vencimento_em": "2027-01-01",
          "trial_ativo": False,
          "pagamento_recusado": False,
          "endereco": "Rua B",
      }
      resp = client.post("/barbearias/", json=payload, headers=admin_headers)
      assert resp.status_code == 200

      from app.models.barbearia import Barbearia
      criada = db_session.query(Barbearia).filter(Barbearia.login == "teste.hash").first()
      assert criada is not None
      assert criada.senha != "senha_plain"  # não plaintext
      assert verificar_senha("senha_plain", criada.senha)  # hash válido


  def test_barbearias_crud_atualiza_com_senha_hasheada(client, db_session, make_tenant_headers):
      from app.security import verificar_senha, hash_senha
      from app.models.barbearia import Barbearia

      admin_headers = make_tenant_headers(is_admin=True)
      barbearia = Barbearia(
          nome="Para Atualizar",
          login="para.atualizar",
          senha=hash_senha("senha_original"),
          plano="basico",
          endereco="Rua C",
      )
      db_session.add(barbearia)
      db_session.commit()
      db_session.refresh(barbearia)

      payload = {
          "nome": "Para Atualizar",
          "login": "para.atualizar",
          "senha": "senha_nova",
          "plano": "basico",
          "status_manual": "ativo",
          "vencimento_em": "2027-01-01",
          "trial_ativo": False,
          "pagamento_recusado": False,
          "endereco": "Rua C",
      }
      resp = client.put(f"/barbearias/{barbearia.id}", json=payload, headers=admin_headers)
      assert resp.status_code == 200

      db_session.refresh(barbearia)
      assert barbearia.senha != "senha_nova"
      assert verificar_senha("senha_nova", barbearia.senha)
  ```

- [ ] **Step 3.2: Rodar e confirmar falha**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py::test_barbearias_crud_cria_com_senha_hasheada tests/test_auth_barbearias.py::test_barbearias_crud_atualiza_com_senha_hasheada -v
  ```
  Esperado: FAIL

- [ ] **Step 3.3: Atualizar barbearias.py**

  Em `backend/app/routes/barbearias.py`:

  ```python
  # Adicionar import
  from app.security import hash_senha

  # No endpoint criar(), substituir:
  # senha=dados.senha,
  senha=hash_senha(dados.senha),

  # No endpoint atualizar(), substituir:
  # barbearia.senha = dados.senha
  barbearia.senha = hash_senha(dados.senha)
  ```

  **Nota:** O schema `BarbeariaAdminUpdate` tem `senha: str` (obrigatório). Isso significa que toda atualização via PUT exige a senha. Esse comportamento existente é mantido — o hash é aplicado incondicionalmente. Se no futuro a senha se tornar opcional no schema, basta adicionar `if dados.senha: barbearia.senha = hash_senha(dados.senha)`.

- [ ] **Step 3.4: Rodar testes**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py -v
  ```
  Esperado: todos PASS

- [ ] **Step 3.5: Commit**

  ```bash
  git add backend/app/routes/barbearias.py backend/tests/test_auth_barbearias.py
  git commit -m "feat(barbearias): hashear senha nos endpoints POST e PUT"
  ```

---

## Task 4: Script de migração one-shot das senhas existentes

**Files:**
- Create: `backend/scripts/migrate_senhas.py`

**Contexto:** Senhas em produção estão em plaintext. Este script deve ser executado **uma única vez** no deploy da Fase 1, **após** o deploy do código (com `hash_senha` disponível), **antes** de qualquer login novo. Criar snapshot Neon antes de rodar.

- [ ] **Step 4.1: Criar o script**

  Criar `backend/scripts/migrate_senhas.py`:
  ```python
  #!/usr/bin/env python3
  """
  Script one-shot: migra senhas plaintext para bcrypt.

  Uso:
    python scripts/migrate_senhas.py          # modo real (commit no banco)
    python scripts/migrate_senhas.py --dry-run  # apenas loga, não salva

  Pré-requisitos:
    - DATABASE_URL configurada (backend/.env ou env var)
    - Executar APÓS deploy do código com hash_senha disponível
    - Criar snapshot Neon antes: neonctl branch create --name pre-bcrypt-migration
  """
  import sys
  import os
  from pathlib import Path

  # Permitir importar app.* sem instalar o pacote
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

  # Carregar .env
  from dotenv import load_dotenv
  load_dotenv(Path(__file__).resolve().parents[1] / ".env")
  load_dotenv(Path(__file__).resolve().parents[2] / ".env")

  from sqlalchemy.orm import Session
  from app.database import SessionLocal
  from app.models.barbearia import Barbearia
  from app.security import hash_senha, verificar_senha

  DRY_RUN = "--dry-run" in sys.argv


  def is_already_hashed(senha: str | None) -> bool:
      return bool(senha and senha.startswith("$2b$"))


  def main():
      print(f"{'[DRY-RUN] ' if DRY_RUN else ''}Iniciando migração de senhas...")
      db: Session = SessionLocal()
      try:
          barbearias = db.query(Barbearia).all()
          total = len(barbearias)
          migradas = 0
          ignoradas = 0
          erros = 0

          for b in barbearias:
              if not b.senha:
                  print(f"  [SKIP] id={b.id} login={b.login} — senha vazia")
                  ignoradas += 1
                  continue

              if is_already_hashed(b.senha):
                  print(f"  [OK]   id={b.id} login={b.login} — já hasheada")
                  ignoradas += 1
                  continue

              try:
                  if not DRY_RUN:
                      b.senha = hash_senha(b.senha)
                      db.commit()
                  print(f"  [{'SIMULADO' if DRY_RUN else 'MIGRADO'}] id={b.id} login={b.login}")
                  migradas += 1
              except Exception as exc:
                  db.rollback()
                  print(f"  [ERRO]  id={b.id} login={b.login} — {exc}")
                  erros += 1

      finally:
          db.close()

      print(f"\nTotal: {total} | Migradas: {migradas} | Ignoradas: {ignoradas} | Erros: {erros}")
      if erros > 0:
          sys.exit(1)


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 4.2: Testar em dry-run (local)**

  ```bash
  cd backend && python scripts/migrate_senhas.py --dry-run
  ```
  Esperado: lista as barbearias sem alterar nada, `Erros: 0`

- [ ] **Step 4.3: Commit**

  ```bash
  git add backend/scripts/migrate_senhas.py
  git commit -m "feat(scripts): adicionar migrate_senhas.py para migração one-shot de bcrypt"
  ```

---

## Task 5: Refatorar JWT para usar PyJWT + campo jti

**Files:**
- Modify: `backend/app/security.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/test_security.py`

**Contexto:** O JWT atual é hand-rolled. `create_access_token` e `decode_access_token` passam a usar `PyJWT`. A interface pública (parâmetros e retorno) não muda — só a implementação interna. Adicionar campo `jti` (UUID v4) ao payload.

- [ ] **Step 5.1: Adicionar PyJWT ao requirements.txt**

  Em `backend/requirements.txt`:
  ```
  PyJWT==2.10.1
  ```
  Instalar: `pip install PyJWT==2.10.1`

- [ ] **Step 5.2: Adicionar `jti` ao modelo TokenClaims**

  Em `backend/app/security.py`, atualizar `TokenClaims`:
  ```python
  class TokenClaims(BaseModel):
      sub: str
      tenant_id: int | None = None
      is_admin: bool = False
      jti: str | None = None  # None em tokens antigos (sem jti)
      iat: int
      exp: int
  ```

- [ ] **Step 5.3: Escrever testes para o novo JWT**

  Adicionar em `backend/tests/test_security.py`:
  ```python
  from app.security import create_access_token, decode_access_token, TokenClaims
  import time


  def test_create_and_decode_token_tenant():
      token = create_access_token(sub="user1", tenant_id=42, is_admin=False)
      claims = decode_access_token(token)
      assert claims.sub == "user1"
      assert claims.tenant_id == 42
      assert claims.is_admin is False
      assert claims.jti is not None  # novo campo


  def test_create_and_decode_token_admin():
      token = create_access_token(sub="admin", tenant_id=None, is_admin=True)
      claims = decode_access_token(token)
      assert claims.is_admin is True
      assert claims.tenant_id is None


  def test_token_expirado_levanta_erro():
      token = create_access_token(sub="user", tenant_id=1, is_admin=False, expires_minutes=-1)
      with pytest.raises(ValueError, match="[Ee]xpirado|[Ee]xpired"):
          decode_access_token(token)


  def test_token_adulterado_levanta_erro():
      token = create_access_token(sub="user", tenant_id=1, is_admin=False)
      partes = token.split(".")
      token_adulterado = partes[0] + ".ADULTERADO." + partes[2]
      with pytest.raises(ValueError):
          decode_access_token(token_adulterado)
  ```

- [ ] **Step 5.4: Rodar e confirmar falha (jti não existe ainda)**

  ```bash
  cd backend && python -m pytest tests/test_security.py::test_create_and_decode_token_tenant -v
  ```

- [ ] **Step 5.5: Substituir implementação JWT em security.py**

  Substituir as funções `_b64url_encode`, `_b64url_decode`, `_assinar`, `_encode`, `create_access_token`, `decode_access_token` pelo seguinte:

  ```python
  import jwt as pyjwt
  from uuid import uuid4

  # Remover imports: base64, hashlib, hmac, json, time
  # Manter: os, from pydantic import BaseModel, passlib imports

  def create_access_token(
      sub: str,
      tenant_id: int | None,
      is_admin: bool,
      expires_minutes: int | None = None,
  ) -> str:
      import time
      now = int(time.time())
      ttl = expires_minutes if expires_minutes is not None else JWT_EXPIRES_MINUTES
      payload = {
          "sub": sub,
          "tenant_id": tenant_id,
          "is_admin": is_admin,
          "jti": str(uuid4()),
          "iat": now,
          "exp": now + (ttl * 60),
      }
      return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


  def decode_access_token(token: str) -> TokenClaims:
      try:
          payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
      except pyjwt.ExpiredSignatureError as exc:
          raise ValueError("Token expirado.") from exc
      except pyjwt.InvalidTokenError as exc:
          raise ValueError("Token invalido.") from exc
      return TokenClaims(**payload)
  ```

  Remover as funções `_b64url_encode`, `_b64url_decode`, `_assinar`, `_encode` e os imports `base64`, `hashlib`, `hmac`, `json`, `time` (mover `time` para dentro de `create_access_token` ou manter no topo).

- [ ] **Step 5.6: Rodar todos os testes de security**

  ```bash
  cd backend && python -m pytest tests/test_security.py -v
  ```
  Esperado: todos PASS

- [ ] **Step 5.7: Rodar todos os testes do projeto**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```
  Verificar que nenhum teste quebrou com a mudança do JWT.

- [ ] **Step 5.8: Commit**

  ```bash
  git add backend/requirements.txt backend/app/security.py backend/tests/test_security.py
  git commit -m "feat(security): substituir JWT hand-rolled por PyJWT com campo jti"
  ```

---

## Task 6: TokenBlacklist — modelo + criação de tabela

**Files:**
- Create: `backend/app/models/token_blacklist.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/database.py`

**Contexto:** O projeto não usa Alembic — gerencia migrações via funções `_ensure_*` em `database.py`. A tabela `token_blacklist` é criada via `Base.metadata.create_all` em novos installs e via `_ensure_token_blacklist_table()` em installs existentes.

- [ ] **Step 6.1: Criar model**

  Criar `backend/app/models/token_blacklist.py`:
  ```python
  from datetime import datetime

  from sqlalchemy import Column, DateTime, Index, String

  from app.database import Base


  class TokenBlacklist(Base):
      __tablename__ = "token_blacklist"
      __table_args__ = (Index("ix_token_blacklist_expires_at", "expires_at"),)

      jti = Column(String(36), primary_key=True)
      expires_at = Column(DateTime, nullable=False)
  ```

- [ ] **Step 6.2: Registrar no __init__.py dos models**

  Em `backend/app/models/__init__.py`, adicionar:
  ```python
  from app.models.token_blacklist import TokenBlacklist
  # e no __all__:
  "TokenBlacklist",
  ```

- [ ] **Step 6.3: Adicionar _ensure para deployments existentes**

  Em `backend/app/database.py`, adicionar a função (antes de `init_db`):
  ```python
  def _ensure_token_blacklist_table():
      try:
          with engine.begin() as conn:
              conn.execute(text(
                  "CREATE TABLE IF NOT EXISTS token_blacklist ("
                  "  jti VARCHAR(36) PRIMARY KEY,"
                  "  expires_at TIMESTAMP NOT NULL"
                  ")"
              ))
              conn.execute(text(
                  "CREATE INDEX IF NOT EXISTS ix_token_blacklist_expires_at "
                  "ON token_blacklist (expires_at)"
              ))
      except Exception:
          pass
  ```

  Em `init_db()`, adicionar chamada (depois de `_backfill_agendamentos_notification_defaults()`):
  ```python
  _ensure_token_blacklist_table()
  ```

  Também adicionar o import do model em `init_db()`:
  ```python
  from app.models import token_blacklist
  ```

- [ ] **Step 6.4: Adicionar import de TokenBlacklist em conftest.py**

  Em `backend/tests/conftest.py`, adicionar o import do modelo para que ele seja registrado no `Base.metadata` antes do `create_all`:
  ```python
  from app.models.token_blacklist import TokenBlacklist  # registra na metadata do SQLite
  ```
  Adicionar junto aos outros imports de models existentes.

- [ ] **Step 6.5: Verificar que a tabela é criada corretamente nos testes**

  ```bash
  cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Esperado: nenhum erro novo

- [ ] **Step 6.5: Commit**

  ```bash
  git add backend/app/models/token_blacklist.py backend/app/models/__init__.py backend/app/database.py
  git commit -m "feat(models): adicionar TokenBlacklist para suporte a logout real"
  ```

---

## Task 7: Endpoint de logout + checagem de blacklist

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/app/routes/deps.py`
- Modify: `backend/tests/test_auth_barbearias.py`

**Contexto:** O logout insere o `jti` do token na blacklist. A checagem ocorre em `deps.py` (em `get_current_claims`), não em `decode_access_token` — mantém `security.py` puro. Tokens sem `jti` (emitidos antes do deploy) são aceitos sem checagem.

- [ ] **Step 7.1: Escrever testes para logout**

  Adicionar em `backend/tests/test_auth_barbearias.py`:
  ```python
  def test_logout_invalida_token(client):
      # Login para obter token
      resp_login = client.post(
          "/auth/login",
          json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
      )
      token = resp_login.json()["access_token"]
      headers = {"Authorization": f"Bearer {token}"}

      # Antes do logout: acesso ok
      resp_antes = client.get("/barbearias/", headers=headers)
      assert resp_antes.status_code == 200

      # Logout
      resp_logout = client.post("/auth/logout", headers=headers)
      assert resp_logout.status_code == 200

      # Após logout: token rejeitado
      resp_depois = client.get("/barbearias/", headers=headers)
      assert resp_depois.status_code == 401


  def test_logout_sem_token_retorna_401(client):
      resp = client.post("/auth/logout")
      assert resp.status_code == 401
  ```

- [ ] **Step 7.2: Rodar e confirmar falha**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py::test_logout_invalida_token -v
  ```
  Esperado: FAIL — endpoint `/auth/logout` não existe

- [ ] **Step 7.3: Adicionar endpoint de logout em auth.py**

  Em `backend/app/routes/auth.py`:
  ```python
  from datetime import datetime
  from sqlalchemy.orm import Session
  from app.database import get_db
  from app.models.token_blacklist import TokenBlacklist
  from app.routes.deps import get_current_claims

  @router.post("/logout", status_code=200)
  def logout(
      claims: TokenClaims = Depends(get_current_claims),
      db: Session = Depends(get_db),
  ):
      if claims.jti:
          from datetime import datetime, timezone
          expires_at = datetime.utcfromtimestamp(claims.exp)  # UTC naive, consistente com utcnow()
          blacklisted = TokenBlacklist(jti=claims.jti, expires_at=expires_at)
          db.merge(blacklisted)  # merge para evitar erro se jti já existir
          db.commit()
      return {"detail": "Logout realizado com sucesso."}
  ```

- [ ] **Step 7.4: Adicionar checagem de blacklist em deps.py**

  Em `backend/app/routes/deps.py`, modificar `get_current_claims`:
  ```python
  from app.models.token_blacklist import TokenBlacklist

  def get_current_claims(
      credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
      db: Session = Depends(get_db),
  ) -> TokenClaims:
      if not credentials or credentials.scheme.lower() != "bearer":
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao obrigatoria.")

      try:
          claims = decode_access_token(credentials.credentials)
      except ValueError as exc:
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

      # Checar blacklist apenas se o token tem jti (tokens antigos sem jti são aceitos)
      if claims.jti:
          na_blacklist = db.query(TokenBlacklist).filter(TokenBlacklist.jti == claims.jti).first()
          if na_blacklist:
              raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revogado.")

      return claims
  ```

- [ ] **Step 7.5: Adicionar rota de logout ao conftest.py do app de teste**

  Em `backend/tests/conftest.py`, o fixture `app` inclui `auth.router` — o endpoint `/auth/logout` já estará disponível. Verificar que está incluído.

- [ ] **Step 7.6: Rodar testes de auth**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py -v
  ```
  Esperado: todos PASS (incluindo os dois novos de logout)

- [ ] **Step 7.7: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```
  Esperado: todos PASS

- [ ] **Step 7.8: Commit**

  ```bash
  git add backend/app/routes/auth.py backend/app/routes/deps.py backend/tests/test_auth_barbearias.py
  git commit -m "feat(auth): adicionar endpoint /auth/logout com invalidação de token via blacklist"
  ```

---

## Task 8: Rate limiting com slowapi

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/limiter.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routes/auth.py`
- Create: `backend/tests/test_rate_limit.py`

**Contexto:** O sistema roda atrás de nginx. O `slowapi` deve ler o IP real via `X-Real-IP`. Para evitar importação circular (`main.py` importa `auth.py`, que não pode importar `main.py`), o `Limiter` é instanciado em `backend/app/limiter.py` — um módulo sem dependências de app — e importado por ambos `main.py` e `auth.py`.

- [ ] **Step 8.1: Adicionar slowapi**

  Em `backend/requirements.txt`:
  ```
  slowapi==0.1.9
  ```
  Instalar: `pip install slowapi==0.1.9`

- [ ] **Step 8.2: Criar backend/app/limiter.py**

  Criar `backend/app/limiter.py`:
  ```python
  import os
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
  RATE_LIMIT_PUBLIC = os.getenv("RATE_LIMIT_PUBLIC", "30/minute")

  limiter = Limiter(key_func=get_remote_address)
  ```

- [ ] **Step 8.3: Configurar Limiter em main.py**

  Em `backend/app/main.py`, adicionar:
  ```python
  from slowapi import _rate_limit_exceeded_handler
  from slowapi.errors import RateLimitExceeded
  from app.limiter import limiter
  ```

  Após `app = FastAPI(...)`:
  ```python
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  ```

- [ ] **Step 8.4: Aplicar limite no endpoint de login**

  Em `backend/app/routes/auth.py`:
  ```python
  from fastapi import Request
  from app.limiter import limiter, RATE_LIMIT_LOGIN

  @router.post("/login", response_model=LoginResponse)
  @limiter.limit(RATE_LIMIT_LOGIN)
  def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
      # ... código existente sem mudança ...
  ```

  **Nota:** O decorator `@limiter.limit()` requer `request: Request` como primeiro parâmetro da função.

- [ ] **Step 8.5: Escrever teste de rate limit**

  Criar `backend/tests/test_rate_limit.py`:
  ```python
  import pytest
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.errors import RateLimitExceeded
  from slowapi.util import get_remote_address

  from app.database import get_db
  from app.routes import auth


  def make_limited_app(session_factory, limit: str = "2/minute"):
      """Cria app de teste com limite reduzido para testar rate limiting."""
      test_limiter = Limiter(key_func=get_remote_address, default_limits=[limit])
      test_app = FastAPI()
      test_app.state.limiter = test_limiter
      test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

      # Re-registrar o router de auth com o limiter de teste
      # Nota: simplificado — em produção o limiter é injetado via app.state
      test_app.include_router(auth.router)

      def override_get_db():
          db = session_factory()
          try:
              yield db
          finally:
              db.close()

      test_app.dependency_overrides[get_db] = override_get_db
      return test_app


  def test_login_retorna_429_apos_limite(session_factory):
      """Verificar que o endpoint de login retorna 429 após exceder o limite."""
      # Este teste verifica a presença do decorator, não o comportamento em tempo real
      # pois o TestClient não respeita limites de tempo do slowapi sem mock
      app = make_limited_app(session_factory)
      client = TestClient(app)

      # Fazer requisições até o limite
      for _ in range(2):
          r = client.post("/auth/login", json={"usuario": "x", "senha": "y"})
          assert r.status_code in (200, 401)  # antes do limite

      # A próxima deve ser bloqueada
      r = client.post("/auth/login", json={"usuario": "x", "senha": "y"})
      assert r.status_code == 429
  ```

- [ ] **Step 8.6: Rodar teste de rate limit**

  ```bash
  cd backend && python -m pytest tests/test_rate_limit.py -v
  ```
  **Nota:** O teste é um smoke test — verifica que o decorator está presente e retorna 429 ao exceder o limite dentro da mesma instância de teste. Não testa janelas de tempo reais.

- [ ] **Step 8.7: Instrução de configuração do nginx**

  Verificar que `/etc/nginx/sites-available/<site>` contém:
  ```nginx
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  ```
  Se não tiver, adicionar e rodar `sudo nginx -t && sudo systemctl reload nginx`.

- [ ] **Step 8.8: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```

- [ ] **Step 8.9: Commit**

  ```bash
  git add backend/requirements.txt backend/app/limiter.py backend/app/main.py \
          backend/app/routes/auth.py backend/tests/test_rate_limit.py
  git commit -m "feat(security): adicionar rate limiting com slowapi no endpoint de login"
  ```

---

## Task 9: Testes de isolamento de tenant

**Files:**
- Create: `backend/tests/test_tenant_isolation.py`

**Contexto:** Garantir que tenant A não acessa dados do tenant B. Os testes usam SQLite em memória via conftest existente.

- [ ] **Step 9.1: Criar arquivo de testes**

  Criar `backend/tests/test_tenant_isolation.py`:
  ```python
  """
  Testes de isolamento de tenant: garante que um tenant não acessa dados de outro.
  """
  import pytest
  from app.models.barbearia import Barbearia
  from app.models.barbeiro import Barbeiro
  from app.models.servico import Servico
  from app.models.agendamento import Agendamento
  from app.security import hash_senha
  from datetime import datetime, timedelta


  @pytest.fixture
  def dois_tenants(db_session):
      t1 = Barbearia(nome="Tenant Um", login="tenant.um", senha=hash_senha("senha1"), endereco="Rua 1")
      t2 = Barbearia(nome="Tenant Dois", login="tenant.dois", senha=hash_senha("senha2"), endereco="Rua 2")
      db_session.add_all([t1, t2])
      db_session.commit()
      db_session.refresh(t1)
      db_session.refresh(t2)

      b1 = Barbeiro(nome="Barbeiro T1", barbearia_id=t1.id)
      b2 = Barbeiro(nome="Barbeiro T2", barbearia_id=t2.id)
      s1 = Servico(nome="Corte T1", duracao_minutos=30, preco=40.0, barbearia_id=t1.id)
      db_session.add_all([b1, b2, s1])
      db_session.commit()
      db_session.refresh(b1)
      db_session.refresh(b2)
      db_session.refresh(s1)

      return {"t1": t1, "t2": t2, "b1": b1, "b2": b2, "s1": s1}


  def test_tenant_nao_ve_agenda_do_outro(client, dois_tenants, make_tenant_headers):
      t1 = dois_tenants["t1"]
      t2 = dois_tenants["t2"]

      headers_t1 = make_tenant_headers(tenant_id=t1.id)
      headers_t2_errado = {
          "Authorization": headers_t1["Authorization"],  # token de t1
          "X-Barbearia-Id": str(t2.id),  # mas tentando acessar t2
      }
      resp = client.get("/agenda/", headers=headers_t2_errado)
      assert resp.status_code == 403


  def test_tenant_nao_ve_clientes_do_outro(client, dois_tenants, make_tenant_headers):
      t1 = dois_tenants["t1"]
      t2 = dois_tenants["t2"]

      headers_t1_acessando_t2 = {
          "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
          "X-Barbearia-Id": str(t2.id),
      }
      resp = client.get("/clientes/", headers=headers_t1_acessando_t2)
      assert resp.status_code == 403


  def test_tenant_nao_ve_servicos_do_outro(client, dois_tenants, make_tenant_headers):
      t1 = dois_tenants["t1"]
      t2 = dois_tenants["t2"]

      headers_t1_acessando_t2 = {
          "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
          "X-Barbearia-Id": str(t2.id),
      }
      resp = client.get("/servicos/", headers=headers_t1_acessando_t2)
      assert resp.status_code == 403


  def test_tenant_nao_cria_agendamento_em_outro_tenant(client, dois_tenants, make_tenant_headers):
      t1 = dois_tenants["t1"]
      t2 = dois_tenants["t2"]

      headers_t1_acessando_t2 = {
          "Authorization": make_tenant_headers(tenant_id=t1.id)["Authorization"],
          "X-Barbearia-Id": str(t2.id),
      }
      payload = {
          "cliente_nome": "Intruso",
          "cliente_telefone": "5511999990000",
          "barbeiro_id": dois_tenants["b2"].id,
          "servico_id": dois_tenants["s1"].id,
          "data_hora_inicio": (datetime.now() + timedelta(days=1)).isoformat(),
      }
      resp = client.post("/agendamentos/", json=payload, headers=headers_t1_acessando_t2)
      assert resp.status_code == 403


  def test_endpoint_admin_bloqueia_tenant(client, make_tenant_headers, dois_tenants):
      t1 = dois_tenants["t1"]
      headers_tenant = make_tenant_headers(tenant_id=t1.id)
      # Tenants não devem acessar lista de barbearias (endpoint admin)
      resp = client.get("/barbearias/", headers=headers_tenant)
      assert resp.status_code == 403
  ```

- [ ] **Step 9.2: Rodar os testes de isolamento**

  ```bash
  cd backend && python -m pytest tests/test_tenant_isolation.py -v
  ```
  Esperado: todos PASS (se algum falhar, investigar o router correspondente e corrigir a lógica de tenant)

- [ ] **Step 9.3: Commit**

  ```bash
  git add backend/tests/test_tenant_isolation.py
  git commit -m "test(security): adicionar testes de isolamento de tenant"
  ```

---

## Task 10: Relatório da Fase 1

**Files:**
- Create: `docs/superpowers/reports/2026-03-23-fase-1-changelog.md`

- [ ] **Step 10.1: Gerar relatório**

  Criar `docs/superpowers/reports/2026-03-23-fase-1-changelog.md` com:
  ```markdown
  # Changelog — Fase 1: Segurança

  **Data:** [data do deploy]
  **Revisão Alembic:** N/A (projeto usa database.py _ensure_*)

  ## Dependências adicionadas
  - `passlib[bcrypt]==1.7.4`
  - `PyJWT==2.10.1`
  - `slowapi==0.1.9`

  ## Arquivos modificados
  - `backend/app/security.py` — bcrypt helpers, refactor JWT para PyJWT, jti
  - `backend/app/routes/auth.py` — verificar_senha no login, endpoint /auth/logout, rate limit
  - `backend/app/routes/barbearias.py` — hash_senha nos endpoints POST e PUT
  - `backend/app/routes/deps.py` — checagem de blacklist em get_current_claims
  - `backend/app/main.py` — configuração do slowapi Limiter
  - `backend/app/database.py` — _ensure_token_blacklist_table()

  ## Arquivos criados
  - `backend/app/models/token_blacklist.py`
  - `backend/scripts/migrate_senhas.py`
  - `backend/tests/test_security.py`
  - `backend/tests/test_rate_limit.py`
  - `backend/tests/test_tenant_isolation.py`

  ## Endpoints novos
  - `POST /auth/logout` — invalida token via blacklist

  ## Endpoints modificados
  - `POST /auth/login` — usa verificar_senha (bcrypt), rate limit 5/minute
  - `POST /barbearias/` — senha é hasheada antes de salvar
  - `PUT /barbearias/{id}` — senha é hasheada antes de salvar

  ## Variáveis de ambiente novas
  - `RATE_LIMIT_LOGIN` (default: `5/minute`)
  - `RATE_LIMIT_PUBLIC` (default: `30/minute`) — a implementar em public.py se necessário

  ## Instruções de deploy
  1. Criar snapshot Neon: `neonctl branch create --name pre-bcrypt-migration`
  2. Deploy do código (nova versão)
  3. Rodar script de migração: `python scripts/migrate_senhas.py`
  4. Verificar log: todos os registros migrados, Erros: 0
  5. Verificar configuração nginx (X-Real-IP e X-Forwarded-For)
  6. Reiniciar nginx: `sudo systemctl reload nginx`
  ```

- [ ] **Step 10.2: Commit**

  ```bash
  git add docs/superpowers/reports/2026-03-23-fase-1-changelog.md
  git commit -m "docs: relatório de mudanças da Fase 1 (segurança)"
  ```

---

## ═══════════════════════════════════════
## FASE 2: GENERALIZAÇÃO
## ═══════════════════════════════════════

> **ATENÇÃO:** A Fase 2 é um deploy independente. Confirmar que a Fase 1 está estável em produção antes de iniciar.

---

## Task 11: Migração de schema — rename de tabelas + tipo_servico

**Files:**
- Modify: `backend/app/database.py`

**Contexto:** Sem Alembic — a renomeação é feita via `_ensure_*` em `database.py`. PostgreSQL suporta `ALTER TABLE RENAME TO` e `ALTER TABLE RENAME COLUMN`. As funções são best-effort (falham silenciosamente se a coluna/tabela já foi renomeada).

- [ ] **Step 11.1: Adicionar função _ensure_rename_para_estabelecimentos**

  Em `backend/app/database.py`, adicionar:
  ```python
  def _ensure_rename_para_estabelecimentos():
      """Renomeia tabelas e colunas para a nomenclatura genérica."""
      _run_best_effort([
          # Renomear tabelas
          "ALTER TABLE barbearias RENAME TO estabelecimentos",
          "ALTER TABLE barbeiros RENAME TO profissionais",

          # Renomear colunas em agendamentos
          "ALTER TABLE agendamentos RENAME COLUMN barbearia_id TO estabelecimento_id",
          "ALTER TABLE agendamentos RENAME COLUMN barbeiro_id TO profissional_id",

          # Renomear colunas em profissionais (ex-barbeiros)
          # barbearia_id é apenas synonym ORM, não coluna física — a coluna real é barbershop_id
          "ALTER TABLE profissionais RENAME COLUMN barbershop_id TO estabelecimento_id",

          # Renomear colunas em clientes
          "ALTER TABLE clientes RENAME COLUMN barbearia_id TO estabelecimento_id",

          # Renomear colunas em servicos
          "ALTER TABLE servicos RENAME COLUMN barbearia_id TO estabelecimento_id",

          # Renomear colunas em conversas
          "ALTER TABLE conversas RENAME COLUMN tenant_id TO estabelecimento_id",

          # Renomear colunas em reminder_jobs
          "ALTER TABLE reminder_jobs RENAME COLUMN tenant_id TO estabelecimento_id",
      ])


  def _ensure_tipo_servico_column():
      """Adiciona coluna tipo_servico em estabelecimentos."""
      _run_best_effort([
          "ALTER TABLE estabelecimentos ADD COLUMN tipo_servico VARCHAR(50) NOT NULL DEFAULT 'barbearia'",
          "UPDATE estabelecimentos SET tipo_servico = 'barbearia' WHERE tipo_servico IS NULL",
      ])
  ```

  Em `init_db()`, adicionar as chamadas ao final:
  ```python
  _ensure_rename_para_estabelecimentos()
  _ensure_tipo_servico_column()
  ```

- [ ] **Step 11.2: Verificar com testes (os testes usam SQLite — os renomes falharão silenciosamente pois as tabelas são criadas do zero com os novos nomes após os models serem atualizados)**

  ```bash
  cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Esperado: nenhum teste quebrado (os `_ensure_*` falham silenciosamente no SQLite)

- [ ] **Step 11.3: Commit**

  ```bash
  git add backend/app/database.py
  git commit -m "feat(db): adicionar _ensure_rename_para_estabelecimentos e tipo_servico"
  ```

---

## Task 12: Renomear models — Barbearia→Estabelecimento, Barbeiro→Profissional

**Files:**
- Rename+Modify: `backend/app/models/barbearia.py` → `backend/app/models/estabelecimento.py`
- Rename+Modify: `backend/app/models/barbeiro.py` → `backend/app/models/profissional.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 12.1: Criar estabelecimento.py a partir de barbearia.py**

  Criar `backend/app/models/estabelecimento.py` com o conteúdo de `barbearia.py`, fazendo as seguintes mudanças:
  - Classe: `Barbearia` → `Estabelecimento`
  - `__tablename__ = "estabelecimentos"` (novo nome)
  - Adicionar coluna: `tipo_servico = Column(String(50), nullable=False, server_default="barbearia")`
  - Manter todos os outros campos

  ```python
  from datetime import datetime
  from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Integer, String
  from sqlalchemy.orm import relationship
  from app.database import Base


  class Estabelecimento(Base):
      __tablename__ = "estabelecimentos"

      id = Column(Integer, primary_key=True, index=True)
      nome = Column(String(255), nullable=False)
      slug = Column(String(120), nullable=True, unique=True, index=True)
      endereco = Column(String(255), nullable=True, default="")
      mega_instance_key = Column(String(255), nullable=True, unique=True, index=True)
      mega_token = Column(String(255), nullable=True)
      whatsapp_number = Column(String(30), nullable=True, unique=True, index=True)
      login = Column(String(255), nullable=True, unique=True)
      senha = Column(String(255), nullable=True)
      plano = Column(String(50), nullable=True, default="basico")
      status_manual = Column(String(50), nullable=True, default="ativo")
      vencimento_em = Column(Date, nullable=True)
      trial_ativo = Column(Boolean, nullable=False, default=False)
      trial_fim_em = Column(Date, nullable=True)
      ultimo_acesso_em = Column(DateTime, nullable=True)
      pagamento_recusado = Column(Boolean, nullable=False, default=False)
      horarios_funcionamento = Column(JSON, nullable=True)
      tipo_servico = Column(String(50), nullable=False, server_default="barbearia")
      criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)

      profissionais = relationship("Profissional", back_populates="estabelecimento")
  ```

- [ ] **Step 12.2: Criar profissional.py a partir de barbeiro.py**

  Criar `backend/app/models/profissional.py`:
  ```python
  from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
  from sqlalchemy.orm import relationship
  from app.database import Base


  class Profissional(Base):
      __tablename__ = "profissionais"

      id = Column(Integer, primary_key=True, index=True)
      nome = Column(String(255), nullable=False)
      estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False, index=True)
      ativo = Column(Boolean, nullable=False, default=True)
      tempo_por_servico = Column(JSON, nullable=True)
      horarios_funcionamento = Column(JSON, nullable=True)

      estabelecimento = relationship("Estabelecimento", back_populates="profissionais")
  ```

- [ ] **Step 12.3: Atualizar models/__init__.py**

  Manter imports antigos como aliases para compatibilidade durante a transição + adicionar novos:
  ```python
  from app.models.estabelecimento import Estabelecimento
  from app.models.profissional import Profissional
  # manter temporariamente para não quebrar imports em todo o código legado:
  Barbearia = Estabelecimento
  Barbeiro = Profissional

  from app.models.agendamento import Agendamento
  from app.models.cliente import Cliente
  from app.models.conversa import Conversa
  from app.models.reminder_job import ReminderJob
  from app.models.servico import Servico
  from app.models.webhook_event import WebhookEvent
  from app.models.token_blacklist import TokenBlacklist

  __all__ = [
      "Estabelecimento", "Profissional",
      "Barbearia", "Barbeiro",  # aliases de compatibilidade
      "Agendamento", "Cliente", "Conversa", "ReminderJob",
      "Servico", "WebhookEvent", "TokenBlacklist",
  ]
  ```

- [ ] **Step 12.4: Rodar testes**

  ```bash
  cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
  ```

- [ ] **Step 12.5: Atualizar agendamento.py, cliente.py e servico.py**

  Esses models têm ForeignKeys apontando para os nomes antigos de tabela. Atualizar:

  **`backend/app/models/agendamento.py`:**
  ```python
  # Substituir:
  estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)
  profissional_id = Column(Integer, ForeignKey("profissionais.id"), nullable=False)
  servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
  cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
  # Remover synonym tenant_id = synonym("barbearia_id"); adicionar:
  tenant_id = synonym("estabelecimento_id")
  barbearia_id = synonym("estabelecimento_id")  # alias de compatibilidade
  barbeiro_id = synonym("profissional_id")       # alias de compatibilidade
  # Atualizar Index:
  Index("ix_agendamentos_tenant_data_profissional", "estabelecimento_id", "data", "profissional_id")
  # Atualizar relationships:
  profissional = relationship("Profissional")
  estabelecimento = relationship("Estabelecimento")
  ```

  **`backend/app/models/cliente.py`:**
  ```python
  # Substituir:
  estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)
  barbearia_id = synonym("estabelecimento_id")  # alias de compatibilidade
  ```

  **`backend/app/models/servico.py`:**
  ```python
  # Substituir:
  estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True, index=True)
  tenant_id = synonym("estabelecimento_id")
  barbearia_id = synonym("estabelecimento_id")  # alias de compatibilidade
  ```

- [ ] **Step 12.6: Rodar testes**

  ```bash
  cd backend && python -m pytest tests/ -v --tb=short
  ```

- [ ] **Step 12.7: Commit**

  ```bash
  git add backend/app/models/estabelecimento.py backend/app/models/profissional.py \
          backend/app/models/agendamento.py backend/app/models/cliente.py \
          backend/app/models/servico.py backend/app/models/__init__.py
  git commit -m "feat(models): adicionar Estabelecimento e Profissional, atualizar FKs em agendamento/cliente/servico"
  ```

---

## Task 13: Renomear routers e atualizar imports

**Files:**
- Rename+Modify: `backend/app/routes/barbearias.py` → `estabelecimentos.py`
- Rename+Modify: `backend/app/routes/barbeiros.py` → `profissionais.py`
- Rename+Modify: `backend/app/routes/barbearia_funcionamento.py` → `estabelecimento_funcionamento.py`
- Rename+Modify: `backend/app/services/barbershop_hours_service.py` → `estabelecimento_hours_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 13.1: Criar estabelecimentos.py**

  Copiar conteúdo de `barbearias.py` para `estabelecimentos.py`, fazendo:
  - `from app.models.barbearia import Barbearia` → `from app.models.estabelecimento import Estabelecimento`
  - Usar `Estabelecimento` em vez de `Barbearia` em todo o arquivo
  - `from app.schemas.barbearia import BarbeariaAdminCreate, ...` → manter (schemas renomeados na Task 14)
  - `router = APIRouter(prefix="/estabelecimentos", ...)` — atualizar prefix

- [ ] **Step 13.2: Criar profissionais.py**

  Copiar conteúdo de `barbeiros.py` para `profissionais.py`:
  - `from app.models.barbeiro import Barbeiro` → `from app.models.profissional import Profissional`
  - `router = APIRouter(prefix="/profissionais", ...)`
  - Substituir `Barbeiro` por `Profissional`, `barbearia_id` por `estabelecimento_id`

- [ ] **Step 13.3: Criar estabelecimento_funcionamento.py**

  Copiar de `barbearia_funcionamento.py`, atualizando:
  - `router = APIRouter(prefix="/estabelecimentos/me/funcionamento", ...)`
  - `from app.models.estabelecimento import Estabelecimento`
  - Usar `Estabelecimento` em vez de `Barbearia`
  - `from app.services.estabelecimento_hours_service import normalize_working_hours`

- [ ] **Step 13.4: Criar estabelecimento_hours_service.py**

  Copiar de `barbershop_hours_service.py` — sem mudanças de lógica, só renomear o arquivo.

- [ ] **Step 13.5: Atualizar main.py**

  Adicionar imports dos novos routers e incluí-los na app, mantendo os antigos enquanto o frontend não foi atualizado (período de transição):
  ```python
  from app.routes import (
      # ... routers existentes ...
      estabelecimentos,
      profissionais,
      estabelecimento_funcionamento,
  )
  # Incluir novos routers
  app.include_router(estabelecimentos.router)
  app.include_router(profissionais.router)
  app.include_router(estabelecimento_funcionamento.router)
  # Manter antigos temporariamente (remover após frontend atualizado)
  app.include_router(barbearias.router)
  app.include_router(barbeiros.router)
  app.include_router(barbearia_funcionamento.router)
  ```

- [ ] **Step 13.6: Atualizar conftest.py para incluir novos routers nos testes**

  Em `backend/tests/conftest.py`, adicionar os novos routers ao fixture `app`.

- [ ] **Step 13.7: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v --tb=short
  ```
  Esperado: todos PASS

- [ ] **Step 13.8: Commit**

  ```bash
  git add backend/app/routes/estabelecimentos.py backend/app/routes/profissionais.py \
          backend/app/routes/estabelecimento_funcionamento.py \
          backend/app/services/estabelecimento_hours_service.py \
          backend/app/main.py backend/tests/conftest.py
  git commit -m "feat(routes): adicionar routers /estabelecimentos e /profissionais"
  ```

---

## Task 14: Atualizar schemas e deps.py

**Files:**
- Modify: `backend/app/schemas/barbearia.py`
- Modify: `backend/app/routes/deps.py`

- [ ] **Step 14.1: Adicionar aliases nos schemas**

  Em `backend/app/schemas/barbearia.py`, ao final do arquivo:
  ```python
  # Aliases de compatibilidade — usar os novos nomes em código novo
  EstabelecimentoAdminCreate = BarbeariaAdminCreate
  EstabelecimentoAdminUpdate = BarbeariaAdminUpdate
  EstabelecimentoAdminResponse = BarbeariaAdminResponse
  EstabelecimentoFuncionamentoDia = BarbeariaFuncionamentoDia
  EstabelecimentoFuncionamento = BarbeariaFuncionamento
  ```

- [ ] **Step 14.2: Adicionar get_current_estabelecimento em deps.py**

  Em `backend/app/routes/deps.py`:
  ```python
  from app.models.estabelecimento import Estabelecimento

  def get_current_estabelecimento(
      tenant_id: int = Depends(tenant_id_from_header),
      db: Session = Depends(get_db),
  ) -> Estabelecimento:
      est = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
      if not est:
          raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
      return est

  # Manter alias antigo
  get_current_barbearia = get_current_estabelecimento
  ```

- [ ] **Step 14.3: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```

- [ ] **Step 14.4: Commit**

  ```bash
  git add backend/app/schemas/barbearia.py backend/app/routes/deps.py
  git commit -m "feat(deps): adicionar get_current_estabelecimento e aliases de schema"
  ```

---

## Task 15: Endpoint GET /auth/me

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/tests/test_auth_barbearias.py`

**Contexto:** O frontend usa `GET /auth/me` para obter `tipo_servico` e outros dados do estabelecimento logado, sem precisar embutir no JWT.

- [ ] **Step 15.1: Adicionar schema MeResponse**

  Em `backend/app/schemas/auth.py`:
  ```python
  class MeResponse(BaseModel):
      id: int | None = None
      nome: str
      plano: str
      is_admin: bool
      tipo_servico: str | None = None  # None para admin
  ```

- [ ] **Step 15.2: Escrever teste**

  Adicionar em `backend/tests/test_auth_barbearias.py`:
  ```python
  def test_me_retorna_dados_do_tenant(client, db_session, make_tenant_headers):
      from app.security import hash_senha
      from app.models.barbearia import Barbearia
      b = Barbearia(
          nome="Tenant Me",
          login="tenant.me",
          senha=hash_senha("senha"),
          plano="premium",
          endereco="Rua Me",
      )
      db_session.add(b)
      db_session.commit()
      db_session.refresh(b)

      headers = make_tenant_headers(tenant_id=b.id)
      resp = client.get("/auth/me", headers=headers)
      assert resp.status_code == 200
      body = resp.json()
      assert body["nome"] == "Tenant Me"
      assert body["plano"] == "premium"
      assert body["is_admin"] is False
      assert "tipo_servico" in body


  def test_me_admin_retorna_dados_admin(client):
      import app.routes.auth as auth_module
      resp_login = client.post(
          "/auth/login",
          json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA},
      )
      token = resp_login.json()["access_token"]
      resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
      assert resp.status_code == 200
      body = resp.json()
      assert body["is_admin"] is True
      assert body["tipo_servico"] is None
  ```

- [ ] **Step 15.3: Rodar e confirmar falha**

  ```bash
  cd backend && python -m pytest tests/test_auth_barbearias.py::test_me_retorna_dados_do_tenant -v
  ```

- [ ] **Step 15.4: Implementar GET /auth/me**

  Em `backend/app/routes/auth.py`:
  ```python
  from app.schemas.auth import MeResponse
  from app.models.estabelecimento import Estabelecimento

  @router.get("/me", response_model=MeResponse)
  def me(
      claims: TokenClaims = Depends(get_current_claims),
      db: Session = Depends(get_db),
  ):
      if claims.is_admin:
          return MeResponse(nome="Administrador", plano="premium", is_admin=True)

      est = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
      if not est:
          raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")

      return MeResponse(
          id=est.id,
          nome=est.nome,
          plano=(est.plano or "basico").lower(),
          is_admin=False,
          tipo_servico=est.tipo_servico or "barbearia",
      )
  ```

- [ ] **Step 15.5: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```

- [ ] **Step 15.6: Commit**

  ```bash
  git add backend/app/routes/auth.py backend/app/schemas/auth.py backend/tests/test_auth_barbearias.py
  git commit -m "feat(auth): adicionar endpoint GET /auth/me com tipo_servico"
  ```

---

## Task 16: Frontend — vocab.ts + atualização de labels e chamadas de API

**Files:**
- Create: `frontend/lib/vocab.ts`
- Modify: `frontend/services/api.ts`
- Modify: `frontend/services/auth.ts`
- Modify: Componentes que exibem "Barbeiro"/"Barbearia" (verificar durante implementação)

- [ ] **Step 16.1: Criar frontend/lib/vocab.ts**

  Criar `frontend/lib/vocab.ts`:
  ```typescript
  export type TipoServico = "barbearia" | "salao_beleza" | "estetica_automotiva" | string;

  export type VocabEntry = {
    profissional: string;
    estabelecimento: string;
    profissionalPlural: string;
  };

  const vocabMap: Record<string, VocabEntry> = {
    barbearia: {
      profissional: "Barbeiro",
      estabelecimento: "Barbearia",
      profissionalPlural: "Barbeiros",
    },
    salao_beleza: {
      profissional: "Atendente",
      estabelecimento: "Salão",
      profissionalPlural: "Atendentes",
    },
    estetica_automotiva: {
      profissional: "Detailer",
      estabelecimento: "Estética",
      profissionalPlural: "Detailers",
    },
  };

  const defaultVocab: VocabEntry = vocabMap["barbearia"];

  export function getVocab(tipo: TipoServico | null | undefined): VocabEntry {
    if (!tipo) return defaultVocab;
    return vocabMap[tipo] ?? defaultVocab;
  }
  ```

- [ ] **Step 16.2: Adicionar chamada GET /auth/me no serviço de auth**

  Em `frontend/services/auth.ts`, adicionar função:
  ```typescript
  import { API_URL } from "./api";

  export type MeResponse = {
    id?: number;
    nome: string;
    plano: string;
    is_admin: boolean;
    tipo_servico?: string | null;
  };

  export async function fetchMe(accessToken: string): Promise<MeResponse | null> {
    try {
      const resp = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!resp.ok) return null;
      return resp.json();
    } catch {
      return null;
    }
  }
  ```

- [ ] **Step 16.3: Atualizar chamadas de API de /barbearias para /estabelecimentos**

  Em `frontend/services/api.ts`, localizar todas as ocorrências de `/barbearias` e `/barbeiros` e substituir por `/estabelecimentos` e `/profissionais`.

  **Importante:** Durante o período de transição em que ambos os routers existem no backend (Task 13, Step 13.5), qualquer um funciona. Após remover os routers antigos, apenas os novos endpoints funcionam.

- [ ] **Step 16.4: Atualizar barbershops-admin.ts → renomear para estabelecimentos-admin.ts**

  Criar `frontend/services/estabelecimentos-admin.ts` com o mesmo conteúdo de `barbershops-admin.ts`, atualizando:
  - URLs de `/barbearias` para `/estabelecimentos`
  - Tipos `BarbeariaAdmin` → `EstabelecimentoAdmin`
  - Exports correspondentes

- [ ] **Step 16.5: Verificar componentes com textos hardcoded**

  Buscar no frontend por strings como "Barbeiro", "Barbearia", "barbeiro" em componentes `.tsx`:
  ```bash
  grep -r "Barbeiro\|Barbearia\|barbeiro\|barbearia" frontend/app --include="*.tsx" -l
  ```
  Para cada arquivo encontrado, avaliar se o texto deve vir de `getVocab()` ou é irrelevante (ex: comments, metadata).

- [ ] **Step 16.6: Build do frontend para verificar erros TypeScript**

  ```bash
  cd frontend && npm run build
  ```
  Resolver quaisquer erros de TypeScript.

- [ ] **Step 16.7: Commit**

  ```bash
  git add frontend/lib/vocab.ts frontend/services/api.ts frontend/services/estabelecimentos-admin.ts \
          frontend/services/auth.ts
  git commit -m "feat(frontend): adicionar vocab.ts, /estabelecimentos endpoints, GET /auth/me"
  ```

---

## Task 17: Cleanup — remover routers antigos e aliases

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/conftest.py`

**Contexto:** Após confirmar que o frontend usa apenas os novos endpoints, remover os routers antigos.

- [ ] **Step 17.1: Remover routers antigos do main.py**

  Em `backend/app/main.py`, remover os includes de `barbearias.router`, `barbeiros.router`, `barbearia_funcionamento.router`.

- [ ] **Step 17.2: Remover aliases de compatibilidade do models/__init__.py**

  Remover `Barbearia = Estabelecimento` e `Barbeiro = Profissional`.

- [ ] **Step 17.3: Atualizar imports em todos os arquivos que ainda usam Barbearia/Barbeiro**

  Fazer busca global:
  ```bash
  grep -r "from app.models.barbearia import\|from app.models.barbeiro import\|import Barbearia\|import Barbeiro" backend/ --include="*.py"
  ```
  Atualizar cada ocorrência.

- [ ] **Step 17.4: Rodar todos os testes**

  ```bash
  cd backend && python -m pytest tests/ -v
  ```

- [ ] **Step 17.5: Commit**

  ```bash
  git add -A
  git commit -m "refactor: remover routers antigos e aliases de compatibilidade (cleanup fase 2)"
  ```

---

## Task 18: Relatório da Fase 2

**Files:**
- Create: `docs/superpowers/reports/2026-03-23-fase-2-changelog.md`

- [ ] **Step 18.1: Gerar relatório**

  Criar `docs/superpowers/reports/2026-03-23-fase-2-changelog.md`:
  ```markdown
  # Changelog — Fase 2: Generalização

  **Data:** [data do deploy]

  ## Tabelas/Colunas renomeadas no BD
  - `barbearias` → `estabelecimentos`
  - `barbeiros` → `profissionais`
  - `barbearia_id` → `estabelecimento_id` (em agendamentos, clientes, servicos, conversas, reminder_jobs)
  - `barbeiro_id` → `profissional_id` (em agendamentos)
  - `barbershop_id` → `estabelecimento_id` (em profissionais)

  ## Coluna nova
  - `estabelecimentos.tipo_servico VARCHAR(50) DEFAULT 'barbearia'`

  ## Arquivos criados
  - `backend/app/models/estabelecimento.py`
  - `backend/app/models/profissional.py`
  - `backend/app/routes/estabelecimentos.py`
  - `backend/app/routes/profissionais.py`
  - `backend/app/routes/estabelecimento_funcionamento.py`
  - `backend/app/services/estabelecimento_hours_service.py`
  - `frontend/lib/vocab.ts`
  - `frontend/services/estabelecimentos-admin.ts`

  ## Arquivos modificados
  - `backend/app/models/agendamento.py`, `cliente.py`, `servico.py` — FKs atualizadas
  - `backend/app/models/__init__.py` — novos exports
  - `backend/app/database.py` — _ensure_rename_*, _ensure_tipo_servico
  - `backend/app/routes/deps.py` — get_current_estabelecimento
  - `backend/app/routes/auth.py` — GET /auth/me
  - `backend/app/schemas/auth.py` — MeResponse
  - `backend/app/main.py` — novos routers incluídos, antigos removidos

  ## Endpoints novos
  - `GET /auth/me` — retorna dados do estabelecimento logado + tipo_servico
  - `GET/POST/PUT/DELETE /estabelecimentos/` — substitui /barbearias/
  - `GET/POST/PUT/DELETE /profissionais/` — substitui /barbeiros/
  - `GET/PUT /estabelecimentos/me/funcionamento` — substitui /barbearias/me/funcionamento

  ## Endpoints removidos (após cleanup Task 17)
  - `/barbearias/`, `/barbeiros/`, `/barbearias/me/funcionamento`

  ## Variáveis de ambiente novas
  - Nenhuma

  ## Instruções de deploy
  1. `git pull` no VPS
  2. Reiniciar serviço backend (init_db executa _ensure_rename automaticamente)
  3. Verificar logs de startup
  4. Deploy do frontend
  5. Confirmar que frontend funciona com novos endpoints
  6. Executar cleanup (Task 17) e redeploy
  ```

- [ ] **Step 18.2: Commit final**

  ```bash
  git add docs/superpowers/reports/2026-03-23-fase-2-changelog.md
  git commit -m "docs: relatório de mudanças da Fase 2 (generalização)"
  ```

---

## Instrução de Deploy

### Fase 1

1. `git pull` no VPS
2. `pip install -r requirements.txt` (novos: passlib, PyJWT, slowapi)
3. Reiniciar serviço backend
4. Criar snapshot Neon: `neonctl branch create --name pre-bcrypt-migration`
5. `python scripts/migrate_senhas.py --dry-run` (verificar log)
6. `python scripts/migrate_senhas.py` (migração real)
7. Verificar e atualizar config nginx (X-Real-IP/X-Forwarded-For)
8. `sudo systemctl reload nginx`

### Fase 2

1. `git pull` no VPS (deploy da Fase 2)
2. `pip install -r requirements.txt` (sem novidades)
3. Reiniciar serviço backend — o `init_db()` executa os `_ensure_rename_*` automaticamente
4. Verificar logs de startup (os `_ensure_*` devem reportar sucesso ou falha silenciosa)
5. Deploy do frontend atualizado
6. Remover routers antigos (Task 17) após confirmar que frontend usa novos endpoints
