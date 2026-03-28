# Spec: Aba "Análise" no Dashboard Premium

**Data:** 2026-03-28

## Objetivo

Adicionar uma aba "Análise" ao dashboard premium existente com 5 blocos de métricas usando dados mockados, mantendo 100% do estilo visual atual.

---

## Decisões de design

- **Estrutura:** abas (tabs) — "Visão geral" (conteúdo atual) e "Análise" (novo)
- **Arquitetura:** componente separado `AnaliseTab.tsx`; `page.tsx` gerencia a tab ativa
- **Dados:** todos mockados como constantes em `AnaliseTab.tsx`; sem chamadas de API
- **Dependências novas:** nenhuma — recharts já instalado, mas Bloco 2 usa CSS puro (pattern de progress bar já existente)

---

## Arquivos

| Arquivo | Ação |
|---|---|
| `frontend/app/dashboard/page.tsx` | Modificar — adicionar state `activeTab`, barra de tabs, renderização condicional |
| `frontend/app/dashboard/AnaliseTab.tsx` | Criar — 5 blocos com dados mock |
| `frontend/app/dashboard/page.module.css` | Modificar — estilos da tab bar e blocos novos |

---

## Modificações em `page.tsx`

### Tab bar

Posicionada entre o `<section className={styles.hero}>` e o conteúdo principal (`.statsGrid` / `.contentGrid`).

```tsx
type Tab = "visao-geral" | "analise";
const [activeTab, setActiveTab] = useState<Tab>("visao-geral");
```

```tsx
<div className={styles.tabBar}>
  <button
    className={cx(styles.tabBtn, activeTab === "visao-geral" && styles.tabBtnActive)}
    onClick={() => setActiveTab("visao-geral")}
  >
    Visão geral
  </button>
  <button
    className={cx(styles.tabBtn, activeTab === "analise" && styles.tabBtnActive)}
    onClick={() => setActiveTab("analise")}
  >
    Análise
  </button>
</div>
```

O conteúdo original (`.statsGrid` + `.contentGrid`) é envolvido em `{activeTab === "visao-geral" && ...}`. A aba "Análise" renderiza `<AnaliseTab />`.

A função `cx` já existe em `gestao/page.tsx` mas não em `dashboard/page.tsx` — precisa ser adicionada (ou usar template literal simples).

---

## Componente `AnaliseTab.tsx`

### Dados mock

```tsx
const MOCK_RESUMO = {
  agendamentos: 148,
  faturamento: 5920,
  ticketMedio: 40,
  ocupacao: 78,
};

const MOCK_SEMANA = [
  { dia: "Seg", clientes: 22 },
  { dia: "Ter", clientes: 29 },
  { dia: "Qua", clientes: 26 },
  { dia: "Qui", clientes: 40 },
  { dia: "Sex", clientes: 35 },
  { dia: "Sáb", clientes: 18 },
];

const MOCK_HORARIOS = [
  { hora: "18:00", atendimentos: 25 },
  { hora: "17:00", atendimentos: 22 },
  { hora: "09:00", atendimentos: 19 },
  { hora: "10:00", atendimentos: 17 },
  { hora: "14:00", atendimentos: 15 },
];

const MOCK_SERVICOS = [
  { nome: "Corte", total: 110 },
  { nome: "Barba", total: 72 },
  { nome: "Corte + Barba", total: 48 },
  { nome: "Hidratação", total: 22 },
];

const MOCK_CLIENTES = {
  novos: 38,
  recorrentes: 110,
  cancelamentos: 7,
  noShow: 3,
};
```

### Layout (3 linhas)

**Linha 1 — Bloco 1: Resumo do mês**
Grid 4 colunas usando as classes `.statsGrid`, `.statCard`, `.statContent`, `.statLabel`, `.statValue`, `.statHelper`, `.statIcon` já existentes.

Cards:
1. Agendamentos do mês — ícone `Scissors`
2. Faturamento do mês — ícone `DollarSign`, valor formatado com `brl()`
3. Ticket médio — ícone `TrendingUp`, valor formatado com `brl()`
4. Taxa de ocupação — ícone `BarChart2`, valor como `"78%"`

**Linha 2 — Bloco 2 (esquerda) + Bloco 3 (direita)**
Grid `1fr 340px` igual ao `.contentGrid` existente (usa a classe `.contentGrid`).

