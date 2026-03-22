# Redesign Frontend — Barbearia Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar o novo design system (Editorial Limpo, Libre Baskerville + Jost, âmbar `#d4930a`) em todos os arquivos do frontend, substituindo completamente os tokens antigos e o layout da página de login.

**Architecture:** Design System First — reescrever `globals.css` primeiro com todos os novos tokens CSS, depois migrar cada arquivo de módulo CSS e TSX para usar os novos tokens. Nenhuma lógica de negócio é alterada; apenas visual e tipografia.

**Tech Stack:** Next.js App Router, CSS Modules, `next/font/google` (Libre_Baskerville + Jost), Tailwind CSS (via `@import "tailwindcss"`)

---

## Mapa de Arquivos

| Arquivo | Tipo de mudança |
|---|---|
| `frontend/app/layout.tsx` | Substituir fontes: `Cormorant_Garamond + Outfit` → `Libre_Baskerville + Jost` |
| `frontend/app/globals.css` | Reescrever completamente: novos tokens, tipografia, componentes base, dark mode |
| `frontend/app/components/Header.module.css` | Remapear tokens antigos (`--header-*`, `--theme-*`) → novos (`--ink`, `--surface`, `--line`, `--accent`) |
| `frontend/app/components/ThemeToggle.module.css` | Remapear tokens antigos → novos |
| `frontend/app/components/AppShell.tsx` | Remover `inLogin` da condição do ThemeToggle floating |
| `frontend/app/login/page.tsx` | Reestruturar JSX para split-screen (lógica de estado inalterada) |
| `frontend/app/login/page.module.css` | Reescrever para split-screen layout |
| `frontend/app/page.module.css` | Remapear tokens antigos → novos, refinamentos visuais |
| `frontend/app/agenda/page.module.css` | Remapear tokens antigos → novos |
| `frontend/app/components/AgendaGrid.module.css` | Remapear `--theme-line`, `--theme-panel-soft` → novos tokens |
| `frontend/app/components/AgendaCell.module.css` | Remapear status colors + fix `.cellSelected` hardcoded |
| `frontend/app/gestao/page.module.css` | Remapear tokens antigos → novos |

---

## Task 1: Substituir fontes em `layout.tsx`

**Files:**
- Modify: `frontend/app/layout.tsx`

**Contexto:** O arquivo atual importa `Cormorant_Garamond` e `Outfit`. Precisamos trocar por `Libre_Baskerville` e `Jost` mantendo as mesmas variáveis CSS (`--font-display`, `--font-body`).

- [ ] **Step 1: Editar as importações de fonte**

Abrir `frontend/app/layout.tsx` e substituir:

```tsx
// DE:
import { Cormorant_Garamond, Outfit } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

// PARA:
import { Libre_Baskerville, Jost } from "next/font/google";

const libreBaskerville = Libre_Baskerville({
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const jost = Jost({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});
```

- [ ] **Step 2: Atualizar o `<body>` para usar as novas variáveis**

Substituir a linha do `<body>`:
```tsx
// DE:
<body className={`antialiased ${cormorant.variable} ${outfit.variable}`} suppressHydrationWarning>

// PARA:
<body className={`antialiased ${libreBaskerville.variable} ${jost.variable}`} suppressHydrationWarning>
```

- [ ] **Step 3: Verificar build**

```bash
cd frontend && npm run build 2>&1 | tail -20
```
Esperado: sem erros de TypeScript ou de fonte não encontrada.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat: substituir fontes Cormorant+Outfit por Libre Baskerville+Jost"
```

---

## Task 2: Reescrever `globals.css` com novos tokens

**Files:**
- Modify: `frontend/app/globals.css`

**Contexto:** O arquivo atual tem tokens antigos como `--theme-accent: #c36b2d`, `--header-bg`, `--bg`, etc., além de um bloco `[data-theme="dark"] .bg-white` de overrides Tailwind que deve ser removido. O novo globals.css define a paleta completa nova (âmbar `#d4930a`, escala de neutros preto/cinza/branco) e os componentes base (botões, inputs, badges).

**ATENÇÃO:** Este arquivo é o pivô de toda a migração. Após esta task, **todos** os outros arquivos de módulo CSS que ainda referenciam os tokens antigos ficam sem resolução — eles serão corrigidos nas tasks seguintes. A ordem de execução das tasks 3–12 não importa desde que a Task 2 seja feita primeiro.

- [ ] **Step 1: Reescrever `globals.css` completamente**

Substituir todo o conteúdo do arquivo por:

