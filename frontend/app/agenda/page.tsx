"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays, CheckCircle2, Clock3, TrendingUp, Users } from "lucide-react";
import AgendaGrid, { SelectedAgendamento } from "../components/AgendaGrid";
import { AgendaDiaResponse, getAgendaDia } from "@/services/api";
import styles from "./page.module.css";

function getLocalISODate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateLabel(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("pt-BR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function calcularDuracaoEmMinutos(inicio?: string, fim?: string): string {
  if (!inicio || !fim) return "Nao informado";

  const inicioDate = new Date(inicio);
  const fimDate = new Date(fim);
  const diffMs = fimDate.getTime() - inicioDate.getTime();
  if (Number.isNaN(diffMs) || diffMs <= 0) return "Nao informado";
  return `${Math.round(diffMs / 60000)} min`;
}

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

function DetailBlock({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className={styles.detailBlock}>
      <span className={styles.detailLabel}>{label}</span>
      <strong className={styles.detailValue}>{value}</strong>
    </div>
  );
}

export default function AgendaPage() {
  const [selectedDate, setSelectedDate] = useState(getLocalISODate());
  const [selectedProfissionalId, setSelectedProfissionalId] = useState("all");
  const [data, setData] = useState<AgendaDiaResponse | null>(null);
  const [selected, setSelected] = useState<SelectedAgendamento | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const carregarAgenda = async () => {
      setLoading(true);
      setError(null);

      try {
        const resposta = await getAgendaDia(selectedDate);
        setData(resposta);
        setSelected(null);
      } catch {
        setData(null);
        setSelected(null);
        setError("Falha ao buscar agenda. Confirme se o backend esta acessivel.");
      } finally {
        setLoading(false);
      }
    };

    carregarAgenda();
  }, [selectedDate]);

  useEffect(() => {
    if (!data) {
      setSelectedProfissionalId("all");
      return;
    }

    if (
      selectedProfissionalId !== "all" &&
      !data.barbeiros.some((barbeiro) => String(barbeiro.id) === selectedProfissionalId)
    ) {
      setSelectedProfissionalId("all");
    }
  }, [data, selectedProfissionalId]);

  const barbeirosVisiveis =
    data?.barbeiros.filter(
      (barbeiro) => selectedProfissionalId === "all" || String(barbeiro.id) === selectedProfissionalId
    ) ?? [];

  const filteredData = data ? { ...data, barbeiros: barbeirosVisiveis } : null;
  const selectedKey = selected ? `${selected.profissionalId}-${selected.hora}` : undefined;
  const totalSlots = filteredData
    ? filteredData.barbeiros.reduce((acc, barbeiro) => acc + barbeiro.horarios.length, 0)
    : 0;
  const totalOcupados = filteredData
    ? filteredData.barbeiros.reduce((acc, barbeiro) => acc + barbeiro.agendamentos.length, 0)
    : 0;
  const totalLivres = Math.max(totalSlots - totalOcupados, 0);
  const taxaOcupacao = totalSlots > 0 ? Math.round((totalOcupados / totalSlots) * 100) : 0;

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.hero}>
          <div className={styles.heroCopy}>
            <span className={styles.eyebrow}>Agenda</span>
            <h1 className={styles.heroTitle}>Controle visual do dia</h1>
            <p className={styles.heroText}>
              Veja a disponibilidade por profissional, acompanhe bloqueios individuais e abra a gestao
              quando precisar ajustar a operacao.
            </p>
          </div>

          <div className={styles.heroControls}>
            <label className={styles.controlGroup}>
              <span className={styles.controlLabel}>Data</span>
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                className={styles.control}
              />
            </label>
            <Link href="/gestao" className={styles.linkButton}>
              Ir para gestao
            </Link>
          </div>
        </header>

        <section className={styles.statsGrid}>
          <StatCard
            label="Slots do dia"
            value={loading ? "..." : String(totalSlots)}
            helper="Todos os horarios validos na agenda"
            icon={<CalendarDays size={20} />}
          />
          <StatCard
            label="Ocupados"
            value={loading ? "..." : String(totalOcupados)}
            helper="Horarios com atendimento marcado"
            icon={<Users size={20} />}
          />
          <StatCard
            label="Livres"
            value={loading ? "..." : String(totalLivres)}
            helper="Espacos ainda disponiveis"
            icon={<Clock3 size={20} />}
          />
          <StatCard
            label="Ocupacao"
            value={loading ? "..." : `${taxaOcupacao}%`}
            helper="Percentual do dia preenchido"
            icon={<TrendingUp size={20} />}
          />
        </section>

        {error ? <div className={styles.notice}>{error}</div> : null}

        <div className={styles.contentGrid}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <p className={styles.panelEyebrow}>Grade</p>
                <h2 className={styles.panelTitle}>Mapa de horarios</h2>
                <p className={styles.panelDescription}>
                  {selectedDate ? `Data selecionada: ${formatDateLabel(selectedDate)}` : "Escolha uma data"}
                </p>
              </div>
              <div className={styles.filterBox}>
                <label htmlFor="profissional-filter" className={styles.controlLabel}>
                  Profissional
                </label>
                <select
                  id="profissional-filter"
                  value={selectedProfissionalId}
                  onChange={(event) => {
                    setSelectedProfissionalId(event.target.value);
                    setSelected(null);
                  }}
                  className={styles.control}
                >
                  <option value="all">Todos os profissionais</option>
                  {data?.barbeiros.map((barbeiro) => (
                    <option key={barbeiro.id} value={String(barbeiro.id)}>
                      {barbeiro.nome}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {loading ? (
              <div className={styles.loadingState}>
                <div className={styles.loadingPulse} />
                <p>Carregando agenda...</p>
              </div>
            ) : filteredData ? (
              <AgendaGrid data={filteredData} selectedKey={selectedKey} onSelect={setSelected} />
            ) : (
              <div className={styles.emptyState}>Nenhum dado de agenda disponivel.</div>
            )}
          </section>

          <aside className={styles.sidePanel}>
            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div>
                  <p className={styles.panelEyebrow}>Legenda</p>
                  <h2 className={styles.panelTitle}>Leitura rapida</h2>
                </div>
              </div>
              <div className={styles.legendList}>
                <div className={styles.legendItem}>
                  <span className={cx(styles.legendSwatch, styles.legendLivre)} />
                  <span>Livre para novo agendamento</span>
                </div>
                <div className={styles.legendItem}>
                  <span className={cx(styles.legendSwatch, styles.legendConfirmado)} />
                  <span>Horario confirmado</span>
                </div>
                <div className={styles.legendItem}>
                  <span className={cx(styles.legendSwatch, styles.legendPendentePagamento)} />
                  <span>Aguardando pagamento</span>
                </div>
                <div className={styles.legendItem}>
                  <span className={cx(styles.legendSwatch, styles.legendIndisponivel)} />
                  <span>Fora do expediente do profissional</span>
                </div>
              </div>
            </section>

            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div>
                  <p className={styles.panelEyebrow}>Detalhes</p>
                  <h2 className={styles.panelTitle}>
                    {selected ? `${selected.profissionalNome} as ${selected.hora}` : "Selecione um horario"}
                  </h2>
                </div>
              </div>

              {!selected ? (
                <div className={styles.emptyState}>
                  Clique em um slot da grade para ver os dados do atendimento ou do horario livre.
                </div>
              ) : selected.agendamento ? (
                <div className={styles.detailStack}>
                  <DetailBlock label="Profissional" value={selected.profissionalNome} />
                  <DetailBlock label="Horario" value={selected.hora} />
                  <DetailBlock label="Cliente" value={selected.agendamento.cliente} />
                  <DetailBlock
                    label="Telefone"
                    value={selected.agendamento.telefone || "Nao informado"}
                  />
                  <DetailBlock label="Servico" value={selected.agendamento.servico} />
                  <DetailBlock
                    label="Duracao"
                    value={calcularDuracaoEmMinutos(
                      selected.agendamento.inicio,
                      selected.agendamento.fim
                    )}
                  />
                  <DetailBlock
                    label="Pagamento"
                    value={selected.agendamento.payment_status || "not_required"}
                  />
                  {selected.agendamento.payment_amount ? (
                    <DetailBlock
                      label="Valor pago/previsto"
                      value={new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
                        selected.agendamento.payment_amount
                      )}
                    />
                  ) : null}
                  {selected.agendamento.payment_method ? (
                    <DetailBlock label="Metodo" value={selected.agendamento.payment_method} />
                  ) : null}
                  <div className={styles.statusBadge}>
                    <CheckCircle2 size={14} />
                    {selected.agendamento.status === "confirmado"
                      ? "Confirmado"
                      : selected.agendamento.status === "pending_payment"
                        ? "Aguardando pagamento"
                        : "Agendado"}
                  </div>
                </div>
              ) : (
                <div className={styles.detailStack}>
                  <DetailBlock label="Profissional" value={selected.profissionalNome} />
                  <DetailBlock label="Horario" value={selected.hora} />
                  <div className={styles.emptyState}>Esse horario esta livre para novo agendamento.</div>
                </div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
