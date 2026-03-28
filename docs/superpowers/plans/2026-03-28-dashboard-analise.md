# Dashboard — Aba Análise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Análise" ao dashboard premium com 5 blocos de métricas usando dados mockados.

**Architecture:** `page.tsx` ganha state `activeTab` e barra de tabs; `AnaliseTab.tsx` (novo componente) contém todos os 5 blocos e dados mock; todas as classes CSS novas são adicionadas ao `page.module.css` existente.

**Tech Stack:** Next.js 14 (App Router), React, CSS Modules, Lucide React

---

## Arquivos

| Arquivo | Ação |
|---|---|
| `frontend/app/dashboard/page.module.css` | Modificar — tab bar + layout analise + blocos 2/3/5 |
| `frontend/app/dashboard/AnaliseTab.tsx` | Criar — 5 blocos com dados mock |
| `frontend/app/dashboard/page.tsx` | Modificar — import, state, tab bar, renderização condicional |

---

## Task 1: CSS — tab bar e blocos da seção Análise

**Files:**
- Modify: `frontend/app/dashboard/page.module.css`

- [ ] **Step 1: Adicionar classes ao final de `page.module.css`**

Abrir `frontend/app/dashboard/page.module.css` e adicionar ao final (após o último `@media`):

```css
/* ── Tab bar ─────────────────────────────────────────────── */
.tabBar {
  display: flex;
  gap: 4px;
  margin-top: 20px;
  border-bottom: 1px solid var(--line);
}

.tabBtn {
  padding: 10px 18px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: color 0.15s;
}

.tabBtn:hover {
  color: var(--ink);
}

.tabBtnActive {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

/* ── Análise — layout ────────────────────────────────────── */
.analiseGrid3Col {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
  margin-top: 20px;
  align-items: start;
}

.analiseGrid2Col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 20px;
  align-items: start;
}

/* ── Bloco 2 — barras semanais ───────────────────────────── */
.weekBarList {
  display: grid;
  gap: 8px;
}

.weekBarItem {
  display: flex;
  align-items: center;
  gap: 10px;
}

.weekBarLabel {
  width: 28px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ink-muted);
  flex-shrink: 0;
}

.weekBarLabelPeak {
  color: var(--accent);
  font-weight: 700;
}

.weekBarTrack {
  flex: 1;
  height: 16px;
  background: var(--surface-alt);
  border-radius: 999px;
  overflow: hidden;
}

.weekBarFill {
  height: 100%;
  background: var(--accent-soft);
  border-radius: 999px;
  transition: width 0.6s ease;
}

.weekBarFillPeak {
  background: var(--accent);
}

.weekBarCount {
  font-size: 0.78rem;
  color: var(--ink-muted);
  min-width: 24px;
  text-align: right;
}

.weekBarCountPeak {
  color: var(--accent);
  font-weight: 700;
}

/* ── Bloco 3 — ranking horários ──────────────────────────── */
.rankList {
  display: grid;
  gap: 6px;
}

.rankItem {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-lg);
  background: var(--surface-alt);
  border: 1px solid var(--line);
}

.rankItemTop {
  background: var(--accent-soft);
  border-color: transparent;
}

.rankPos {
  font-size: 0.72rem;
  font-weight: 800;
  color: var(--ink-muted);
  min-width: 20px;
}

.rankPosTop {
  color: var(--accent);
}

.rankLabel {
  flex: 1;
  font-size: 0.9rem;
  font-weight: 700;
}

.rankCount {
  font-size: 0.82rem;
  color: var(--ink-muted);
}

.rankCountTop {
  color: var(--accent);
  font-weight: 700;
}

/* ── Bloco 5 — métrica danger ────────────────────────────── */
.clienteStatItemDanger {
  background: #fff5f5;
  border-color: #fecaca;
}

.clienteStatValueDanger {
  color: var(--danger);
}

.clienteStatLabelDanger {
  color: var(--danger);
}

.metricDivider {
  border: none;
  border-top: 1px solid var(--line);
  margin: 16px 0;
}

/* ── Responsividade análise ──────────────────────────────── */
@media (max-width: 1120px) {
  .analiseGrid3Col {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .analiseGrid2Col {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend && npx tsc --noEmit 2>&1
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/dashboard/page.module.css
git commit -m "style: classes CSS para tab bar e blocos da aba Análise"
```