```css
@import "tailwindcss";

/* ─── TIPOGRAFIA ─────────────────────────────────────────── */
:root {
  --font-display: "Libre Baskerville", Georgia, serif;
  --font-body: "Jost", system-ui, sans-serif;
}

/* ─── PALETA LIGHT MODE ──────────────────────────────────── */
:root {
  --ink:          #1a1a1a;
  --ink-muted:    #4a4a4a;
  --ink-subtle:   #9a9a9a;
  --canvas:       #f9f9f7;
  --surface:      #ffffff;
  --surface-alt:  #f0f0ee;
  --line:         #e0e0dc;
  --overlay:      rgba(0,0,0,0.48);

  --accent:       #d4930a;
  --accent-dark:  #a36f06;
  --accent-soft:  #fef3dc;

  --success:      #166534;
  --success-soft: #f0fdf4;
  --success-line: #bbf7d0;
  --warning:      #854d0e;
  --warning-soft: #fefce8;
  --warning-line: #fde68a;
  --danger:       #991b1b;
  --danger-soft:  #fef2f2;
  --danger-line:  #fecaca;

  --radius-sm:  6px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-xl:  14px;
  --radius-2xl: 16px;

  --shadow-sm:  0 1px 4px rgba(0,0,0,0.06);
  --shadow-md:  0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg:  0 8px 32px rgba(0,0,0,0.10);
}

/* ─── PALETA DARK MODE ───────────────────────────────────── */
[data-theme="dark"] {
  --ink:          #f0f0ee;
  --ink-muted:    #b0b0ae;
  --ink-subtle:   #707070;
  --canvas:       #141414;
  --surface:      #1e1e1c;
  --surface-alt:  #282826;
  --line:         rgba(255,255,255,0.10);
  --overlay:      rgba(0,0,0,0.68);

  --accent:       #e5a820;
  --accent-dark:  #c98f10;
  --accent-soft:  rgba(212,147,10,0.18);

  --success:      #4ade80;
  --success-soft: rgba(74,222,128,0.12);
  --success-line: rgba(74,222,128,0.25);
  --warning:      #fbbf24;
  --warning-soft: rgba(251,191,36,0.12);
  --warning-line: rgba(251,191,36,0.25);
  --danger:       #f87171;
  --danger-soft:  rgba(248,113,113,0.12);
  --danger-line:  rgba(248,113,113,0.25);
}

/* ─── RESET & BASE ───────────────────────────────────────── */
*, *::before, *::after {
  box-sizing: border-box;
}

html {
  font-family: var(--font-body);
  color-scheme: light dark;
}

body {
  background: var(--canvas);
  color: var(--ink);
  font-family: var(--font-body);
  line-height: 1.6;
}

/* ─── TIPOGRAFIA — HEADINGS ──────────────────────────────── */
h1, h2, h3, h4 {
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

h1 { font-size: clamp(2rem, 4vw, 3.5rem); }
h2 { font-size: clamp(1.5rem, 3vw, 2.25rem); }
h3 { font-size: 1.25rem; }
h4 { font-size: 1.05rem; }

/* ─── EYEBROW LABELS ─────────────────────────────────────── */
/* .eyebrow-section: 11px — eyebrows de seção de página */
/* .eyebrow-card: 9px — eyebrows dentro de cards */
.eyebrow-section,
.eyebrow-card {
  font-family: var(--font-body);
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
}
.eyebrow-section { font-size: 11px; }
.eyebrow-card    { font-size: 9px; }

/* ─── BOTÕES BASE ────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 18px;
  border: none;
  border-radius: var(--radius-md);
  font-family: var(--font-body);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
  text-decoration: none;
}
.btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* Primary dark */
.btn-primary {
  background: var(--ink);
  color: #ffffff;
}

/* Primary accent */
.btn-accent {
  background: var(--accent);
  color: #ffffff;
}

/* Secondary */
.btn-secondary {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
}

/* Outline accent */
.btn-outline-accent {
  background: transparent;
  border: 1.5px solid var(--accent);
  color: var(--accent);
}

/* Tamanhos */
.btn-sm  { padding: 6px 14px; font-size: 0.82rem; }
.btn-lg  { padding: 13px 22px; font-size: 0.96rem; }
.btn-xl  { padding: 15px 28px; font-size: 1rem; }

/* ─── INPUTS ─────────────────────────────────────────────── */
.input {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 11px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(212,147,10,0.12);
}
.input::placeholder {
  color: var(--ink-subtle);
}

/* ─── BADGES ─────────────────────────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-family: var(--font-body);
  font-size: 0.75rem;
  font-weight: 700;
  border: 1px solid;
}
.badge-confirmado {
  background: var(--success-soft);
  color: var(--success);
  border-color: var(--success-line);
}
.badge-pendente {
  background: var(--warning-soft);
  color: var(--warning);
  border-color: var(--warning-line);
}
.badge-cancelado {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: var(--danger-line);
}
.badge-livre {
  background: var(--surface-alt);
  color: var(--ink-subtle);
  border-color: var(--line);
}

/* ─── ICON BUTTON ────────────────────────────────────────── */
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.icon-button:hover {
  background: var(--surface-alt);
  color: var(--ink);
}
```

