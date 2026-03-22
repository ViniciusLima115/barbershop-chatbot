# Redesign Frontend — Barbearia Chatbot

**Data:** 2026-03-22
**Status:** Aprovado pelo usuário

---

## Contexto

O frontend atual usa fontes genéricas (system fonts), tem shadows azuis incorretos nos botões primários e inputs (bug), e apesar de ter uma paleta quente decente para barbearias, não transmite profissionalidade suficiente para um produto SaaS. O objetivo é elevar o visual ao nível de um produto premium sem quebrar funcionalidades existentes.

---

## Decisões de Design (aprovadas)

| Decisão | Escolha |
|---|---|
| Estilo geral | Editorial Limpo — preto/branco/cinza |
| Navegação | Top Nav (evolução do atual) |
| Cor de destaque | Âmbar/Dourado `#d4930a` |
| Login | Split Screen — esquerda escura com textura diagonal, direita clara |
| Fontes | **Libre Baskerville** (headings) + **Jost** (body) |

---

## Abordagem de Implementação

**Design System First** — reescrever `globals.css` com novos tokens, depois aplicar arquivo por arquivo. Cada página e componente é consequência natural dos tokens.

---

## Seção 1 — Design Tokens (globals.css)

### Paleta — Light Mode (`:root`)

```css
--ink:          #1a1a1a   /* texto principal, headings */
--ink-muted:    #4a4a4a   /* texto secundário */
--ink-subtle:   #9a9a9a   /* placeholders, hints */
--canvas:       #f9f9f7   /* fundo da página */
--surface:      #ffffff   /* cards, painéis */
--surface-alt:  #f0f0ee   /* fundo alternativo, nav pill */
--line:         #e0e0dc   /* bordas, divisores */
--overlay:      rgba(0,0,0,0.48)

/* Acento âmbar */
--accent:       #d4930a
--accent-dark:  #a36f06   /* hover/pressed E texto sobre --accent-soft */
--accent-soft:  #fef3dc   /* badge backgrounds, highlights */

/* Semânticas */
--success:      #166534
--success-soft: #f0fdf4
--success-line: #bbf7d0
--warning:      #854d0e
--warning-soft: #fefce8
--warning-line: #fde68a
--danger:       #991b1b
--danger-soft:  #fef2f2
--danger-line:  #fecaca
```

### Paleta — Dark Mode (`[data-theme="dark"]`)

```css
--ink:          #f0f0ee
--ink-muted:    #b0b0ae
--ink-subtle:   #707070
--canvas:       #141414
--surface:      #1e1e1c
--surface-alt:  #282826
--line:         rgba(255,255,255,0.1)
--overlay:      rgba(0,0,0,0.68)

--accent:       #e5a820   /* ligeiramente mais claro no escuro */
--accent-dark:  #c98f10
--accent-soft:  rgba(212,147,10,0.18)

--success:      #4ade80
--success-soft: rgba(74,222,128,0.12)
--success-line: rgba(74,222,128,0.25)
--warning:      #fbbf24
--warning-soft: rgba(251,191,36,0.12)
--warning-line: rgba(251,191,36,0.25)
--danger:       #f87171
--danger-soft:  rgba(248,113,113,0.12)
--danger-line:  rgba(248,113,113,0.25)
```

**Nota:** O bloco de overrides de classes Tailwind (`[data-theme="dark"] .bg-white`, etc.) em `globals.css` a partir de `[data-theme="dark"] .bg-white` até o final do arquivo deve ser **removido** — com os novos tokens CSS todas as propriedades são declaradas via variáveis, sem necessidade de overrides por classe utilitária. **Atenção:** `--surface` e `--surface-alt` existem no sistema atual com valores diferentes; como `globals.css` será reescrito por completo isso não é problema, mas qualquer arquivo de módulo migrado parcialmente pode capturar os novos valores — migrar todos os arquivos da lista de uma vez.

### Border Radius (tokens)

```css
--radius-sm:  6px    /* badges, pills pequenas */
--radius-md:  8px    /* botões, inputs, células */
--radius-lg:  12px   /* cards, painéis */
--radius-xl:  14px   /* modais, hero cards */
--radius-2xl: 16px   /* frame principal */
```

### Sombras

```css
--shadow-sm:  0 1px 4px rgba(0,0,0,0.06)
--shadow-md:  0 4px 16px rgba(0,0,0,0.08)
--shadow-lg:  0 8px 32px rgba(0,0,0,0.10)
```

### Tipografia

