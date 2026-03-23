"use client";

import { useEffect, useState } from "react";
import { Lock, TrendingUp, Users, Scissors, DollarSign } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useAuthSession } from "@/services/auth";
import {
  getDashboardFinanceiro,
  getDashboardServicos,
  getDashboardClientes,
  type FinanceiroResponse,
  type ServicosMaisVendidosResponse,
  type ClientesResponse,
} from "@/services/api";
import styles from "./page.module.css";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const pct = (v: number | null) => {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
};

function UpgradeScreen() {
  return (
    <div className={styles.upgradePage}>
      <div className={styles.upgradeCard}>
        <div className={styles.upgradeIcon}>
          <Lock size={28} />
        </div>
        <h1 className={styles.upgradeTitle}>Dashboard Premium</h1>
        <p className={styles.upgradeText}>
          Acesse analytics financeiros, ranking de serviços e análise de clientes
          com o plano <strong>Premium</strong>. Fale com o suporte para fazer upgrade.
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const session = useAuthSession();
  const isPremium = session?.plan === "premium";
  const tenantId = session?.tenantId ?? "";

  const [financeiro, setFinanceiro] = useState<FinanceiroResponse | null>(null);
  const [servicos, setServicos] = useState<ServicosMaisVendidosResponse | null>(null);
  const [clientes, setClientes] = useState<ClientesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPremium || !tenantId) return;

    setLoading(true);
    Promise.all([
      getDashboardFinanceiro(tenantId),
      getDashboardServicos(tenantId),
      getDashboardClientes(tenantId),
    ])
      .then(([fin, srv, cli]) => {
        setFinanceiro(fin);
        setServicos(srv);
        setClientes(cli);
      })
      .catch(() => setError("Erro ao carregar dados. Tente novamente."))
      .finally(() => setLoading(false));
  }, [isPremium, tenantId]);

  if (!session) return null;
  if (!isPremium) return <UpgradeScreen />;

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.loadingPulse} />
        <p style={{ color: "var(--ink-muted)" }}>Carregando analytics…</p>
      </div>
    );
  }

  if (error || !financeiro || !servicos || !clientes) {
    return (
      <div className={styles.loadingState}>
        <p style={{ color: "var(--danger)" }}>{error ?? "Erro desconhecido."}</p>
      </div>
    );
  }

  const maxVendas = servicos.servicos[0]?.total_vendas ?? 1;

  const variacaoClass =
    financeiro.variacao_percentual === null
      ? ""
      : financeiro.variacao_percentual >= 0
      ? styles.variacaoPositiva
      : styles.variacaoNegativa;

  const mesLabel = (mes: string) => {
    const [year, month] = mes.split("-");
    return new Date(Number(year), Number(month) - 1).toLocaleDateString("pt-BR", {
      month: "short",
    });
  };

  return (
    <div className={styles.page}>
      <div className={`app-container ${styles.shell}`}>
        {/* Hero */}
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Analytics Premium</p>
          <h1 className={styles.heroTitle}>Dashboard</h1>
          <p className={styles.heroSubtitle}>
            Visão financeira e comportamento de clientes da sua barbearia.
          </p>
        </section>

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
      </div>
    </div>
  );
}
