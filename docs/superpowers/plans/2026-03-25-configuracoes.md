# Configurações — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/configuracoes` page for tenants to update their profile, change password, customize tenant theme (accent color, background, logo), and set notification preferences.

**Architecture:** Direct columns on `estabelecimentos` via `_ensure_configuracoes_columns()`. New `/configuracoes` FastAPI router (4 PATCH endpoints, tenant-only). `GET /auth/me` extended to return theme fields. Frontend sidebar layout with live theme preview and `useTenantTheme` hook applying CSS vars from session.

**Tech Stack:** FastAPI, SQLAlchemy, passlib[bcrypt], Pydantic v2, Next.js 14, Tailwind CSS, Lucide React, TypeScript

---

## File Map

### Backend — New files
- `backend/app/schemas/configuracoes.py` — Pydantic request bodies for the 4 PATCH endpoints
- `backend/app/routes/configuracoes.py` — router with `/configuracoes/perfil`, `/senha`, `/tema`, `/notificacoes`
- `backend/tests/test_configuracoes.py` — 13 tests covering all endpoints (TDD)

### Backend — Modified files
- `backend/app/database.py` — add `_ensure_configuracoes_columns()`, call in `init_db()`
- `backend/app/models/estabelecimento.py` — add 5 new columns
- `backend/app/schemas/auth.py` — extend `MeResponse` with tema + notif fields
- `backend/app/schemas/public.py` — add `accent_color`, `bg_color`, `logo_url` to `PublicBarbeariaLookupResponse`
- `backend/app/routes/auth.py` — update `me()` to return new fields
- `backend/app/services/public_booking_service.py` — include tema fields in lookup response
- `backend/app/main.py` — register `configuracoes` router
- `backend/tests/conftest.py` — include `configuracoes` router in test app

### Frontend — New files
- `frontend/app/configuracoes/page.tsx` — settings page with sidebar layout
- `frontend/hooks/useTenantTheme.ts` — hook that applies tenant CSS vars to document

### Frontend — Modified files
- `frontend/services/auth.ts` — extend `AuthSession` type, extend `MeResponse`, update `login()` to call `fetchMe` and persist theme
- `frontend/app/layout.tsx` — extend early injection script to apply tenant CSS vars
- `frontend/app/components/Header.tsx` — add "Configurações" nav item for tenants
- `frontend/middleware.ts` — protect `/configuracoes` route

---

## Task 1: DB migration + model columns

**Files:**
- Modify: `backend/app/database.py`
- Modify: `backend/app/models/estabelecimento.py`

- [ ] **Step 1.1: Read the files**

  Read `backend/app/database.py` (lines 40–90) and `backend/app/models/estabelecimento.py` completely before making changes.

- [ ] **Step 1.2: Add `_ensure_configuracoes_columns()` to database.py**

  Add this function anywhere in the file (before `init_db` is fine):

  ```python
  def _ensure_configuracoes_columns():
      """Adiciona colunas de configuração (tema, notificações) em estabelecimentos."""
      _run_best_effort([
          "ALTER TABLE estabelecimentos ADD COLUMN accent_color VARCHAR(7) NOT NULL DEFAULT '#d4930a'",
          "ALTER TABLE estabelecimentos ADD COLUMN bg_color VARCHAR(7) NOT NULL DEFAULT '#ffffff'",
          "ALTER TABLE estabelecimentos ADD COLUMN logo_url VARCHAR(500)",
          "ALTER TABLE estabelecimentos ADD COLUMN notif_ativo BOOLEAN NOT NULL DEFAULT TRUE",
          "ALTER TABLE estabelecimentos ADD COLUMN notif_horas_antes INTEGER NOT NULL DEFAULT 2",
      ])
  ```

  Then inside `init_db()`, append at the very end (after `_ensure_tipo_servico_column()`):
  ```python
  _ensure_configuracoes_columns()
  ```

- [ ] **Step 1.3: Add columns to the `Estabelecimento` SQLAlchemy model**

  In `backend/app/models/estabelecimento.py`, add the 5 columns to the `Estabelecimento` class (after `tipo_servico`):
  ```python
  accent_color = Column(String(7), nullable=False, server_default="#d4930a")
  bg_color = Column(String(7), nullable=False, server_default="#ffffff")
  logo_url = Column(String(500), nullable=True)
  notif_ativo = Column(Boolean, nullable=False, default=True)
  notif_horas_antes = Column(Integer, nullable=False, default=2)
  ```

  Import `Integer` from sqlalchemy if not already imported. `Boolean` and `String` should already be there.