```css
/* Fontes via next/font/google (substitui Cormorant+Outfit) */
Libre Baskerville — variable: --font-display
  weights: 400, 700 | styles: normal, italic
  uso: h1, h2, h3, h4, números grandes

Jost — variable: --font-body
  weights: 300, 400, 500, 600, 700
  uso: body, labels, botões, navegação, inputs
```

Eyebrow labels (dois tamanhos fixos):
- **11px** — eyebrows de seção de página (`Agenda do dia`, `Painel`)
- **9px** — eyebrows dentro de cards e células

Ambos: `font-family: Jost, font-weight: 700, letter-spacing: 0.16em, text-transform: uppercase`

### Componentes Base

**Botões (4 variantes):**
- Primary dark: `background #1a1a1a, color white, border-radius var(--radius-md), padding 10px 18px`
- Primary accent: `background #d4930a, color white, border-radius var(--radius-md)`
- Secondary: `background var(--surface), border 1px solid var(--line), color var(--ink-muted)`
- Outline accent: `background transparent, border 1.5px solid var(--accent), color var(--accent)`

Hover (todos): `opacity 0.9, transform translateY(-1px)`, duração `0.15s ease`

**Inputs:**
- Default: `background var(--surface), border 1px solid var(--line), border-radius var(--radius-md), padding 11px 14px`
- Focus: `border-color var(--accent), box-shadow 0 0 0 3px rgba(212,147,10,0.12)` — **sem** shadow azul

**Badges:**
- Confirmado: `background var(--success-soft), color var(--success), border 1px solid var(--success-line)`
- Pendente: `background var(--warning-soft), color var(--warning), border 1px solid var(--warning-line)`
- Cancelado: `background var(--danger-soft), color var(--danger), border 1px solid var(--danger-line)`
- Livre: `background var(--surface-alt), color var(--ink-subtle), border 1px solid var(--line)`

---

## Seção 2 — Header (`Header.module.css`)

Sticky top nav com:

- **Esquerda:** icon box `background #1a1a1a, border-radius 8px` com ícone SVG âmbar → eyebrow 9px → nome em Libre Baskerville 14px
- **Centro:** nav pill (`background var(--surface-alt), border-radius 10px, padding 4px`) com links Jost 12px 600; ativo: `background var(--surface), box-shadow var(--shadow-sm)`
- **Direita:** `ThemeToggle` + botão "Sair"

Mobile (`< 768px`): nav pill vira grid 2×2, stack vertical.

---

## Seção 3 — ThemeToggle (`ThemeToggle.module.css` + `ThemeToggle.tsx`)

Arquivo **está em escopo** para modificação.

O `ThemeToggle` existente usa tokens antigos (`--header-chip-bg`, `--header-line`, `--theme-accent`, `--shadow-accent`) que serão removidos. Deve ser remapeado para:
- Container pill: `background var(--surface-alt), border 1px solid var(--line)`
- Botão ativo: `background var(--surface), color var(--ink), box-shadow var(--shadow-sm)`
- Botão inativo: `color var(--ink-subtle)`
- Acento: `color var(--accent)` quando modo selecionado for "dark" ou "light"

O `AppShell.tsx` renderiza `<ThemeToggle floating />` em `/login` e rotas públicas. Com o novo layout split-screen, o ThemeToggle flutuante deve ser **removido da página de login** — o toggle fica apenas no header das páginas autenticadas. Rotas públicas (`/agendar`, `/confirmar`, etc.) mantêm o floating toggle.

---

## Seção 4 — Login (`login/page.module.css` + `login/page.tsx`)

**Ambos os arquivos estão em escopo** — o layout split-screen requer mudanças no TSX além do CSS.

**TSX:** Substituir o wrapper `<main className={styles.page}><div className={styles.shell}>` por uma estrutura de dois painéis:
```
<main className={styles.page}>
  <div className={styles.left}>   ← painel escuro
  <div className={styles.right}>  ← formulário
```
A lógica de submissão e estado (`handleSubmit`, `useState`) não muda.

**CSS — Painel Esquerdo:**
- `background: #1a1a1a`
- Textura diagonal: `repeating-linear-gradient(45deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, transparent 1px, transparent 12px)`
- **Sem** radial-gradient (removido por feedback do usuário)
- Conteúdo: logo + eyebrow → título Libre Baskerville → divisor âmbar 28×2px → social proof
- Social proof: avatares placeholder + texto "Já usam o sistema" — conteúdo é placeholder, não requer dados reais