- [ ] **Step 2: Verificar que o build compila e que o bloco de overrides Tailwind foi removido**

```bash
cd frontend && npm run build 2>&1 | tail -30
```
Esperado: sem erros de sintaxe CSS. Pode haver warnings de tokens antigos em módulos CSS — isso é esperado e será corrigido nas tasks seguintes.

Verificar que nenhum override de classe Tailwind sobrou:
```bash
grep -n "data-theme.*bg-white\|data-theme.*bg-gray" frontend/app/globals.css
```
Esperado: nenhuma saída (zero matches).

- [ ] **Step 3: Verificar localmente que a UI carrega sem quebrar**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/login` e verificar que a página renderiza (mesmo com design parcialmente incorreto enquanto os módulos CSS ainda usam tokens antigos).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: reescrever globals.css com novos design tokens (Editorial Limpo, âmbar)"
```

---

## Task 3: Remapear `Header.module.css`

**Files:**
- Modify: `frontend/app/components/Header.module.css`

**Contexto:** O arquivo usa tokens antigos: `--header-bg`, `--header-line`, `--header-text`, `--header-text-muted`, `--header-chip-bg`, `--header-chip-hover`, `--header-chip-highlight`, `--header-card-bg`, `--header-line-strong`, `--theme-accent`, `--theme-accent-strong`, `--theme-on-accent`, `--shadow-accent`, `--shadow-soft`.

- [ ] **Step 1: Reescrever `Header.module.css`**

Substituir todo o conteúdo por:

```css
.header {
  position: sticky;
  top: 0;
  z-index: 40;
  padding: 12px 0;
  background: var(--canvas);
  border-bottom: 1px solid var(--line);
}

.shell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: var(--ink);
  text-decoration: none;
}

.brandIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  background: #1a1a1a; /* hardcoded — deve permanecer escuro em ambos os temas */
  color: var(--accent);
}

.brandCopy {
  display: grid;
  min-width: 0;
}

.brandEyebrow {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-subtle);
  line-height: 1;
  margin-bottom: 2px;
}

.brandTitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: var(--surface-alt);
}

.navLink {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  color: var(--ink-muted);
  text-decoration: none;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  transition: background 0.15s ease, color 0.15s ease;
}

.navLink:hover {
  background: var(--surface);
  color: var(--ink);
}

.navLinkActive {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-sm);
}

.logoutButton {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink-muted);
  font-family: var(--font-body);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.logoutButton:hover {
  transform: translateY(-1px);
  border-color: var(--ink-subtle);
  color: var(--ink);
}

@media (max-width: 980px) {
  .shell {
    flex-direction: column;
    align-items: stretch;
  }
  .actions {
    flex-direction: column;
    align-items: stretch;
  }
  .nav {
    flex-wrap: wrap;
    border-radius: var(--radius-lg);
  }
  .logoutButton {
    justify-content: center;
  }
}

@media (max-width: 640px) {
  .header {
    padding: 8px 0;
  }
  .brandTitle {
    font-size: 13px;
  }
  .nav {
    gap: 4px;
    padding: 4px;
  }
  .navLink {
    flex: 1 1 calc(50% - 4px);
    justify-content: center;
    min-width: 100px;
  }
}
```

- [ ] **Step 2: Verificar visualmente o header**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/admin` e verificar que o header renderiza corretamente: ícone preto com âmbar, pill de nav cinza, botão Sair.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/components/Header.module.css
git commit -m "feat: remapear Header.module.css para novos design tokens"
```

---

## Task 4: Remapear `ThemeToggle.module.css` + `AppShell.tsx`

**Files:**
- Modify: `frontend/app/components/ThemeToggle.module.css`
- Modify: `frontend/app/components/AppShell.tsx`

**Contexto:**
- `ThemeToggle.module.css` usa tokens antigos: `--header-chip-bg`, `--header-line`, `--shadow-soft`, `--header-text-muted`, `--header-text`, `--header-chip-hover`, `--theme-on-accent`, `--theme-accent`, `--theme-accent-strong`, `--shadow-accent`, `--text-secondary`.
- `AppShell.tsx` linha ~30 tem: `(inLogin || isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />`. O spec determina remover `inLogin` da condição — o toggle flutuante deve aparecer apenas em rotas públicas, não no login.

- [ ] **Step 1: Reescrever `ThemeToggle.module.css`**