- [ ] **Step 1.4: Run full tests**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ --tb=short -q 2>&1 | tail -10
  ```
  Expected: all 118 tests pass. The `_ensure_*` functions fail silently on SQLite.

- [ ] **Step 1.5: Commit**

  ```bash
  git add backend/app/database.py backend/app/models/estabelecimento.py
  git commit -m "feat(db): adicionar _ensure_configuracoes_columns e colunas no model Estabelecimento"
  ```

---

## Task 2: Schemas

**Files:**
- Create: `backend/app/schemas/configuracoes.py`
- Modify: `backend/app/schemas/auth.py`

- [ ] **Step 2.1: Create `backend/app/schemas/configuracoes.py`**

  ```python
  import re
  from pydantic import BaseModel, field_validator


  _HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


  class PerfilUpdate(BaseModel):
      nome: str | None = None
      endereco: str | None = None
      whatsapp_number: str | None = None
      slug: str | None = None


  class SenhaUpdate(BaseModel):
      senha_atual: str
      nova_senha: str

      @field_validator("nova_senha")
      @classmethod
      def nova_senha_minima(cls, v: str) -> str:
          if len(v) < 8:
              raise ValueError("A nova senha deve ter pelo menos 8 caracteres.")
          return v


  class TemaUpdate(BaseModel):
      accent_color: str | None = None
      bg_color: str | None = None
      logo_url: str | None = None

      @field_validator("accent_color", "bg_color")
      @classmethod
      def validar_hex(cls, v: str | None) -> str | None:
          if v is None:
              return v
          if not _HEX_COLOR_RE.match(v):
              raise ValueError("Cor deve estar no formato hexadecimal #rrggbb.")
          return v

      @field_validator("logo_url")
      @classmethod
      def validar_logo_url(cls, v: str | None) -> str | None:
          if v is None:
              return v
          if not v.startswith("https://"):
              raise ValueError("logo_url deve começar com https://")
          return v


  class NotificacoesUpdate(BaseModel):
      notif_ativo: bool | None = None
      notif_horas_antes: int | None = None

      @field_validator("notif_horas_antes")
      @classmethod
      def validar_horas(cls, v: int | None) -> int | None:
          if v is None:
              return v
          if v not in [1, 2, 4, 8, 24]:
              raise ValueError("notif_horas_antes deve ser um de: 1, 2, 4, 8, 24.")
          return v
  ```

- [ ] **Step 2.2: Extend `MeResponse` in `backend/app/schemas/auth.py`**

  Read the file first. Add the new fields to `MeResponse`:
  ```python
  class MeResponse(BaseModel):
      id: int | None = None
      nome: str
      plano: str
      is_admin: bool
      tipo_servico: str | None = None
      # Tema por tenant (admin retorna defaults)
      accent_color: str = "#d4930a"
      bg_color: str = "#ffffff"
      logo_url: str | None = None
      notif_ativo: bool = True
      notif_horas_antes: int = 2
  ```

- [ ] **Step 2.3: Run tests**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ --tb=short -q 2>&1 | tail -10
  ```
  Expected: 118 tests pass (schemas changes don't break existing tests).

- [ ] **Step 2.4: Commit**

  ```bash
  git add backend/app/schemas/configuracoes.py backend/app/schemas/auth.py
  git commit -m "feat(schemas): adicionar schemas de configurações e estender MeResponse"
  ```

---

## Task 3: Backend router `/configuracoes` (TDD)

**Files:**
- Create: `backend/tests/test_configuracoes.py`
- Create: `backend/app/routes/configuracoes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`

### Context
The `/configuracoes` router uses `get_current_claims` directly (not `tenant_id_from_header`), so no `X-Barbearia-Id` header is needed. In tests, use `make_tenant_headers(tenant_id=b.id, include_tenant_header=False)` to generate auth headers without the X-header.

- [ ] **Step 3.1: Write all failing tests in `backend/tests/test_configuracoes.py`**

  ```python
  import pytest
  from app.models.estabelecimento import Estabelecimento
  from app.security import hash_senha


  @pytest.fixture
  def tenant_com_senha(db_session):
      est = Estabelecimento(
          nome="Config Teste",
          login="config.teste",
          senha=hash_senha("senha123"),
          slug="config-teste",
          endereco="Rua A",
          plano="basico",
      )
      db_session.add(est)
      db_session.commit()
      db_session.refresh(est)
      return est


  @pytest.fixture
  def headers_tenant(tenant_com_senha, make_tenant_headers):
      return make_tenant_headers(
          tenant_id=tenant_com_senha.id,
          include_tenant_header=False,
      )


  def test_configuracoes_requer_autenticacao(client):
      resp = client.patch("/configuracoes/perfil", json={"nome": "Novo"})
      assert resp.status_code == 401


  def test_admin_nao_acessa_configuracoes(client, make_tenant_headers):
      headers = make_tenant_headers(is_admin=True)
      resp = client.patch("/configuracoes/perfil", json={"nome": "Novo"}, headers=headers)
      assert resp.status_code == 403


  def test_atualizar_perfil_sucesso(client, db_session, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/perfil",
          json={"nome": "Novo Nome", "endereco": "Rua B"},
          headers=headers_tenant,
      )
      assert resp.status_code == 200
      db_session.refresh(tenant_com_senha)
      assert tenant_com_senha.nome == "Novo Nome"
      assert tenant_com_senha.endereco == "Rua B"


  def test_atualizar_perfil_slug_duplicado(client, db_session, tenant_com_senha, headers_tenant):
      # Criar outro estabelecimento com slug existente
      outro = Estabelecimento(nome="Outro", slug="slug-existente")
      db_session.add(outro)
      db_session.commit()

      resp = client.patch(
          "/configuracoes/perfil",
          json={"slug": "slug-existente"},
          headers=headers_tenant,
      )
      assert resp.status_code == 409


  def test_trocar_senha_correto(client, db_session, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/senha",
          json={"senha_atual": "senha123", "nova_senha": "novaSenha456"},
          headers=headers_tenant,
      )
      assert resp.status_code == 200
      db_session.refresh(tenant_com_senha)
      from app.security import verificar_senha
      assert verificar_senha("novaSenha456", tenant_com_senha.senha)


  def test_trocar_senha_atual_errada(client, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/senha",
          json={"senha_atual": "errada", "nova_senha": "novaSenha456"},
          headers=headers_tenant,
      )
      assert resp.status_code == 400


  def test_trocar_senha_muito_curta(client, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/senha",
          json={"senha_atual": "senha123", "nova_senha": "curta"},
          headers=headers_tenant,
      )
      assert resp.status_code == 422


  def test_atualizar_tema_sucesso(client, db_session, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/tema",
          json={"accent_color": "#ff0000", "bg_color": "#000000", "logo_url": "https://example.com/logo.png"},
          headers=headers_tenant,
      )
      assert resp.status_code == 200
      db_session.refresh(tenant_com_senha)
      assert tenant_com_senha.accent_color == "#ff0000"
      assert tenant_com_senha.bg_color == "#000000"
      assert tenant_com_senha.logo_url == "https://example.com/logo.png"


  def test_atualizar_tema_cor_invalida(client, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/tema",
          json={"accent_color": "vermelho"},
          headers=headers_tenant,
      )
      assert resp.status_code == 422


  def test_atualizar_tema_logo_url_invalida(client, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/tema",
          json={"logo_url": "http://insecure.com/logo.png"},
          headers=headers_tenant,
      )
      assert resp.status_code == 422


  def test_atualizar_notificacoes_sucesso(client, db_session, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/notificacoes",
          json={"notif_ativo": False, "notif_horas_antes": 24},
          headers=headers_tenant,
      )
      assert resp.status_code == 200
      db_session.refresh(tenant_com_senha)
      assert tenant_com_senha.notif_ativo is False
      assert tenant_com_senha.notif_horas_antes == 24


  def test_atualizar_notificacoes_horas_invalidas(client, tenant_com_senha, headers_tenant):
      resp = client.patch(
          "/configuracoes/notificacoes",
          json={"notif_horas_antes": 3},
          headers=headers_tenant,
      )
      assert resp.status_code == 422


  def test_me_retorna_campos_de_tema(client, db_session, tenant_com_senha, headers_tenant):
      tenant_com_senha.accent_color = "#aabbcc"
      db_session.commit()

      resp = client.get("/auth/me", headers=headers_tenant)
      assert resp.status_code == 200
      body = resp.json()
      assert body["accent_color"] == "#aabbcc"
      assert "bg_color" in body
      assert "notif_ativo" in body
      assert "notif_horas_antes" in body
  ```

- [ ] **Step 3.2: Run tests to confirm they ALL fail (router doesn't exist yet)**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/test_configuracoes.py -v --tb=short 2>&1 | tail -20
  ```
  Expected: all fail with 404 or import errors — that's correct (RED phase).

- [ ] **Step 3.3: Create `backend/app/routes/configuracoes.py`**

  ```python
  from fastapi import APIRouter, Depends, HTTPException
  from sqlalchemy.orm import Session

  from app.database import get_db
  from app.models.estabelecimento import Estabelecimento
  from app.routes.deps import get_current_claims
  from app.schemas.configuracoes import NotificacoesUpdate, PerfilUpdate, SenhaUpdate, TemaUpdate
  from app.security import TokenClaims, hash_senha, verificar_senha

  router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])


  def _get_tenant_estabelecimento(
      claims: TokenClaims = Depends(get_current_claims),
      db: Session = Depends(get_db),
  ) -> tuple[TokenClaims, Estabelecimento]:
      if claims.is_admin:
          raise HTTPException(status_code=403, detail="Endpoint exclusivo para tenants.")
      est = db.query(Estabelecimento).filter(Estabelecimento.id == claims.tenant_id).first()
      if not est:
          raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
      return claims, est


  @router.patch("/perfil")
  def atualizar_perfil(
      dados: PerfilUpdate,
      pair: tuple = Depends(_get_tenant_estabelecimento),
      db: Session = Depends(get_db),
  ):
      _, est = pair
      if dados.slug is not None and dados.slug != est.slug:
          existente = db.query(Estabelecimento).filter(
              Estabelecimento.slug == dados.slug,
              Estabelecimento.id != est.id,
          ).first()
          if existente:
              raise HTTPException(status_code=409, detail="Slug já está em uso.")
          est.slug = dados.slug
      if dados.nome is not None:
          est.nome = dados.nome
      if dados.endereco is not None:
          est.endereco = dados.endereco
      if dados.whatsapp_number is not None:
          est.whatsapp_number = dados.whatsapp_number
      db.commit()
      return {"detail": "Perfil atualizado."}


  @router.patch("/senha")
  def trocar_senha(
      dados: SenhaUpdate,
      pair: tuple = Depends(_get_tenant_estabelecimento),
      db: Session = Depends(get_db),
  ):
      _, est = pair
      if not est.senha or not verificar_senha(dados.senha_atual, est.senha):
          raise HTTPException(status_code=400, detail="Senha atual incorreta.")
      est.senha = hash_senha(dados.nova_senha)
      db.commit()
      return {"detail": "Senha alterada com sucesso."}


  @router.patch("/tema")
  def atualizar_tema(
      dados: TemaUpdate,
      pair: tuple = Depends(_get_tenant_estabelecimento),
      db: Session = Depends(get_db),
  ):
      _, est = pair
      if dados.accent_color is not None:
          est.accent_color = dados.accent_color
      if dados.bg_color is not None:
          est.bg_color = dados.bg_color
      if dados.logo_url is not None:
          est.logo_url = dados.logo_url
      db.commit()
      return {"detail": "Tema atualizado."}


  @router.patch("/notificacoes")
  def atualizar_notificacoes(
      dados: NotificacoesUpdate,
      pair: tuple = Depends(_get_tenant_estabelecimento),
      db: Session = Depends(get_db),
  ):
      _, est = pair
      if dados.notif_ativo is not None:
          est.notif_ativo = dados.notif_ativo
      if dados.notif_horas_antes is not None:
          est.notif_horas_antes = dados.notif_horas_antes
      db.commit()
      return {"detail": "Preferências de notificação atualizadas."}
  ```

- [ ] **Step 3.4: Register router in `backend/app/main.py`**

  Read `main.py` first. Add `configuracoes` to the imports block and the include_router call:
  ```python
  # In imports:
  from app.routes import (
      ...,
      configuracoes,
  )
  # After other include_router calls:
  app.include_router(configuracoes.router)
  ```

- [ ] **Step 3.5: Register router in `backend/tests/conftest.py`**

  Read `conftest.py` first. Add `configuracoes` to the imports and to `test_app`:
  ```python
  from app.routes import ..., configuracoes
  # In app fixture:
  test_app.include_router(configuracoes.router)
  ```

- [ ] **Step 3.6: Run all tests**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ --tb=short -q 2>&1 | tail -15
  ```
  Expected: 131 tests pass (118 existing + 13 new). Fix any failures.

  **If `test_me_retorna_campos_de_tema` fails:** it depends on Task 4 (extending `GET /auth/me`). That's expected — skip it for now, implement it in Task 4.