**CSS — Painel Direito:**
- `background: #f9f9f7`
- Eyebrow âmbar 11px → título "Bem-vindo de volta." → subtítulo itálico Libre Baskerville → campos → botão preto full-width → link suporte âmbar

**Mobile:** stack vertical — painel esquerdo `min-height: 160px`, painel direito ocupa o restante.

---

## Seção 5 — Dashboard (`page.module.css`)

Muda apenas CSS (TSX inalterado).

- **Hero card:** `background var(--surface), border 1px solid var(--line), border-radius var(--radius-xl)` — grid 2 colunas (cópia + aside)
- **Stats row:** 4 cards iguais — ícone em `background var(--accent-soft)` + label 9px + valor Libre Baskerville + helper
- **Content grid** 2 colunas: atalhos rápidos + resumo operacional

---

## Seção 6 — Agenda (`agenda/page.module.css` + `AgendaGrid.module.css` + `AgendaCell.module.css`)

**Todos os três arquivos estão em escopo.**

- **Topbar card:** eyebrow âmbar + data em Libre Baskerville + date picker + botão novo
- **Stats row:** 4 cards (Total / Confirmados verde / Disponíveis / Ocupação âmbar)
- **Grid principal** (3:1): tabela barbeiro × horário + painel lateral
- **`AgendaGrid.module.css`:** remapear tokens de cor de linha/borda para `var(--line)`, `var(--surface-alt)`
- **`AgendaCell.module.css`:** remapear status colors para os novos tokens semânticos (`--success-soft`, `--warning-soft`, etc.); atenção especial para `.cellSelected` que tem valores hardcoded do acento antigo (`rgba(195,107,45,…)`) — substituir por `border-color: var(--accent)` e `box-shadow: 0 0 0 3px rgba(212,147,10,0.18)`
- **Painel lateral:** barbeiros (nome + contagem), legenda, próximo horário livre em `background var(--accent-soft)`

---

## Seção 7 — Gestão (`gestao/page.module.css`)

Muda apenas CSS. A estrutura é **aba lateral vertical** (sidebar 320px + área de conteúdo), não horizontal — o spec usa "aba" referindo-se a esse padrão.

- **Tab sidebar:** `background var(--surface), border-right 1px solid var(--line)` — botão ativo: `background var(--accent-soft), color var(--accent-dark), font-weight 700`
- **Tabelas:** `border-collapse collapse`, thead `background var(--surface-alt)`, row hover `background var(--surface-alt)`
- **Formulários:** label Jost 11px 600, inputs com tokens novos, espaçamento de campos `gap: 16px`
- **Modais:** `border-radius var(--radius-xl), box-shadow var(--shadow-lg)`

---

## Arquivos a Modificar

| Arquivo | Tipo de mudança |
|---|---|
| `frontend/app/layout.tsx` | Substituir `Cormorant_Garamond + Outfit` por `Libre_Baskerville + Jost` (variáveis: `--font-display`, `--font-body`) |
| `frontend/app/globals.css` | Reescrever completamente: tokens, heading styles, componentes base, dark mode, remover bloco de overrides Tailwind |
| `frontend/app/components/Header.module.css` | Remapear para novos tokens |
| `frontend/app/components/ThemeToggle.module.css` | Remapear tokens antigos para novos |
| `frontend/app/components/AppShell.tsx` | Remover `ThemeToggle floating` da rota `/login` |
| `frontend/app/login/page.tsx` | Reestruturar HTML para split-screen (lógica de estado inalterada) |
| `frontend/app/login/page.module.css` | Reescrever para split-screen layout |
| `frontend/app/page.module.css` | Aplicar tokens e refinamentos visuais |
| `frontend/app/agenda/page.module.css` | Aplicar tokens e novo layout topbar |
| `frontend/app/components/AgendaGrid.module.css` | Remapear tokens de cor |
| `frontend/app/components/AgendaCell.module.css` | Remapear status colors para tokens semânticos |
| `frontend/app/gestao/page.module.css` | Aplicar tokens, refinamentos de tab sidebar, tabelas, formulários |

---

## O que NÃO muda

- Lógica de autenticação, rotas e estrutura de páginas
- TSX de componentes funcionais (Modal, Alert, Badge, Button, FormInput, StatCard, Loading) — apenas CSS desses arquivos pode ser ajustado se necessário
- Backend e API
- Páginas públicas (`/agendar`, `/confirmar`, `/cancelar`, `/reagendar`, `/[slug]`)
- `middleware.ts`, `AppShell.tsx` (exceto remoção do floating toggle no login)
