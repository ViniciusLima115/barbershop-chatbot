"use client";

import { useCallback, useEffect, useState } from "react";
import { Lock, TrendingUp, Users, Scissors, DollarSign, ArrowLeft } from "lucide-react";
import Link from "next/link";
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
  getDashboardResumoBasico,
  type FinanceiroResponse,
  type ServicosMaisVendidosResponse,
  type ClientesResponse,
  type ResumoBasicoResponse,
} from "@/services/api";
import styles from "./page.module.css";
import AnaliseTab from "./AnaliseTab";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const pct = (v: number | null) => {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
};

function UpgradeScreen({ minPlan = "basico" }: { minPlan?: "basico" | "premium" }) {
  return (
    <div className={styles.upgradePage}>
      <div className={styles.upgradeCard}>
        <div className={styles.upgradeIcon}>
          <Lock size={28} />
        </div>
        <h1 className={styles.upgradeTitle}>
          {minPlan === "premium" ? "Dashboard Premium" : "Dashboard"}
        </h1>
        <p className={styles.upgradeText}>
          {minPlan === "premium"
            ? <>Acesse analytics financeiros, ranking de serviços e análise de clientes com o plano <strong>Premium</strong>.</>
            : <>Acesse métricas do seu estabelecimento a partir do plano <strong>Básico</strong>.</>
          }
          {" "}Fale com o suporte para fazer upgrade.
        </p>
        <Link href="/upgrade" style={{ display: "inline-block", marginTop: "16px", padding: "10px 24px", background: "var(--accent)", color: "#fff", borderRadius: "8px", fontWeight: 600, fontSize: "0.9rem", textDecoration: "none" }}>
          Ver planos
        </Link>
      </div>
    </div>
  );
}

function DashboardBasico({ tenantId }: { tenantId: string }) {
  const [resumo, setResumo] = useState<ResumoBasicoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const carregarResumo = useCallback(() => {
    getDashboardResumoBasico(tenantId)
      .then(setResumo)
      .catch(() => setError("Erro ao carregar dados. Tente novamente."))
      .finally(() => setLoading(false));
  }, [tenantId]);

  useEffect(() => {
    carregarResumo();
    window.addEventListener("presenca-confirmada", carregarResumo);
    return () => window.removeEventListener("presenca-confirmada", carregarResumo);
  }, [carregarResumo]);

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.loadingPulse} />
        <p style={{ color: "var(--ink-muted)" }}>Carregando dados…</p>
      </div>
    );
  }

  if (error || !resumo) {
    return (
      <div className={styles.loadingState}>
        <p style={{ color: "var(--danger)" }}>{error ?? "Erro desconhecido."}</p>
      </div>
    );
  }

  const brlFmt = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div className={styles.page}>
      <div className={`app-container ${styles.shell}`}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "var(--ink-muted)", fontSize: "0.88rem", fontWeight: 600, marginBottom: "16px", textDecoration: "none" }}>
          <ArrowLeft size={16} />
          Voltar
        </Link>
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Plano Básico</p>
          <h1 className={styles.heroTitle}>Dashboard</h1>
          <p className={styles.heroSubtitle}>Resumo do mês do seu estabelecimento.</p>
        </section>

        <div className={styles.statsGrid}>
          <article className={styles.statCard}>
            <div className={styles.statIcon}><Scissors size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Agendamentos hoje</span>
              <strong className={styles.statValue}>{resumo.agendamentos_hoje}</strong>
              <span className={styles.statHelper}>confirmados ou pendentes</span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><TrendingUp size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Agendamentos no mês</span>
              <strong className={styles.statValue}>{resumo.total_agendamentos_mes}</strong>
              <span className={styles.statHelper}>{resumo.agendamentos_confirmados_mes} confirmados · {resumo.agendamentos_cancelados_mes} cancelados</span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><DollarSign size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Faturamento estimado</span>
              <strong className={styles.statValue}>{brlFmt(resumo.faturamento_estimado_mes)}</strong>
              <span className={styles.statHelper}>agendamentos confirmados no mês</span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><Users size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Clientes únicos</span>
              <strong className={styles.statValue}>{resumo.total_clientes_unicos_mes}</strong>
              <span className={styles.statHelper}>confirmados no mês atual</span>
            </div>
          </article>
        </div>

        <div className={styles.panel} style={{ marginTop: "20px" }}>
          <h2 className={styles.panelTitle} style={{ marginBottom: "8px" }}>Pagamentos online</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem", marginBottom: "10px" }}>
            Valor recebido hoje: <strong>{brlFmt(resumo.valor_recebido_hoje ?? 0)}</strong>
          </p>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem", margin: 0 }}>
            Pendentes: <strong>{resumo.pagamentos_pendentes ?? 0}</strong> · Expirados:{" "}
            <strong>{resumo.pagamentos_expirados ?? 0}</strong>
          </p>
        </div>

        <div className={styles.panel} style={{ marginTop: "20px" }}>
          <h2 className={styles.panelTitle} style={{ marginBottom: "12px" }}>Quer analytics avançados?</h2>
          <p style={{ color: "var(--ink-muted)", fontSize: "0.9rem", marginBottom: "16px" }}>
            Com o plano <strong>Premium</strong> você acessa dashboard financeiro completo, ranking de serviços, análise de clientes e muito mais.
          </p>
          <Link href="/upgrade" style={{ display: "inline-block", padding: "10px 20px", background: "var(--accent)", color: "#fff", borderRadius: "8px", fontWeight: 600, fontSize: "0.9rem", textDecoration: "none" }}>
            Ver plano Premium
          </Link>
        </div>
      </div>
    </div>
  );
}