- [ ] **Step 3.7: Commit**

  ```bash
  git add backend/app/routes/configuracoes.py backend/app/schemas/configuracoes.py \
          backend/tests/test_configuracoes.py backend/app/main.py backend/tests/conftest.py
  git commit -m "feat(backend): router /configuracoes com 4 endpoints PATCH (TDD)"
  ```

---

## Task 4: Extend `GET /auth/me`

**Files:**
- Modify: `backend/app/routes/auth.py`

- [ ] **Step 4.1: Update `me()` in `backend/app/routes/auth.py`**

  Read the file first. Find the `me()` function and update the return statement for the tenant path to include the new fields:
  ```python
  return MeResponse(
      id=est.id,
      nome=est.nome,
      plano=(est.plano or "basico").lower(),
      is_admin=False,
      tipo_servico=getattr(est, "tipo_servico", "barbearia") or "barbearia",
      accent_color=getattr(est, "accent_color", None) or "#d4930a",
      bg_color=getattr(est, "bg_color", None) or "#ffffff",
      logo_url=getattr(est, "logo_url", None),
      notif_ativo=getattr(est, "notif_ativo", True),
      notif_horas_antes=getattr(est, "notif_horas_antes", 2),
  )
  ```
  The admin path (`return MeResponse(nome="Administrador", ...)`) does NOT need to change — `MeResponse` Pydantic defaults cover it.