*Bloco 2 — Movimento da semana* (classe `.panel`):
- Lista de 6 linhas (Seg–Sáb), cada uma com: label do dia, barra horizontal CSS, contagem
- Barra CSS: `.weekBarTrack` (fundo) + `.weekBarFill` (preenchimento proporcional ao máximo)
- Dia com máximo de clientes recebe `.weekBarFillPeak` (cor `var(--accent)` em vez de `var(--accent-soft)`) + label em destaque

*Bloco 3 — Horários mais cheios* (classe `.panel`):
- Lista de 5 itens com rank `#1`–`#5`, horário e contagem
- Item #1 recebe destaque: fundo `var(--accent-soft)`, texto accent
- Demais: fundo `var(--surface-alt)`

**Linha 3 — Bloco 4 (esquerda) + Bloco 5 (direita)**
Grid `1fr 1fr` com gap 20px.

*Bloco 4 — Serviços mais vendidos* (classe `.panel`):
- Reutiliza exatamente as classes `.servicosList`, `.servicoItem`, `.servicoHeader`, `.servicoNome`, `.servicoVendas`, `.progressTrack`, `.progressBar`
- Sem coluna de receita (dados mock não têm — só `total`)

*Bloco 5 — Clientes novos vs recorrentes + Cancelamentos* (classe `.panel`):
- Dois grupos separados por um `<hr>` ou divisor visual
- Grupo 1 (clientes): grid 2 colunas usando `.clienteStatItem`, `.clienteStatValue`, `.clienteStatLabel`
- Grupo 2 (cancelamentos): grid 2 colunas usando `.clienteStatItem` + `.clienteStatItemDanger` (variante vermelha)
  - "Cancelamentos" e "Faltas (no-show)" com `color: var(--danger)` e `background: var(--danger-soft, #fff5f5)`

---

## Novas classes CSS em `page.module.css`

```css
/* ── Tab bar ───────────────────────────────────────────────── */
.tabBar { ... }        /* flex, gap, margin, border-bottom */
.tabBtn { ... }        /* base tab button — ghost, sem borda */
.tabBtnActive { ... }  /* border-bottom accent, cor accent */

/* ── Análise — layout ──────────────────────────────────────── */
.analiseGrid3Col { ... } /* grid 1fr 340px, gap 20px, margin-top 20px */
.analiseGrid2Col { ... } /* grid 1fr 1fr, gap 20px, margin-top 20px */

/* ── Bloco 2 — barras semanais ─────────────────────────────── */
.weekBarList { ... }     /* grid, gap 8px */
.weekBarItem { ... }     /* flex, align-items center, gap 10px */
.weekBarLabel { ... }    /* largura fixa 28px, font-size 0.82rem */
.weekBarLabelPeak { ... }/* cor accent, font-weight 700 */
.weekBarTrack { ... }    /* flex:1, height 16px, background surface-alt, border-radius */
.weekBarFill { ... }     /* height 100%, background accent-soft, border-radius, transition */
.weekBarFillPeak { ... } /* background accent */
.weekBarCount { ... }    /* font-size 0.78rem, color ink-muted, min-width 24px, text-right */
.weekBarCountPeak { ... }/* color accent, font-weight 700 */

/* ── Bloco 3 — ranking horários ────────────────────────────── */
.rankList { ... }        /* grid, gap 6px */
.rankItem { ... }        /* flex, gap 10px, padding, border-radius, background surface-alt */
.rankItemTop { ... }     /* background accent-soft */
.rankPos { ... }         /* font-size 0.72rem, font-weight 800, color ink-subtle, min-width */
.rankPosTop { ... }      /* color accent */
.rankLabel { ... }       /* flex:1, font-weight 700 */
.rankCount { ... }       /* font-size 0.78rem, color ink-muted */
.rankCountTop { ... }    /* color accent, font-weight 700 */

/* ── Bloco 5 — métrica danger ──────────────────────────────── */
.clienteStatItemDanger { ... } /* background #fff5f5, border danger light */
.clienteStatValueDanger { ... }/* color var(--danger) */
.clienteStatLabelDanger { ... }/* color var(--danger) */

/* ── Bloco 5 — separador ───────────────────────────────────── */
.metricDivider { ... }   /* border-top line, margin 16px 0 */
```

---

## Responsividade

- `@media (max-width: 1120px)`: `.analiseGrid3Col` colapsa para `1fr`
- `@media (max-width: 768px)`: `.analiseGrid2Col` colapsa para `1fr`
- `.statsGrid` já tem breakpoints — reutilizado sem alteração

---

## Fora de escopo

- Conexão com API real para os dados de análise
- Filtros de período (mês/semana/etc.)
- Exportação de dados