---

## Task 2: Criar `AnaliseTab.tsx` com os 5 blocos

**Files:**
- Create: `frontend/app/dashboard/AnaliseTab.tsx`

- [ ] **Step 1: Criar o arquivo `AnaliseTab.tsx`**

Criar `frontend/app/dashboard/AnaliseTab.tsx` com o seguinte conteúdo:

```tsx
import { BarChart2, DollarSign, Scissors, TrendingUp } from "lucide-react";
import styles from "./page.module.css";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

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

export default function AnaliseTab() {
  const maxSemana = Math.max(...MOCK_SEMANA.map((d) => d.clientes));
  const maxServico = MOCK_SERVICOS[0]?.total ?? 1;

  return (
    <div style={{ marginTop: "20px" }}>
      {/* Bloco 1 — Resumo do mês */}
      <div className={styles.statsGrid}>
        <article className={styles.statCard}>
          <div className={styles.statIcon}>
            <Scissors size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Agendamentos</span>
            <strong className={styles.statValue}>{MOCK_RESUMO.agendamentos}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}>
            <DollarSign size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Faturamento</span>
            <strong className={styles.statValue}>{brl(MOCK_RESUMO.faturamento)}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}>
            <TrendingUp size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Ticket médio</span>
            <strong className={styles.statValue}>{brl(MOCK_RESUMO.ticketMedio)}</strong>
            <span className={styles.statHelper}>por agendamento</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}>
            <BarChart2 size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Taxa de ocupação</span>
            <strong className={styles.statValue}>{MOCK_RESUMO.ocupacao}%</strong>
            <span className={styles.statHelper}>da agenda preenchida</span>
          </div>
        </article>
      </div>

      {/* Linha 2: Bloco 2 + Bloco 3 */}
      <div className={styles.analiseGrid3Col}>
        {/* Bloco 2 — Movimento da semana */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Movimento da semana</h2>
          <div className={styles.weekBarList}>
            {MOCK_SEMANA.map((item) => {
              const isPeak = item.clientes === maxSemana;
              return (
                <div key={item.dia} className={styles.weekBarItem}>
                  <span
                    className={
                      isPeak
                        ? `${styles.weekBarLabel} ${styles.weekBarLabelPeak}`
                        : styles.weekBarLabel
                    }
                  >
                    {item.dia}
                  </span>
                  <div className={styles.weekBarTrack}>
                    <div
                      className={
                        isPeak
                          ? `${styles.weekBarFill} ${styles.weekBarFillPeak}`
                          : styles.weekBarFill
                      }
                      style={{ width: `${(item.clientes / maxSemana) * 100}%` }}
                    />
                  </div>
                  <span
                    className={
                      isPeak
                        ? `${styles.weekBarCount} ${styles.weekBarCountPeak}`
                        : styles.weekBarCount
                    }
                  >
                    {item.clientes}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Bloco 3 — Horários mais cheios */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Horários mais cheios</h2>
          <div className={styles.rankList}>
            {MOCK_HORARIOS.map((item, i) => {
              const isTop = i === 0;
              return (
                <div
                  key={item.hora}
                  className={
                    isTop
                      ? `${styles.rankItem} ${styles.rankItemTop}`
                      : styles.rankItem
                  }
                >
                  <span
                    className={
                      isTop
                        ? `${styles.rankPos} ${styles.rankPosTop}`
                        : styles.rankPos
                    }
                  >
                    #{i + 1}
                  </span>
                  <span className={styles.rankLabel}>{item.hora}</span>
                  <span
                    className={
                      isTop
                        ? `${styles.rankCount} ${styles.rankCountTop}`
                        : styles.rankCount
                    }
                  >
                    {item.atendimentos} atend.
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Linha 3: Bloco 4 + Bloco 5 */}
      <div className={styles.analiseGrid2Col}>
        {/* Bloco 4 — Serviços mais vendidos */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Serviços mais vendidos</h2>
          <div className={styles.servicosList}>
            {MOCK_SERVICOS.map((s) => (
              <div key={s.nome} className={styles.servicoItem}>
                <div className={styles.servicoHeader}>
                  <span className={styles.servicoNome}>{s.nome}</span>
                  <span className={styles.servicoVendas}>{s.total}×</span>
                </div>
                <div className={styles.progressTrack}>
                  <div
                    className={styles.progressBar}
                    style={{ width: `${(s.total / maxServico) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Bloco 5 — Clientes & Retenção */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Clientes & Retenção</h2>
          <div className={styles.clienteStats}>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{MOCK_CLIENTES.novos}</strong>
              <span className={styles.clienteStatLabel}>Novos</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{MOCK_CLIENTES.recorrentes}</strong>
              <span className={styles.clienteStatLabel}>Recorrentes</span>
            </div>
          </div>
          <hr className={styles.metricDivider} />
          <div className={styles.clienteStats}>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong
                className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}
              >
                {MOCK_CLIENTES.cancelamentos}
              </strong>
              <span
                className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}
              >
                Cancelamentos
              </span>
            </div>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong
                className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}
              >
                {MOCK_CLIENTES.noShow}
              </strong>
              <span
                className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}
              >
                Faltas (no-show)
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend && npx tsc --noEmit 2>&1
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/dashboard/AnaliseTab.tsx
git commit -m "feat: componente AnaliseTab com 5 blocos de métricas mockadas"
```

---

## Task 3: Adicionar tabs em `page.tsx`

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

- [ ] **Step 1: Adicionar import de `AnaliseTab` e `useState` já está presente**

No topo de `frontend/app/dashboard/page.tsx`, adicionar após os imports existentes:

```tsx
import AnaliseTab from "./AnaliseTab";
```

O `useState` já está importado de `"react"` na linha 3 — não adicionar duplicata.

- [ ] **Step 2: Adicionar `type Tab` e state `activeTab` dentro de `DashboardPage`**

Localizar a linha `const [financeiro, setFinanceiro] = useState<FinanceiroResponse | null>(null);` (~linha 55) e adicionar **antes** dela:

```tsx
type Tab = "visao-geral" | "analise";
const [activeTab, setActiveTab] = useState<Tab>("visao-geral");
```

- [ ] **Step 3: Adicionar tab bar no JSX**

Localizar o bloco `{/* Hero */}` (~linha 118). Após o fechamento `</section>` do hero e **antes** do bloco `{/* Stat cards */}`, adicionar:

```tsx
{/* Tab bar */}
<div className={styles.tabBar}>
  <button
    className={
      activeTab === "visao-geral"
        ? `${styles.tabBtn} ${styles.tabBtnActive}`
        : styles.tabBtn
    }
    onClick={() => setActiveTab("visao-geral")}
  >
    Visão geral
  </button>
  <button
    className={
      activeTab === "analise"
        ? `${styles.tabBtn} ${styles.tabBtnActive}`
        : styles.tabBtn
    }
    onClick={() => setActiveTab("analise")}
  >
    Análise
  </button>
