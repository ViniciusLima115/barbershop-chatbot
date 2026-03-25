# Spec — Página de Configurações (Spec 2)

**Data:** 2026-03-25
**Status:** Aprovado pelo usuário
**Projeto:** barbearia-chatbot SaaS

---

## Contexto

O sistema já possui uma página `/gestao` para configurações operacionais (serviços, profissionais, horários). Esta spec cobre uma nova página separada `/configuracoes` com foco em conta, identidade visual e preferências do estabelecimento.

Pré-requisitos concluídos (Fase 1 + Fase 2):
- Senhas com bcrypt, JWT via PyJWT, logout com blacklist
- Models `Estabelecimento`/`Profissional`, endpoint `GET /auth/me`
- `tipo_servico` por tenant

---

## Escopo

### O que está incluído
1. **Perfil do Estabelecimento** — nome, endereço, WhatsApp, slug
2. **Troca de Senha** — senha atual + nova senha com validação bcrypt
3. **Tema por Tenant** — accent color, background color, logo URL; aplicado na página pública e no painel admin
4. **Preferências de Notificação** — ativar/desativar lembretes + antecedência em horas

### O que NÃO está incluído
- Upload de arquivo para logo (campo URL simples)
- Tema para emails/notificações
- Configurações de profissionais/serviços (já estão em /gestao)

---

## Arquitetura

### Abordagem de dados: colunas diretas em `estabelecimentos`

Colunas novas adicionadas via `_ensure_configuracoes_columns()` em `database.py`:

| Coluna | Tipo | Default |
|---|---|---|
| `accent_color` | `VARCHAR(7)` | `'#d4930a'` |
| `bg_color` | `VARCHAR(7)` | `'#ffffff'` |
| `logo_url` | `VARCHAR(500)` | `NULL` |
| `notif_ativo` | `BOOLEAN` | `TRUE` |
| `notif_horas_antes` | `INTEGER` | `2` |

Justificativa: colunas explícitas são mais simples de validar e consultar que um JSONB blob. Compatível com o padrão `_ensure_*` já adotado.

---

## Backend

### Novo router: `backend/app/routes/configuracoes.py`
Prefix: `/configuracoes`
Autenticação: `Depends(get_current_claims)` — apenas tenants (não admin)

#### Endpoints

**`PATCH /configuracoes/perfil`**
```
Body: { nome, endereco, whatsapp_number, slug }
Validação: slug único (exceto o próprio tenant), whatsapp formato básico
Response: 200 { detail: "Perfil atualizado." }
```

**`PATCH /configuracoes/senha`**
```
Body: { senha_atual, nova_senha }
Validação:
  - verificar_senha(senha_atual, est.senha) → 400 se errado
  - len(nova_senha) >= 8 → 422 se curta
  - hash_senha(nova_senha) antes de salvar
Response: 200 { detail: "Senha alterada com sucesso." }
```

**`PATCH /configuracoes/tema`**
```
Body: { accent_color, bg_color, logo_url }
Validação: accent_color e bg_color são hex válidos (#rrggbb)
Response: 200 { detail: "Tema atualizado." }
```

**`PATCH /configuracoes/notificacoes`**
```
Body: { notif_ativo, notif_horas_antes }
Validação: notif_horas_antes in [1, 2, 4, 8, 24]
Response: 200 { detail: "Preferências de notificação atualizadas." }
```

### Extensão de `GET /auth/me`
`MeResponse` passa a incluir:
```python
accent_color: str = "#d4930a"
bg_color: str = "#ffffff"
logo_url: str | None = None
notif_ativo: bool = True
notif_horas_antes: int = 2
```

### Schemas
Novo arquivo `backend/app/schemas/configuracoes.py`:
- `PerfilUpdate`
- `SenhaUpdate`
- `TemaUpdate`
- `NotificacoesUpdate`

### Testes (TDD — test file: `backend/tests/test_configuracoes.py`)
- `test_atualizar_perfil_sucesso`
- `test_atualizar_perfil_slug_duplicado`
- `test_trocar_senha_correto`
- `test_trocar_senha_atual_errada`
- `test_trocar_senha_muito_curta`
- `test_atualizar_tema_sucesso`
- `test_atualizar_tema_cor_invalida`
- `test_atualizar_notificacoes_sucesso`
- `test_atualizar_notificacoes_horas_invalidas`
- `test_configuracoes_requer_autenticacao`
- `test_admin_nao_acessa_configuracoes` (admin é bloqueado — endpoint é só para tenants)
- `test_me_retorna_campos_de_tema`

---

## Frontend

### Nova página: `frontend/app/configuracoes/page.tsx`
- Protegida pelo middleware (redireciona para `/login` se não autenticado)
- Não acessível para admin (`is_admin === true` → redirecionar para `/admin`)

### Layout: Sidebar + Conteúdo
```
┌─────────────┬──────────────────────────────┐
│ ⚙ Config.   │                              │
│             │  [seção ativa]               │
│ ● Perfil    │                              │
│   Senha     │  formulário da seção         │
│   Tema      │                              │
│   Notif.    │                              │
└─────────────┴──────────────────────────────┘
```
- Sidebar fixa, estado `activeSection` local (React `useState`)
- Em mobile: sidebar vira menu dropdown/accordion

### Adição ao Header
Novo item "Configurações" no nav do `Header.tsx` (ícone de engrenagem), visível apenas para tenants logados (não admin).

### Sistema de Tema por Tenant

#### Carregamento
1. No login, `GET /auth/me` retorna `accent_color`, `bg_color`, `logo_url`
2. Salvos no `localStorage` junto com a sessão (`barbershop_auth_session`)
3. Hook `useTenantTheme()` aplica ao `document.documentElement`:
   ```ts
   document.documentElement.style.setProperty("--accent", accentColor)
   document.documentElement.style.setProperty("--bg-tenant", bgColor)
   ```
4. Script de early injection (no `<head>`) previne flash ao recarregar

#### Página pública `/[slug]`
- Busca dados do estabelecimento via `GET /public/estabelecimento/{slug}` (já existe)
- Aplica tema localmente na página apenas (não afeta o resto da SPA)

#### Preview ao vivo
- Na seção Tema, mudança de cor aplica `style.setProperty` imediatamente
- "Salvar" → `PATCH /configuracoes/tema` → atualiza `localStorage`

### Seção Tema
- `<input type="color">` para accent_color e bg_color
- Campo texto para logo_url + `<img>` de preview (com fallback se URL inválida)
- Botão "Salvar tema"

### Seção Notificações
- Toggle (checkbox estilizado) para `notif_ativo`
- `<select>` com opções: 1h, 2h, 4h, 8h, 24h
- Botão "Salvar preferências"

### Seção Senha
- Campos: senha atual · nova senha · confirmar nova senha
- Validação client-side: mínimo 8 chars, confirmação igual
- Feedback de erro inline (não toast)

### Seção Perfil
- Campos: nome, endereço, WhatsApp, slug
- Validação client-side básica antes do PATCH
- Mostrar URL da página pública baseada no slug atual

---

## Fluxo de Dados

```
Login → GET /auth/me → salva tema no localStorage
                     ↓
             useTenantTheme() aplica CSS vars
                     ↓
           /configuracoes/tema → PATCH → atualiza localStorage + reaplicar vars
```

---

## Instruções de Deploy

1. Backend: `git pull` + reiniciar serviço (`init_db` executa `_ensure_configuracoes_columns`)
2. Frontend: `npm run build` + deploy
3. Sem necessidade de script de migração de dados (defaults cobrem todos os registros existentes)