Substituir todo o conteúdo por:

```css
.group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface-alt);
}

.floating {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 60;
}

.button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ink-subtle);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.button:hover {
  color: var(--ink);
  background: var(--surface);
}

.buttonActive {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-sm);
}

.status {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 6px;
  color: var(--ink-subtle);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

@media (max-width: 640px) {
  .group {
    gap: 2px;
  }
  .button span,
  .status {
    display: none;
  }
  .button {
    width: 36px;
    padding: 0;
    justify-content: center;
  }
}
```

- [ ] **Step 2: Verificar todas as condições de rota pública em `AppShell.tsx`**

Ler o arquivo `frontend/app/components/AppShell.tsx` e identificar todas as variáveis boolean que representam rotas públicas (ex: `isPublicBookingPath`, `isPublicBookingById`, `inLogin`, e qualquer outra como `isPublicConfirmPath`, `isPublicCancelPath`, etc.).

A condição atual é algo como:
```tsx
(inLogin || isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />
```

O objetivo é remover apenas `inLogin` da condição, preservando todas as outras condições de rota pública (`/agendar`, `/confirmar`, `/cancelar`, `/reagendar`, `/[slug]`).

Após verificar o arquivo, aplicar somente a remoção de `inLogin`:
```tsx
// DE:
(inLogin || isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />

// PARA — remove inLogin mas preserva todos os outros:
(isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />
```

**Nota:** Se existirem variáveis adicionais (ex: `isPublicConfirmPath`) que já estão na condição, elas devem ser mantidas. Apenas `inLogin` é removido.

- [ ] **Step 3: Verificar visualmente**

```bash
cd frontend && npm run dev
```
- Abrir `http://localhost:3000/login` — NÃO deve aparecer ThemeToggle flutuante.
- Abrir `http://localhost:3000/agendar/test` (se existir) — deve aparecer ThemeToggle flutuante.
- Abrir `http://localhost:3000/admin` — ThemeToggle no header deve funcionar.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/ThemeToggle.module.css frontend/app/components/AppShell.tsx
git commit -m "feat: remapear ThemeToggle para novos tokens e remover toggle flutuante do login"
```

---

## Task 5: Reimplementar `login/page.tsx` + `login/page.module.css` (split-screen)

**Files:**
- Modify: `frontend/app/login/page.tsx`
- Modify: `frontend/app/login/page.module.css`

**Contexto:** O login atual é um card centralizado (`<main><div class="shell"><div class="brand">...`). Precisa virar split-screen: painel esquerdo escuro com branding + painel direito claro com formulário.

**REGRA:** A lógica de estado (`useState`, `handleSubmit`) e o card de suporte (overlay + whatsapp) não mudam — apenas a estrutura de wrapping e os estilos.

- [ ] **Step 1: Reescrever `login/page.module.css`**

Substituir todo o conteúdo por:

```css
/* ─── LAYOUT SPLIT-SCREEN ────────────────────────────────── */
.page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.left {
  background: #1a1a1a;
  background-image: repeating-linear-gradient(
    45deg,
    rgba(255,255,255,0.02) 0px,
    rgba(255,255,255,0.02) 1px,
    transparent 1px,
    transparent 12px
  );
  padding: 44px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.right {
  background: #f9f9f7;
  padding: 44px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* ─── PAINEL ESQUERDO ────────────────────────────────────── */
.leftBrand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.leftIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: #d4930a;
  flex-shrink: 0;
}

.leftEyebrow {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.35);
  line-height: 1;
  margin-bottom: 3px;
}

.leftBrandName {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: rgba(255,255,255,0.9);
  letter-spacing: -0.01em;
  line-height: 1;
}

.leftCopy {
  display: grid;
  gap: 12px;
}

.leftTitle {
  font-family: var(--font-display);
  font-size: clamp(1.75rem, 3vw, 2.25rem);
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin: 0;
}

.leftDivider {
  width: 28px;
  height: 2px;
  background: #d4930a;
  border-radius: 2px;
}

.socialProof {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatars {
  display: flex;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid #1a1a1a;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  color: rgba(255,255,255,0.6);
  margin-left: -8px;
}

.avatar:first-child {
  margin-left: 0;
  background: #2a2a2a;
}

.socialText {
  font-family: var(--font-body);
  font-size: 11px;
  color: rgba(255,255,255,0.35);
  line-height: 1.4;
}

.socialText strong {
  color: rgba(255,255,255,0.6);
  font-weight: 600;
}

/* ─── PAINEL DIREITO ─────────────────────────────────────── */
.formEyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #d4930a;
  margin-bottom: 8px;
}