type Tab = "visao-geral" | "analise";

export default function DashboardPage() {
  const session = useAuthSession();
  const plano = session?.plan ?? "gratis";
  const isPremium = plano === "premium";
  const isBasico = plano === "basico";
  const tenantId = session?.tenantId ?? "";

  const [activeTab, setActiveTab] = useState<Tab>("visao-geral");
  const [financeiro, setFinanceiro] = useState<FinanceiroResponse | null>(null);
  const [servicos, setServicos] = useState<ServicosMaisVendidosResponse | null>(null);
  const [clientes, setClientes] = useState<ClientesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const carregarDadosPremium = useCallback(() => {
    if (!isPremium || !tenantId) return;
<<<<<<< HEAD
    setLoading(true);
=======

>>>>>>> d1b47bb (add-mercadoPago)
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

  useEffect(() => {
    carregarDadosPremium();
    window.addEventListener("presenca-confirmada", carregarDadosPremium);
    return () => window.removeEventListener("presenca-confirmada", carregarDadosPremium);
  }, [carregarDadosPremium]);

  if (!session) return null;
  // Plano gratis: pedir upgrade para basico
  if (!isPremium && !isBasico) return <UpgradeScreen minPlan="basico" />;
  // Plano basico: mostrar dashboard simplificado
  if (isBasico) return <DashboardBasico tenantId={tenantId} />;

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
        {/* Back button */}
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "var(--ink-muted)", fontSize: "0.88rem", fontWeight: 600, marginBottom: "16px", textDecoration: "none" }}>
          <ArrowLeft size={16} />
          Voltar
        </Link>

        {/* Hero */}
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Analytics Premium</p>
          <h1 className={styles.heroTitle}>Dashboard</h1>
          <p className={styles.heroSubtitle}>
            Visão financeira e comportamento de clientes do seu estabelecimento.
          </p>
        </section>

        {/* Tab bar */}
        <div className={styles.tabBar}>
          <button
            className={`${styles.tabBtn}${activeTab === "visao-geral" ? ` ${styles.tabBtnActive}` : ""}`}
            onClick={() => setActiveTab("visao-geral")}
          >
            Visão geral
          </button>
          <button
            className={`${styles.tabBtn}${activeTab === "analise" ? ` ${styles.tabBtnActive}` : ""}`}
            onClick={() => setActiveTab("analise")}
          >
            Análise
          </button>
        </div>

        {activeTab === "analise" && <AnaliseTab />}

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

        <section className={styles.panel} style={{ marginBottom: "20px" }}>
          <h2 className={styles.panelTitle}>Pagamentos online</h2>
          <div className={styles.clienteStats}>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{brl(financeiro.valor_recebido_hoje ?? 0)}</strong>
              <span className={styles.clienteStatLabel}>Recebido hoje</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{financeiro.agendamentos_pagos ?? 0}</strong>
              <span className={styles.clienteStatLabel}>Pagamentos aprovados</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>
                {pct(financeiro.taxa_conversao_pagamento ?? null)}
              </strong>
              <span className={styles.clienteStatLabel}>Conversao pagamento</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>
                {financeiro.pagamentos_pendentes ?? 0} / {financeiro.pagamentos_expirados ?? 0}
              </strong>
              <span className={styles.clienteStatLabel}>Pendentes / Expirados</span>
            </div>
          </div>
        </section>

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
      </div>
    </div>
  );
}