- [ ] **Step 4.2: Run full tests**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ --tb=short -q 2>&1 | tail -10
  ```
  Expected: 131 tests pass including `test_me_retorna_campos_de_tema`.

- [ ] **Step 4.3: Commit**

  ```bash
  git add backend/app/routes/auth.py
  git commit -m "feat(auth): GET /auth/me retorna campos de tema e notificações"
  ```

---

## Task 5: Extend public endpoint with tema fields

**Files:**
- Modify: `backend/app/schemas/public.py`
- Modify: `backend/app/services/public_booking_service.py`

- [ ] **Step 5.1: Read both files completely**

  Read `backend/app/schemas/public.py` and `backend/app/services/public_booking_service.py`.

- [ ] **Step 5.2: Add tema fields to `PublicBarbeariaLookupResponse`**

  In `backend/app/schemas/public.py`, add the 3 new optional fields to `PublicBarbeariaLookupResponse`:
  ```python
  class PublicBarbeariaLookupResponse(BaseModel):
      barbearia_id: int
      nome: str
      slug: str
      barbeiros: list[PublicBarbeiroItem]
      servicos: list[PublicServicoItem]
      horarios_disponiveis: list[str]
      horarios_grade: list[PublicHorarioItem] = []
      # Tema por tenant
      accent_color: str = "#d4930a"
      bg_color: str = "#ffffff"
      logo_url: str | None = None
  ```

- [ ] **Step 5.3: Include tema fields in `obter_lookup_publico_por_id`**

  In `public_booking_service.py`, find `obter_lookup_publico_por_id`. The function returns a dict — find where it builds the return dict and add the tema fields:
  ```python
  return {
      "barbearia_id": barbearia.id,
      "nome": barbearia.nome,
      "slug": barbearia.slug or "",
      "barbeiros": barbeiros,
      "servicos": servicos,
      "horarios_disponiveis": horarios_disponiveis,
      "horarios_grade": horarios_grade,
      "accent_color": getattr(barbearia, "accent_color", None) or "#d4930a",
      "bg_color": getattr(barbearia, "bg_color", None) or "#ffffff",
      "logo_url": getattr(barbearia, "logo_url", None),
  }
  ```
  (Use `getattr` with default in case the column doesn't exist in an old DB.)

- [ ] **Step 5.4: Run full tests**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ --tb=short -q 2>&1 | tail -10
  ```
  Expected: 131 tests pass.