.formTitle {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 3vw, 2.25rem);
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.03em;
  line-height: 1.05;
  margin: 0 0 6px;
}

.formSub {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 13px;
  color: #9a9a9a;
  margin: 0 0 28px;
}

.form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
}

.label {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  color: #4a4a4a;
  letter-spacing: 0.02em;
}

.inputWrap {
  position: relative;
}

.input {
  width: 100%;
  min-height: 46px;
  padding: 0 40px 0 14px;
  border: 1px solid #e0e0dc;
  border-radius: var(--radius-md);
  background: #ffffff;
  color: #1a1a1a;
  font-family: var(--font-body);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.input:focus {
  border-color: #d4930a;
  box-shadow: 0 0 0 3px rgba(212,147,10,0.12);
}

.input::placeholder {
  color: #b0b0ae;
}

.inputIcon,
.ghostButton {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
}

.inputIcon {
  pointer-events: none;
  color: #9a9a9a;
}

.ghostButton {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #9a9a9a;
  cursor: pointer;
}

.ghostButton:hover {
  background: #f0f0ee;
  color: #1a1a1a;
}

.error {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: #fef2f2;
  color: #991b1b;
  font-size: 0.88rem;
  font-weight: 600;
  border: 1px solid #fecaca;
}

.submit {
  width: 100%;
  margin-top: 4px;
  background: #1a1a1a;
  color: #ffffff;
  border: none;
  border-radius: var(--radius-md);
  padding: 13px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
  letter-spacing: 0.02em;
}

.submit:hover:not(:disabled) {
  opacity: 0.88;
  transform: translateY(-1px);
}

.submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.supportLink {
  align-self: center;
  margin-top: 14px;
  border: 0;
  background: transparent;
  color: #d4930a;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.01em;
}

.supportLink:hover {
  color: #a36f06;
}

/* ─── SUPPORT CARD (overlay) ─────────────────────────────── */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: var(--overlay);
  backdrop-filter: blur(4px);
}

.supportCard {
  width: 100%;
  max-width: 24rem;
  padding: 1.25rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-lg);
}

.supportHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.supportIntro {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.supportIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 999px;
  color: var(--accent);
  background: var(--accent-soft);
}

.supportTitle {
  font-size: 1rem;
  font-weight: 700;
}

.supportSub {
  margin-top: 0.1rem;
  color: var(--ink-muted);
  font-size: 0.78rem;
}

.supportText {
  color: var(--ink-muted);
  line-height: 1.6;
}

