"use client";

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