- [ ] **Step 5.5: Commit**

  ```bash
  git add backend/app/schemas/public.py backend/app/services/public_booking_service.py
  git commit -m "feat(public): endpoint /public/barbearia/{slug} retorna campos de tema"
  ```

---

## Task 6: Frontend — AuthSession + useTenantTheme + login flow

**Files:**
- Modify: `frontend/services/auth.ts`
- Create: `frontend/hooks/useTenantTheme.ts`
- Modify: `frontend/app/layout.tsx`

### Context
`AuthSession` currently stores: `email`, `tenantId`, `tenantName`, `plan`, `accessToken`. We need to add optional tema fields. `MeResponse` in auth.ts already has the base shape (from Phase 2) — we need to extend it with the new fields.

- [ ] **Step 6.1: Read `frontend/services/auth.ts` and `frontend/app/login/page.tsx` completely**

  Understand the full login flow before making changes.

- [ ] **Step 6.2: Extend `AuthSession` type and `MeResponse` in `frontend/services/auth.ts`**

  Update the types:
  ```typescript
  export type MeResponse = {
    id?: number;
    nome: string;
    plano: string;
    is_admin: boolean;
    tipo_servico?: string | null;
    accent_color?: string;
    bg_color?: string;
    logo_url?: string | null;
    notif_ativo?: boolean;
    notif_horas_antes?: number;
  };

  export type AuthSession = {
    email: string;
    tenantId: string;
    tenantName: string;
    plan: "basico" | "premium";
    accessToken: string;
    // Tema por tenant (opcionais — ausentes para admin)
    accentColor?: string;
    bgColor?: string;
    logoUrl?: string | null;
  };
  ```

  **IMPORTANT — also update `getAuthSession()`:** The function explicitly reconstructs the session object from only 5 known fields. Without updating it, `accentColor`/`bgColor`/`logoUrl` stored in localStorage via `login()` will be discarded on every re-read. Find the `cachedParsedSession = { ... }` block and add the new fields:
  ```typescript
  cachedParsedSession = {
    email: parsed.email,
    tenantId: parsed.tenantId,
    tenantName: parsed.tenantName,
    plan,
    accessToken: parsed.accessToken,
    accentColor: parsed.accentColor,
    bgColor: parsed.bgColor,
    logoUrl: parsed.logoUrl ?? null,
  };
  ```

- [ ] **Step 6.3: Update `login()` caller in `frontend/app/login/page.tsx`**

  Read `frontend/app/login/page.tsx`. After a successful tenant login, call `fetchMe` to get the theme and include it in the session:
  ```typescript
  // After getting resposta from loginUsuario():
  const me = await fetchMe(resposta.access_token);
  login({
    email: usuario,
    tenantId: String(resposta.tenant_id),
    tenantName: resposta.tenant_name ?? "",
    plan: resposta.plano === "premium" ? "premium" : "basico",
    accessToken: resposta.access_token,
    accentColor: me?.accent_color,
    bgColor: me?.bg_color,
    logoUrl: me?.logo_url,
  });
  ```

  **Note:** `fetchMe` is imported from `@/services/auth`. `loginUsuario` is already imported — check the exact import in the login page.

- [ ] **Step 6.4: Create `frontend/hooks/useTenantTheme.ts`**

  Create directory `frontend/hooks/` if it doesn't exist. Then create the file:
  ```typescript
  "use client";

  import { useEffect } from "react";
  import { useAuthSession } from "@/services/auth";

  const DEFAULT_ACCENT = "#d4930a";
  const DEFAULT_BG = "#ffffff";

  export function useTenantTheme() {
    const session = useAuthSession();

    useEffect(() => {
      const accent = session?.accentColor || DEFAULT_ACCENT;
      const bg = session?.bgColor || DEFAULT_BG;

      document.documentElement.style.setProperty("--accent", accent);
      document.documentElement.style.setProperty("--accent-tenant", accent);
      document.documentElement.style.setProperty("--bg-tenant", bg);
    }, [session?.accentColor, session?.bgColor]);
  }
  ```

- [ ] **Step 6.5: Use `useTenantTheme` in `frontend/app/components/AppShell.tsx`**

  Read `AppShell.tsx`. Add the hook call:
  ```typescript
  import { useTenantTheme } from "@/hooks/useTenantTheme";
  // Inside the component:
  useTenantTheme();
  ```

- [ ] **Step 6.6: Extend early injection script in `frontend/app/layout.tsx`**

  Read `layout.tsx`. The `themeScript` constant already runs before React hydrates. Extend it to also apply tenant CSS vars from the session:
  ```javascript
  const themeScript = `
    (function () {
      try {
        var savedTheme = localStorage.getItem("virtualbarber:theme") || "system";
        var systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        var resolvedTheme = savedTheme === "system" ? systemTheme : savedTheme;
        document.documentElement.dataset.theme = resolvedTheme;
        document.documentElement.style.colorScheme = resolvedTheme;
      } catch (error) {
        document.documentElement.dataset.theme = "light";
        document.documentElement.style.colorScheme = "light";
      }
      try {
        var raw = localStorage.getItem("barbershop_auth_session");
        if (raw) {
          var s = JSON.parse(raw);
          if (s.accentColor) document.documentElement.style.setProperty("--accent", s.accentColor);
          if (s.bgColor) document.documentElement.style.setProperty("--bg-tenant", s.bgColor);
        }
      } catch (e) {}
    })();
  `;
  ```