.supportActions {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.whatsButton,
.closeButton {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  min-height: 2.9rem;
  border-radius: var(--radius-md);
  font-family: var(--font-body);
  font-weight: 700;
  text-decoration: none;
}

.whatsButton {
  border: 0;
  background: linear-gradient(135deg, #20b767, #13834a);
  color: white;
}

.closeButton {
  border: 1px solid var(--line);
  background: var(--surface-alt);
  color: var(--ink);
  cursor: pointer;
}

/* ─── MOBILE ─────────────────────────────────────────────── */
@media (max-width: 768px) {
  .page {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  .left {
    min-height: 160px;
    padding: 24px 20px;
  }
  .right {
    padding: 32px 24px;
  }
}
```

- [ ] **Step 2: Reestruturar `login/page.tsx` para split-screen**

A estrutura JSX atual é:
```tsx
<main className={styles.page}>
  <div className={styles.shell}>
    <div className={styles.brand}>...</div>
    <div className={styles.card}>...</div>
    <button className={styles.supportLink}>...</button>
  </div>
  {showSupportCard && <div className={styles.overlay}>...</div>}
</main>
```

Substituir o JSX de `return (...)` por (mantendo toda a lógica de estado e os handlers idênticos):

```tsx
return (
  <main className={styles.page}>
    {/* PAINEL ESQUERDO — branding */}
    <div className={styles.left}>
      <div className={styles.leftBrand}>
        <div className={styles.leftIcon}>
          {/* Laptop já é o ícone usado no login atual — mantido por consistência */}
          <Laptop size={18} color="white" />
        </div>
        <div>
          <div className={styles.leftEyebrow}>Sistema de gestão</div>
          <div className={styles.leftBrandName}>VirtualBarber</div>
        </div>
      </div>

      <div className={styles.leftCopy}>
        <h1 className={styles.leftTitle}>Sua barbearia,<br />bem gerida.</h1>
        <div className={styles.leftDivider} />
        <div className={styles.socialProof}>
          <div className={styles.avatars}>
            <div className={styles.avatar}>CA</div>
            <div className={styles.avatar}>MB</div>
            <div className={styles.avatar}>+</div>
          </div>
          <div className={styles.socialText}>
            <strong>+50 barbearias</strong><br />já usam o sistema
          </div>
        </div>
      </div>
    </div>

    {/* PAINEL DIREITO — formulário */}
    <div className={styles.right}>
      <p className={styles.formEyebrow}>Área restrita</p>
      <h2 className={styles.formTitle}>Bem-vindo<br />de volta.</h2>
      <p className={styles.formSub}>Acesse o painel da sua barbearia.</p>

      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.field}>
          <label htmlFor="email" className={styles.label}>Usuário</label>
          <div className={styles.inputWrap}>
            <input
              id="email"
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={styles.input}
              placeholder="Digite seu usuário"
              autoComplete="username"
            />
            <User size={16} className={styles.inputIcon} />
          </div>
        </div>

        <div className={styles.field}>
          <label htmlFor="password" className={styles.label}>Senha</label>
          <div className={styles.inputWrap}>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
              placeholder="Digite sua senha"
              autoComplete="current-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className={styles.ghostButton}
              aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
            >
              <Eye size={16} />
            </button>
          </div>
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <button
          type="submit"
          className={styles.submit}
          disabled={loading}
        >
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => setShowSupportCard(true)}
        className={styles.supportLink}
      >
        Esqueceu a senha? Fale com o suporte
      </button>
    </div>

    {/* SUPPORT CARD OVERLAY (inalterado) */}
    {showSupportCard && (
      <div className={styles.overlay}>
        <div className={styles.supportCard}>
          <div className={styles.supportHeader}>
            <div className={styles.supportIntro}>
              <span className={styles.supportIcon}>
                <Headset size={18} />
              </span>
              <div>
                <p className={styles.supportTitle}>Contate o suporte</p>
                <p className={styles.supportSub}>Recuperação de acesso</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowSupportCard(false)}
              className="icon-button"
              aria-label="Fechar card de suporte"
            >
              <X size={16} />
            </button>
          </div>
          <p className={styles.supportText}>
            Para recuperar sua senha, fale com nosso atendimento.
          </p>
          <div className={styles.supportActions}>
            <a
              href="https://wa.me/5582999627481"
              target="_blank"
              rel="noreferrer"
              className={styles.whatsButton}
            >
              <MessageCircle size={16} />
              Falar no WhatsApp
            </a>
            <button
              type="button"
              onClick={() => setShowSupportCard(false)}
              className={styles.closeButton}
            >
              Fechar
            </button>
          </div>
        </div>
      </div>
    )}
  </main>
);
```

- [ ] **Step 3: Verificar visualmente o login**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/login` e verificar:
- Painel esquerdo preto com textura diagonal, logo, "Sua barbearia, bem gerida.", divisor âmbar, avatares.
- Painel direito claro com eyebrow âmbar, título Libre Baskerville, campos com focus âmbar, botão preto.
- No mobile (< 768px): stack vertical, painel esquerdo como banner.

- [ ] **Step 4: Verificar que login funciona**

Testar login com credenciais válidas e verificar que redireciona para `/admin`.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/login/page.tsx frontend/app/login/page.module.css
git commit -m "feat: reimplementar login com layout split-screen (branding + formulário)"
```

---

## Task 6: Remapear `page.module.css` (Dashboard)

**Files:**
- Modify: `frontend/app/page.module.css`

**Contexto:** O arquivo usa tokens antigos (`--theme-panel`, `--theme-line`, `--theme-text`, `--theme-muted`, `--theme-accent`, `--theme-accent-strong`, `--theme-accent-soft`, `--theme-hero-border`, `--theme-canvas`, `--theme-shadow`, `--theme-on-accent`, `--theme-danger-*`, `--theme-success-*`, `--theme-warning-*`). Precisa ser remapeado para os novos tokens. O arquivo também usa `color-mix()` e gradientes hardcoded com o acento antigo `rgba(195, 107, 45, ...)` — substituir para `var(--accent)`.

- [ ] **Step 1: Substituir todas as referências a tokens antigos**

Aplicar as seguintes substituições globais no arquivo:

| Token antigo | Token novo |
|---|---|
| `var(--theme-panel)` | `var(--surface)` |
| `var(--theme-panel-strong)` | `var(--surface)` |
| `var(--theme-panel-soft)` | `var(--surface-alt)` |
| `var(--theme-canvas)` | `var(--canvas)` |
| `var(--theme-text)` | `var(--ink)` |
| `var(--theme-muted)` | `var(--ink-muted)` |
| `var(--theme-line)` | `var(--line)` |
| `var(--theme-line-strong)` | `var(--line)` |
| `var(--theme-hero-border)` | `var(--line)` |
| `var(--theme-shadow)` | `var(--shadow-md)` |
| `var(--theme-accent)` | `var(--accent)` |
| `var(--theme-accent-strong)` | `var(--accent-dark)` |
| `var(--theme-accent-soft)` | `var(--accent-soft)` |
| `var(--theme-on-accent)` | `#ffffff` |
| `var(--theme-danger-soft)` | `var(--danger-soft)` |
| `var(--theme-danger-text)` | `var(--danger)` |
| `var(--theme-success-soft)` | `var(--success-soft)` |
| `var(--theme-success-text)` | `var(--success)` |
| `var(--theme-warning-soft)` | `var(--warning-soft)` |
| `var(--theme-warning-text)` | `var(--warning)` |
| `var(--shadow-soft)` | `var(--shadow-sm)` |
| `var(--shadow-elevated)` | `var(--shadow-md)` |
| `rgba(195, 107, 45, ...)` | `rgba(212, 147, 10, ...)` (mesmo alpha) |
| `rgba(138, 66, 21, ...)` | `rgba(163, 111, 6, ...)` (mesmo alpha) |

