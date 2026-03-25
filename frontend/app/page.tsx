"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarDays, CheckCircle2, Scissors, Settings2, Users } from "lucide-react";
import { listAgendamentos, listClientes, listServicos } from "@/services/api";
import { useAuthSession } from "@/services/auth";
import styles from "./page.module.css";

type DashboardData = {
  totalAgendamentos: number;
  totalClientes: number;
  totalServicos: number;
  agendamentosConfirmados: number;
};

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function StatCard({
  label,
  value,
  helper,
  icon,
}: {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
}) {
  return (
    <article className={styles.statCard}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}

function Panel({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          {eyebrow ? <p className={styles.panelEyebrow}>{eyebrow}</p> : null}
          <h2 className={styles.panelTitle}>{title}</h2>
          {description ? <p className={styles.panelDescription}>{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

export default function Home() {
  const session = useAuthSession();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardData>({
    totalAgendamentos: 0,
    totalClientes: 0,
    totalServicos: 0,
    agendamentosConfirmados: 0,
  });

  useEffect(() => {
    const carregarResumo = async () => {
      setLoading(true);
      setError(null);

      try {
        const [agendamentos, clientes, servicos] = await Promise.all([
          listAgendamentos(),
          listClientes(),
          listServicos(),
        ]);

        setData({
          totalAgendamentos: agendamentos.length,
          totalClientes: clientes.length,
          totalServicos: servicos.length,
          agendamentosConfirmados: agendamentos.filter((item) => item.status === "confirmado").length,
        });
      } catch {
        setError("Nao foi possivel carregar os indicadores. Verifique a conexao com a API.");
      } finally {
        setLoading(false);
      }
    };

    if (!session) return;
    if (session.tenantId === "admin") {
      router.replace("/admin");
      return;
    }
    carregarResumo();
  }, [session, router]);

  const taxaConfirmacao = useMemo(() => {
    if (data.totalAgendamentos === 0) return "0%";
    return `${Math.round((data.agendamentosConfirmados / data.totalAgendamentos) * 100)}%`;
  }, [data.agendamentosConfirmados, data.totalAgendamentos]);

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.hero}>
          <div className={styles.heroCopy}>
            <span className={styles.eyebrow}>Painel operacional</span>
            <h1 className={styles.heroTitle}>{session?.tenantName ?? "Barbearia"}</h1>
            <p className={styles.heroText}>
              Acompanhe a operacao do dia, veja o volume da agenda e avance rapido para os modulos
              mais usados.
            </p>
            <div className={styles.heroActions}>
              <Link href="/agenda" className={cx(styles.actionButton, styles.actionPrimary)}>
                <CalendarDays size={16} />
                Abrir agenda
              </Link>
              <Link href="/gestao" className={cx(styles.actionButton, styles.actionSecondary)}>
                <Settings2 size={16} />
                Abrir gestao
              </Link>
            </div>
          </div>

          <aside className={styles.heroAside}>
            <div className={styles.highlightCard}>
              <span className={styles.highlightLabel}>Hoje</span>
              <strong className={styles.highlightValue}>
                {loading ? "..." : String(data.totalAgendamentos)}
              </strong>
              <span className={styles.highlightHelper}>agendamentos no sistema</span>
            </div>
            <div className={styles.highlightCard}>
              <span className={styles.highlightLabel}>Confirmacao</span>
              <strong className={styles.highlightValue}>{loading ? "..." : taxaConfirmacao}</strong>
              <span className={styles.highlightHelper}>dos agendamentos marcados</span>
            </div>
          </aside>
        </header>

        {error ? <div className={styles.notice}>{error}</div> : null}

        <section className={styles.statsGrid}>
          <StatCard
            label="Agendamentos"
            value={loading ? "..." : String(data.totalAgendamentos)}
            helper="Volume total da agenda"
            icon={<CalendarDays size={20} />}
          />
          <StatCard
            label="Confirmados"
            value={loading ? "..." : String(data.agendamentosConfirmados)}
            helper="Atendimentos prontos para o dia"
            icon={<CheckCircle2 size={20} />}
          />
          <StatCard
            label="Clientes"
            value={loading ? "..." : String(data.totalClientes)}
            helper="Base ativa para novos atendimentos"
            icon={<Users size={20} />}
          />
          <StatCard
            label="Servicos"
            value={loading ? "..." : String(data.totalServicos)}
            helper="Itens disponiveis para agendamento"
            icon={<Scissors size={20} />}
          />
        </section>

        <div className={styles.contentGrid}>
          <Panel
            eyebrow="Acesso rapido"
            title="Seu fluxo principal"
            description="As acoes mais usadas ficam aqui para reduzir clique durante a operacao."
          >
            <div className={styles.actionGrid}>
              <Link href="/agenda" className={styles.shortcutCard}>
                <div className={styles.shortcutIcon}>
                  <CalendarDays size={20} />
                </div>
                <div>
                  <strong className={styles.shortcutTitle}>Agenda do dia</strong>
                  <p className={styles.shortcutText}>Veja os horarios e a disponibilidade por barbeiro.</p>
                </div>
              </Link>
              <Link href="/gestao" className={styles.shortcutCard}>
                <div className={styles.shortcutIcon}>
                  <Settings2 size={20} />
                </div>
                <div>
                  <strong className={styles.shortcutTitle}>Gestao completa</strong>
                  <p className={styles.shortcutText}>Cadastre clientes, servicos, equipe e funcionamento.</p>
                </div>
              </Link>
            </div>
          </Panel>

          <Panel
            eyebrow="Ritmo do dia"
            title="Resumo operacional"
            description="Leitura rapida para saber onde agir primeiro."
          >
            <div className={styles.summaryList}>
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Agenda ocupada</span>
                <strong className={styles.summaryValue}>
                  {loading ? "..." : `${data.agendamentosConfirmados} confirmados`}
                </strong>
              </div>
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Relacionamento</span>
                <strong className={styles.summaryValue}>
                  {loading ? "..." : `${data.totalClientes} clientes cadastrados`}
                </strong>
              </div>
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Catalogo</span>
                <strong className={styles.summaryValue}>
                  {loading ? "..." : `${data.totalServicos} servicos configurados`}
                </strong>
              </div>
            </div>
          </Panel>
        </div>

        <Panel
          eyebrow="Rotina"
          title="Fluxo recomendado"
          description="Uma sequencia simples para a equipe manter o painel sempre organizado."
        >
          <div className={styles.timeline}>
            <div className={styles.timelineStep}>
              <span className={styles.timelineIndex}>1</span>
              <div>
                <strong className={styles.timelineTitle}>Comece pela agenda</strong>
                <p className={styles.timelineText}>Confira horarios livres, bloqueios e ajustes por barbeiro.</p>
              </div>
            </div>
            <div className={styles.timelineStep}>
              <span className={styles.timelineIndex}>2</span>
              <div>
                <strong className={styles.timelineTitle}>Revise cadastros</strong>
                <p className={styles.timelineText}>Mantenha clientes, servicos e equipe atualizados.</p>
              </div>
            </div>
            <div className={styles.timelineStep}>
              <span className={styles.timelineIndex}>3</span>
              <div>
                <strong className={styles.timelineTitle}>Ajuste a operacao</strong>
                <p className={styles.timelineText}>Use a gestao para adaptar os horarios e o atendimento do dia.</p>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </main>
  );
}