- [ ] **Step 6.7: Run TypeScript build to check for errors**

  ```bash
  cd /path/to/project/frontend && npm run build 2>&1 | tail -20
  ```
  Fix any TypeScript errors. Most likely: missing imports, wrong field names.

- [ ] **Step 6.8: Commit**

  ```bash
  git add frontend/services/auth.ts frontend/hooks/useTenantTheme.ts \
          frontend/app/layout.tsx frontend/app/components/AppShell.tsx \
          frontend/app/login/page.tsx
  git commit -m "feat(frontend): AuthSession com tema, useTenantTheme hook, early injection"
  ```

---

## Task 7: Frontend — Header nav + middleware protection

**Files:**
- Modify: `frontend/app/components/Header.tsx`
- Modify: `frontend/middleware.ts`

- [ ] **Step 7.1: Add "Configurações" to nav in `Header.tsx`**

  Read `Header.tsx`. The `navItems` array is built conditionally. Add the "Configurações" item for tenants (not admin):
  ```typescript
  import { BarChart2, CalendarDays, LayoutDashboard, Scissors, Settings, Settings2, Shield, LogOut } from "lucide-react";
  // ...
  const navItems = [
    { href: "/", label: "Painel", icon: LayoutDashboard },
    { href: "/agenda", label: "Agenda", icon: CalendarDays },
    { href: "/gestao", label: "Gestao", icon: Settings2 },
    ...(!isAdmin && session?.plan === "premium" ? [{ href: "/dashboard", label: "Dashboard", icon: BarChart2 }] : []),
    ...(!isAdmin ? [{ href: "/configuracoes", label: "Config.", icon: Settings }] : []),
    ...(isAdmin && !inAdminPage ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
  ];
  ```
  (`Settings` icon from lucide-react — if already imported with a different name, use the existing import.)

- [ ] **Step 7.2: Update `frontend/middleware.ts`**

  Read the file. Add `/configuracoes` to both `isProtectedPath` and `config.matcher`:
  ```typescript
  const isProtectedPath =
    pathname === "/" ||
    pathname === "/agenda" ||
    pathname.startsWith("/agenda/") ||
    pathname === "/gestao" ||
    pathname.startsWith("/gestao/") ||
    pathname === "/configuracoes" ||
    pathname.startsWith("/configuracoes/") ||
    pathname.startsWith("/admin");

  export const config = {
    matcher: ["/", "/agenda/:path*", "/gestao/:path*", "/configuracoes/:path*", "/admin/:path*"],
  };
  ```

- [ ] **Step 7.3: Run TypeScript build**

  ```bash
  cd /path/to/project/frontend && npm run build 2>&1 | tail -15
  ```

- [ ] **Step 7.4: Commit**

  ```bash
  git add frontend/app/components/Header.tsx frontend/middleware.ts
  git commit -m "feat(frontend): adicionar Configurações ao nav e proteger rota no middleware"
  ```

---

## Task 8: Frontend — `/configuracoes` page

**Files:**
- Create: `frontend/app/configuracoes/page.tsx`

### Context
- Page uses `"use client"` directive
- Auth: `useAuthSession()` — if `session.tenantId === "admin"` redirect to `/admin`; if no session, middleware already redirects to `/login`
- Layout: sidebar (left) + content (right), controlled by `activeSection` state
- 4 sections: `"perfil"`, `"senha"`, `"tema"`, `"notificacoes"`
- API calls: `PATCH ${API_URL}/configuracoes/{section}` with Bearer token
- Theme preview: change `document.documentElement.style.setProperty` on `<input type="color">` change, revert on cancel
- `API_URL` is imported from `@/services/api`

- [ ] **Step 8.1: Read `frontend/services/api.ts` to find `API_URL` export**

  ```bash
  grep "export.*API_URL\|const API_URL" /path/to/project/frontend/services/api.ts
  ```