Remover o bloco de variáveis locais no topo (`.page { --panel: ...; --line: ...; ... }`) — esses aliases não são mais necessários pois os tokens globais cobrem tudo.

Remover `backdrop-filter: blur(12px)` nos cards (desnecessário no novo sistema flat).

Substituir `border-radius: 28px` e `32px` nos cards principais por `var(--radius-xl)` (14px) ou `var(--radius-2xl)` (16px). Para `.hero` usar `var(--radius-xl)`, para `.statCard` usar `var(--radius-lg)`.

Substituir os gradientes de fundo do `.hero` (`linear-gradient(135deg, var(--surface-soft), var(--panel)), linear-gradient(...)`) por simplesmente `background: var(--surface); border: 1px solid var(--line)`.

- [ ] **Step 2: Verificar visualmente o dashboard**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/admin` (após login) e verificar que os cards, stats, e painéis renderizam corretamente com o novo sistema de cores.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.module.css
git commit -m "feat: remapear page.module.css (dashboard) para novos design tokens"
```

---

## Task 7: Remapear `agenda/page.module.css`

**Files:**
- Modify: `frontend/app/agenda/page.module.css`

**Contexto:** Arquivo usa os mesmos tokens antigos `--theme-*` que o dashboard. A tabela de substituição da Task 6 se aplica aqui também.

- [ ] **Step 1: Aplicar substituições de tokens**

Aplicar as mesmas substituições da tabela da Task 6.

Adicionalmente, remover o bloco de variáveis locais no topo (`.page { --panel: ...; ... }`).

Substituir `border-radius: 28px` nos `.hero`, `.panel`, `.statCard` por `var(--radius-xl)` / `var(--radius-2xl)`.

Simplificar o gradiente de fundo do `.hero` para `background: var(--surface); border: 1px solid var(--line)`.

- [ ] **Step 2: Verificar visualmente a agenda**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/admin/agenda` e verificar que os cards de stats, o hero topbar, o grid de horários e o painel lateral renderizam corretamente.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/agenda/page.module.css
git commit -m "feat: remapear agenda/page.module.css para novos design tokens"
```

---

## Task 8: Remapear `AgendaGrid.module.css` + `AgendaCell.module.css`

**Files:**
- Modify: `frontend/app/components/AgendaGrid.module.css`
- Modify: `frontend/app/components/AgendaCell.module.css`

**Contexto:**
- `AgendaGrid.module.css` usa `--theme-line` e `--theme-panel-soft`.
- `AgendaCell.module.css` usa `--theme-line`, `--theme-text`, `--theme-panel-strong`, `--theme-success-text`, `--theme-success-soft`, `--theme-warning-text`, `--theme-warning-soft`. Atenção especial: `.cellSelected` tem valores hardcoded `rgba(195, 107, 45, ...)` do acento antigo — substituir por tokens novos.

- [ ] **Step 1: Atualizar `AgendaGrid.module.css`**