</div>
```

- [ ] **Step 4: Envolver conteúdo "Visão geral" em condicional**

Localizar os dois blocos existentes:
```tsx
{/* Stat cards */}
<div className={styles.statsGrid}>
  ...
</div>

<div className={styles.contentGrid}>
  ...
</div>
```

Envolvê-los em um fragmento condicional. O resultado deve ser:

```tsx
{activeTab === "visao-geral" && (
  <>
    {/* Stat cards */}
    <div className={styles.statsGrid}>
      <article className={styles.statCard}>
        <div className={styles.statIcon}><DollarSign size={22} /></div>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>Faturamento do mês</span>
          <strong className={styles.statValue}>{brl(financeiro.faturamento_mes_atual)}</strong>
          <span className={`${styles.statHelper} ${variacaoClass}`}>
            {pct(financeiro.variacao_percentual)} vs mês anterior
          </span>
        </div>
      </article>

      <article className={styles.statCard}>
        <div className={styles.statIcon}><TrendingUp size={22} /></div>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>Ticket médio</span>
          <strong className={styles.statValue}>{brl(financeiro.ticket_medio)}</strong>
          <span className={styles.statHelper}>por agendamento confirmado</span>
        </div>
      </article>

      <article className={styles.statCard}>
        <div className={styles.statIcon}><Scissors size={22} /></div>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>Agendamentos</span>
          <strong className={styles.statValue}>{financeiro.total_agendamentos}</strong>
          <span className={styles.statHelper}>confirmados no mês atual</span>
        </div>
      </article>

      <article className={styles.statCard}>
        <div className={styles.statIcon}><Users size={22} /></div>
        <div className={styles.statContent}>
          <span className={styles.statLabel}>Clientes únicos</span>
          <strong className={styles.statValue}>{clientes.total_clientes}</strong>
          <span className={styles.statHelper}>últimos 30 dias</span>
        </div>
      </article>
    </div>

    <div className={styles.contentGrid}>
      {/* Coluna principal */}
      <div style={{ display: "grid", gap: "20px" }}>
        {/* Gráfico faturamento */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Faturamento — últimos 12 meses</h2>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={financeiro.historico_12_meses.map((h) => ({
                  mes: mesLabel(h.mes),
                  faturamento: h.faturamento,
                  agendamentos: h.total_agendamentos,
                }))}
                margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis
                  dataKey="mes"
                  tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`}
                  tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
                  axisLine={false}
                  tickLine={false}
                  width={52}
                />
                <Tooltip
                  formatter={(value) => [brl(Number(value)), "Faturamento"]}
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    borderRadius: "8px",
                    fontSize: "13px",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="faturamento"
                  stroke="var(--accent)"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, fill: "var(--accent)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Clientes */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Clientes — últimos 30 dias</h2>
          <div className={styles.clienteStats}>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{clientes.total_clientes}</strong>
              <span className={styles.clienteStatLabel}>Únicos</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{clientes.clientes_novos}</strong>
              <span className={styles.clienteStatLabel}>Novos</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{clientes.clientes_recorrentes}</strong>
              <span className={styles.clienteStatLabel}>Recorrentes</span>
            </div>
          </div>
          {clientes.taxa_cancelamento > 0 && (
            <p style={{ margin: "0 0 16px", fontSize: "0.84rem", color: "var(--danger)" }}>
              Taxa de cancelamento: <strong>{clientes.taxa_cancelamento}%</strong>
            </p>
          )}

          <p className={styles.topClientesTitle}>Top 5 clientes</p>
          <div className={styles.topClientesList}>
            {clientes.top_5_clientes.map((c, i) => (
              <div key={`${c.telefone}-${i}`} className={styles.topClienteRow}>
                <span className={styles.topClienteRank}>#{i + 1}</span>
                <div className={styles.topClienteInfo}>
                  <div className={styles.topClienteNome}>{c.nome}</div>
                  <div className={styles.topClienteTel}>{c.telefone}</div>
                </div>
                <div className={styles.topClienteStats}>
                  <div className={styles.topClienteValor}>{brl(c.valor_total_gasto)}</div>
                  <div className={styles.topClienteVisitas}>{c.total_visitas} visita{c.total_visitas !== 1 ? "s" : ""}</div>
                </div>
              </div>
            ))}
            {clientes.top_5_clientes.length === 0 && (
              <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem" }}>
                Nenhum dado disponível.
              </p>
            )}
          </div>
        </section>
      </div>

      {/* Sidebar — Serviços */}
      <section className={styles.panel}>
        <h2 className={styles.panelTitle}>Serviços mais vendidos</h2>
        <p style={{ margin: "0 0 16px", fontSize: "0.82rem", color: "var(--ink-muted)" }}>
          Últimos 30 dias
        </p>
        <div className={styles.servicosList}>
          {servicos.servicos.map((s) => (
            <div key={s.nome} className={styles.servicoItem}>
              <div className={styles.servicoHeader}>
                <span className={styles.servicoNome}>{s.nome}</span>
                <span className={styles.servicoVendas}>{s.total_vendas}× · {brl(s.receita_total)}</span>
              </div>
              <div className={styles.progressTrack}>
                <div
                  className={styles.progressBar}
                  style={{ width: `${(s.total_vendas / maxVendas) * 100}%` }}
                />
              </div>
            </div>
          ))}
          {servicos.servicos.length === 0 && (
            <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem" }}>
              Nenhum serviço no período.
            </p>
          )}
        </div>
      </section>
    </div>
  </>
)}

{activeTab === "analise" && <AnaliseTab />}
```

- [ ] **Step 5: Verificar TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend && npx tsc --noEmit 2>&1
```

Expected: sem erros.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: tab bar no dashboard — aba Visão geral e aba Análise"
```