- [ ] **Step 8.2: Create `frontend/app/configuracoes/page.tsx`**

  ```typescript
  "use client";

  import { useState } from "react";
  import { useRouter } from "next/navigation";
  import { Settings, User, Lock, Palette, Bell } from "lucide-react";
  import { useAuthSession, AUTH_STORAGE_KEY } from "@/services/auth";
  import { API_URL } from "@/services/api";

  type Section = "perfil" | "senha" | "tema" | "notificacoes";

  const SECTIONS: { id: Section; label: string; icon: React.ElementType }[] = [
    { id: "perfil", label: "Perfil", icon: User },
    { id: "senha", label: "Senha", icon: Lock },
    { id: "tema", label: "Tema", icon: Palette },
    { id: "notificacoes", label: "Notificações", icon: Bell },
  ];

  async function patchConfiguracao(
    section: string,
    body: Record<string, unknown>,
    token: string,
  ): Promise<{ ok: boolean; detail?: string }> {
    try {
      const resp = await fetch(`${API_URL}/configuracoes/${section}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      return { ok: resp.ok, detail: data.detail };
    } catch {
      return { ok: false, detail: "Erro de conexão." };
    }
  }

  export default function ConfiguracoesPage() {
    const session = useAuthSession();
    const router = useRouter();
    const [activeSection, setActiveSection] = useState<Section>("perfil");
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Redirect admin
    if (session?.tenantId === "admin") {
      router.replace("/admin");
      return null;
    }

    // Perfil state
    const [nome, setNome] = useState(session?.tenantName ?? "");
    const [endereco, setEndereco] = useState("");
    const [whatsapp, setWhatsapp] = useState("");
    const [slug, setSlug] = useState("");

    // Senha state
    const [senhaAtual, setSenhaAtual] = useState("");
    const [novaSenha, setNovaSenha] = useState("");
    const [confirmarSenha, setConfirmarSenha] = useState("");

    // Tema state
    const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#d4930a");
    const [bgColor, setBgColor] = useState(session?.bgColor ?? "#ffffff");
    const [logoUrl, setLogoUrl] = useState(session?.logoUrl ?? "");

    // Notificações state
    const [notifAtivo, setNotifAtivo] = useState(true);
    const [notifHoras, setNotifHoras] = useState<number>(2);

    function clearMessages() {
      setSuccess(null);
      setError(null);
    }

    async function handleSalvarPerfil(e: React.FormEvent) {
      e.preventDefault();
      clearMessages();
      setLoading(true);
      const result = await patchConfiguracao(
        "perfil",
        { nome: nome || undefined, endereco: endereco || undefined, whatsapp_number: whatsapp || undefined, slug: slug || undefined },
        session!.accessToken,
      );
      setLoading(false);
      if (result.ok) setSuccess("Perfil atualizado com sucesso!");
      else setError(result.detail ?? "Erro ao atualizar perfil.");
    }

    async function handleSalvarSenha(e: React.FormEvent) {
      e.preventDefault();
      clearMessages();
      if (novaSenha !== confirmarSenha) {
        setError("Nova senha e confirmação não coincidem.");
        return;
      }
      if (novaSenha.length < 8) {
        setError("A nova senha deve ter pelo menos 8 caracteres.");
        return;
      }
      setLoading(true);
      const result = await patchConfiguracao(
        "senha",
        { senha_atual: senhaAtual, nova_senha: novaSenha },
        session!.accessToken,
      );
      setLoading(false);
      if (result.ok) {
        setSuccess("Senha alterada com sucesso!");
        setSenhaAtual("");
        setNovaSenha("");
        setConfirmarSenha("");
      } else {
        setError(result.detail ?? "Erro ao alterar senha.");
      }
    }

    async function handleSalvarTema(e: React.FormEvent) {
      e.preventDefault();
      clearMessages();
      setLoading(true);
      const result = await patchConfiguracao(
        "tema",
        {
          accent_color: accentColor,
          bg_color: bgColor,
          logo_url: logoUrl || null,
        },
        session!.accessToken,
      );
      setLoading(false);
      if (result.ok) {
        // Persist updated theme in localStorage
        if (typeof window !== "undefined") {
          const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
          if (raw) {
            try {
              const s = JSON.parse(raw);
              s.accentColor = accentColor;
              s.bgColor = bgColor;
              s.logoUrl = logoUrl || null;
              window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(s));
            } catch {}
          }
        }
        setSuccess("Tema atualizado com sucesso!");
      } else {
        setError(result.detail ?? "Erro ao atualizar tema.");
      }
    }

    async function handleSalvarNotificacoes(e: React.FormEvent) {
      e.preventDefault();
      clearMessages();
      setLoading(true);
      const result = await patchConfiguracao(
        "notificacoes",
        { notif_ativo: notifAtivo, notif_horas_antes: notifHoras },
        session!.accessToken,
      );
      setLoading(false);
      if (result.ok) setSuccess("Preferências salvas!");
      else setError(result.detail ?? "Erro ao salvar preferências.");
    }

    return (
      <main className="app-container" style={{ paddingTop: "2rem", paddingBottom: "3rem" }}>
        <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
          {/* Sidebar */}
          <aside
            style={{
              width: "200px",
              flexShrink: 0,
              background: "var(--surface)",
              borderRadius: "8px",
              padding: "1rem",
              border: "1px solid var(--line)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", fontWeight: 700 }}>
              <Settings size={16} />
              <span>Configurações</span>
            </div>
            <nav style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              {SECTIONS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => { setActiveSection(id); clearMessages(); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "6px",
                    border: "none",
                    cursor: "pointer",
                    textAlign: "left",
                    background: activeSection === id ? "var(--accent)" : "transparent",
                    color: activeSection === id ? "#fff" : "var(--ink)",
                    fontWeight: activeSection === id ? 600 : 400,
                  }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              ))}
            </nav>
          </aside>

          {/* Content */}
          <div style={{ flex: 1, maxWidth: "600px" }}>
            {success && (
              <div style={{ background: "var(--success)", color: "#fff", padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem" }}>
                {success}
              </div>
            )}
            {error && (
              <div style={{ background: "var(--danger)", color: "#fff", padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem" }}>
                {error}
              </div>
            )}

            {activeSection === "perfil" && (
              <form onSubmit={handleSalvarPerfil}>
                <h2 style={{ marginBottom: "1.5rem" }}>Perfil do Estabelecimento</h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Nome</span>
                    <input className="mock-input" value={nome} onChange={e => setNome(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Endereço</span>
                    <input className="mock-input" value={endereco} onChange={e => setEndereco(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>WhatsApp</span>
                    <input className="mock-input" value={whatsapp} onChange={e => setWhatsapp(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Slug (URL pública)</span>
                    <input className="mock-input" value={slug} onChange={e => setSlug(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <button type="submit" className="mock-button" disabled={loading}>
                    {loading ? "Salvando..." : "Salvar perfil"}
                  </button>
                </div>
              </form>
            )}

            {activeSection === "senha" && (
              <form onSubmit={handleSalvarSenha}>
                <h2 style={{ marginBottom: "1.5rem" }}>Trocar Senha</h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Senha atual</span>
                    <input type="password" className="mock-input" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Nova senha</span>
                    <input type="password" className="mock-input" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Confirmar nova senha</span>
                    <input type="password" className="mock-input" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} style={{ width: "100%" }} />
                  </label>
                  <button type="submit" className="mock-button" disabled={loading}>
                    {loading ? "Salvando..." : "Alterar senha"}
                  </button>
                </div>
              </form>
            )}

            {activeSection === "tema" && (
              <form onSubmit={handleSalvarTema}>
                <h2 style={{ marginBottom: "1.5rem" }}>Tema do Estabelecimento</h2>
                <p style={{ fontSize: "0.875rem", color: "var(--ink-2)", marginBottom: "1.5rem" }}>
                  Personaliza a cor de destaque e o fundo tanto no painel quanto na página pública de agendamento.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <input
                      type="color"
                      value={accentColor}
                      onChange={e => {
                        setAccentColor(e.target.value);
                        document.documentElement.style.setProperty("--accent", e.target.value);
                      }}
                      style={{ width: "48px", height: "48px", border: "none", borderRadius: "4px", cursor: "pointer" }}
                    />
                    <div>
                      <div style={{ fontWeight: 600 }}>Cor de destaque</div>
                      <div style={{ fontSize: "0.875rem", color: "var(--ink-2)" }}>{accentColor}</div>
                    </div>
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <input
                      type="color"
                      value={bgColor}
                      onChange={e => setBgColor(e.target.value)}
                      style={{ width: "48px", height: "48px", border: "none", borderRadius: "4px", cursor: "pointer" }}
                    />
                    <div>
                      <div style={{ fontWeight: 600 }}>Cor de fundo</div>
                      <div style={{ fontSize: "0.875rem", color: "var(--ink-2)" }}>{bgColor}</div>
                    </div>
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>URL do logo (https://)</span>
                    <input
                      className="mock-input"
                      value={logoUrl}
                      onChange={e => setLogoUrl(e.target.value)}
                      placeholder="https://example.com/logo.png"
                      style={{ width: "100%" }}
                    />
                    {logoUrl && (
                      <img
                        src={logoUrl}
                        alt="Preview do logo"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                        style={{ marginTop: "0.5rem", height: "60px", objectFit: "contain" }}
                      />
                    )}
                  </label>
                  <button type="submit" className="mock-button" disabled={loading}>
                    {loading ? "Salvando..." : "Salvar tema"}
                  </button>
                </div>
              </form>
            )}

            {activeSection === "notificacoes" && (
              <form onSubmit={handleSalvarNotificacoes}>
                <h2 style={{ marginBottom: "1.5rem" }}>Preferências de Notificação</h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <input
                      type="checkbox"
                      checked={notifAtivo}
                      onChange={e => setNotifAtivo(e.target.checked)}
                      style={{ width: "18px", height: "18px" }}
                    />
                    <span>Enviar lembretes de agendamento pelo WhatsApp</span>
                  </label>
                  <label>
                    <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Avisar com quanto tempo de antecedência?</span>
                    <select
                      value={notifHoras}
                      onChange={e => setNotifHoras(Number(e.target.value))}
                      style={{ padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink)" }}
                    >
                      <option value={1}>1 hora antes</option>
                      <option value={2}>2 horas antes</option>
                      <option value={4}>4 horas antes</option>
                      <option value={8}>8 horas antes</option>
                      <option value={24}>24 horas antes</option>
                    </select>
                  </label>
                  <p style={{ fontSize: "0.8rem", color: "var(--ink-2)" }}>
                    Nota: a integração dos lembretes com o scheduler está prevista para uma próxima versão.
                  </p>
                  <button type="submit" className="mock-button" disabled={loading}>
                    {loading ? "Salvando..." : "Salvar preferências"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </main>
    );
  }
  ```

- [ ] **Step 8.3: Run TypeScript build**

  ```bash
  cd /path/to/project/frontend && npm run build 2>&1 | tail -20
  ```
  Fix any TypeScript errors (most likely: wrong import paths, missing types).

- [ ] **Step 8.4: Commit**

  ```bash
  git add frontend/app/configuracoes/page.tsx
  git commit -m "feat(frontend): página /configuracoes com sidebar e 4 seções"
  ```

---

## Task 9: Final verification + push

**Files:**
- No new files

- [ ] **Step 9.1: Run full backend test suite**

  ```bash
  cd /path/to/project/backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: 131 tests pass.

- [ ] **Step 9.2: Run frontend build**

  ```bash
  cd /path/to/project/frontend && npm run build 2>&1 | tail -15
  ```
  Expected: Build succeeds with no errors.

- [ ] **Step 9.3: Push**

  ```bash
  cd /path/to/project && git push origin main
  ```

---

## Deploy Instructions

1. `git pull` no VPS
2. `pip install -r requirements.txt` (sem novos pacotes)
3. Reiniciar backend — `init_db()` executa `_ensure_configuracoes_columns()` automaticamente
4. Deploy do frontend (`npm run build` + deploy)
5. Verificar `/configuracoes` acessível após login
6. Verificar `GET /auth/me` retornando `accent_color`, `bg_color`, etc.