```css
.grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.column {
  padding: 18px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface-alt);
}

.columnHeader {
  margin-bottom: 14px;
}

.columnTitle {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.1;
}

.columnMeta {
  margin: 6px 0 0;
  color: var(--ink-muted);
  font-size: 0.84rem;
}

.slotGrid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

@media (max-width: 560px) {
  .slotGrid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 2: Atualizar `AgendaCell.module.css`**

```css
.cell {
  display: grid;
  gap: 4px;
  align-content: center;
  min-height: 88px;
  padding: 12px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  text-align: left;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.cellLivre {
  cursor: pointer;
  background: var(--surface);
  color: var(--ink);
}

.cellLivre:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.cellConfirmado {
  cursor: pointer;
  color: var(--success);
  background: var(--success-soft);
  border-color: var(--success-line);
}

.cellIndisponivel {
  cursor: not-allowed;
  color: var(--warning);
  background: var(--warning-soft);
  border-color: var(--warning-line);
  opacity: 0.78;
}

.cellSelected {
  box-shadow: 0 0 0 3px rgba(212,147,10,0.18);
  border-color: var(--accent);
}

.hour {
  font-size: 1rem;
  font-weight: 800;
  line-height: 1;
}

.caption {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
```

- [ ] **Step 3: Verificar visualmente os cards da agenda**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/admin/agenda` e verificar:
- Cells livres: fundo branco, borda cinza.
- Cells confirmadas: fundo verde claro, texto verde.
- Cells indisponíveis: fundo amarelo claro, texto amarelo escuro.
- Cell selecionada: borda âmbar com glow `rgba(212,147,10,0.18)`.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/AgendaGrid.module.css frontend/app/components/AgendaCell.module.css
git commit -m "feat: remapear AgendaGrid e AgendaCell para novos tokens semânticos"
```

---

## Task 9: Remapear `gestao/page.module.css`

**Files:**
- Modify: `frontend/app/gestao/page.module.css`

**Contexto:** Arquivo usa os mesmos tokens antigos `--theme-*` + tokens de cores hardcoded `rgba(195, 107, 45, ...)`. Tabela de substituição da Task 6 se aplica.

- [ ] **Step 1: Aplicar substituições de tokens**

Aplicar todas as substituições da tabela da Task 6.

Adicionalmente:
- Substituir todas as ocorrências de `rgba(195, 107, 45, ...)` por `rgba(212, 147, 10, ...)` (mesmo alpha).
- Substituir `rgba(138, 66, 21, ...)` por `rgba(163, 111, 6, ...)` (mesmo alpha).
- Substituir `linear-gradient(135deg, var(--accent), #a8511c)` por `background: var(--accent)`.
- Remover bloco de variáveis locais no topo (`.page { --bg: ...; ... }`).
- Substituir `color-mix(in srgb, var(--surface-alt) ...)` por aproximações simples com os novos tokens quando necessário.
- Para `.tabButtonActive`: substituir por `background: var(--accent-soft); color: var(--accent-dark); font-weight: 700`.
- Para `border-radius: 28px/32px` nos cards: usar `var(--radius-xl)`.
- Substituir `var(--shadow-soft)` → `var(--shadow-sm)` e `var(--theme-shadow)` → `var(--shadow-md)`.

- [ ] **Step 2: Verificar visualmente gestão**

```bash
cd frontend && npm run dev
```
Abrir `http://localhost:3000/admin/gestao` e verificar:
- Sidebar de tabs com tab ativa em `--accent-soft`.
- Tabelas com thead em `--surface-alt`, row hover correto.
- Formulários com labels Jost 11px, inputs com focus âmbar.
- Modais com `--radius-xl` e `--shadow-lg`.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/gestao/page.module.css
git commit -m "feat: remapear gestao/page.module.css para novos design tokens"
```

---

## Task 10: Verificação Final

**Files:** nenhum arquivo novo

- [ ] **Step 1: Build de produção limpo**

```bash
cd frontend && npm run build 2>&1
```
Esperado: zero erros de TypeScript e zero erros CSS.

- [ ] **Step 2: Testar fluxo completo**

```bash
cd frontend && npm run dev
```
Testar:
1. `http://localhost:3000/login` — split-screen, formulário funciona, redireciona após login.
2. `http://localhost:3000/admin` — dashboard com cards, stats, tokens âmbar.
3. `http://localhost:3000/admin/agenda` — agenda com cells coloridas.
4. `http://localhost:3000/admin/gestao` — gestão com sidebar de tabs.
5. Toggle de tema (claro/escuro) no header — tokens de dark mode funcionam.
6. Fonte Libre Baskerville nos headings, Jost no body.
7. F5 em qualquer rota autenticada — não desloga (fix existente).

- [ ] **Step 3: Commit final (se houver arquivos pendentes)**

Caso algum arquivo tenha ajuste residual, usar caminhos explícitos:

```bash
git add \
  frontend/app/layout.tsx \
  frontend/app/globals.css \
  frontend/app/components/Header.module.css \
  frontend/app/components/ThemeToggle.module.css \
  frontend/app/components/AppShell.tsx \
  frontend/app/login/page.tsx \
  frontend/app/login/page.module.css \
  frontend/app/page.module.css \
  frontend/app/agenda/page.module.css \
  frontend/app/components/AgendaGrid.module.css \
  frontend/app/components/AgendaCell.module.css \
  frontend/app/gestao/page.module.css
git commit -m "chore: verificação final do redesign frontend"
```
