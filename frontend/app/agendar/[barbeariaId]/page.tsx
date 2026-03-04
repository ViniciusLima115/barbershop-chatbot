"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  createPublicBooking,
  lookupPublicBarbershopById,
  PublicLookupResponse,
} from "@/services/api";
import styles from "./page.module.css";

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function moedaBRL(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(valor);
}

function formatarDataBR(dataISO: string) {
  if (!dataISO) return "-";
  const data = new Date(`${dataISO}T00:00:00`);
  if (Number.isNaN(data.getTime())) return dataISO;
  return data.toLocaleDateString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function normalizarTelefone(valor: string) {
  return valor.replace(/\D/g, "");
}

export default function PublicBookingByIdPage() {
  const params = useParams<{ barbeariaId: string }>();
  const barbeariaId = Number(params?.barbeariaId);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [lookup, setLookup] = useState<PublicLookupResponse | null>(null);

  const [nomeCliente, setNomeCliente] = useState("");
  const [telefoneCliente, setTelefoneCliente] = useState("");
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [data, setData] = useState(hojeISO());
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;

    async function carregar() {
      if (!Number.isFinite(barbeariaId)) return;
      setLoading(true);
      setErro(null);
      try {
        const base = await lookupPublicBarbershopById({
          barbearia_id: barbeariaId,
        });
        if (!ativo) return;
        setLookup(base);
        setBarbeiroId(base.barbeiros[0]?.id ?? null);
        setServicoId(base.servicos[0]?.id ?? null);
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Nao foi possivel carregar a barbearia.");
      } finally {
        if (ativo) setLoading(false);
      }
    }

    carregar();
    return () => {
      ativo = false;
    };
  }, [barbeariaId]);

  useEffect(() => {
    let ativo = true;

    async function carregarDisponibilidade() {
      if (!Number.isFinite(barbeariaId) || !barbeiroId || !servicoId) return;
      try {
        const atualizado = await lookupPublicBarbershopById({
          barbearia_id: barbeariaId,
          data,
          barbeiro_id: barbeiroId,
          servico_id: servicoId,
        });
        if (!ativo) return;
        setLookup(atualizado);
        setHoraInicio((horaAtual) => {
          if (!horaAtual) return horaAtual;
          const aindaDisponivel = atualizado.horarios_grade.some(
            (slot) => slot.hora === horaAtual && slot.disponivel
          );
          return aindaDisponivel ? horaAtual : null;
        });
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Falha ao carregar horarios.");
      }
    }

    carregarDisponibilidade();
    return () => {
      ativo = false;
    };
  }, [barbeariaId, barbeiroId, servicoId, data]);

  const servicoSelecionado = useMemo(() => {
    if (!lookup || !servicoId) return null;
    return lookup.servicos.find((item) => item.id === servicoId) ?? null;
  }, [lookup, servicoId]);

  const horariosDisponiveis = useMemo(
    () => lookup?.horarios_grade.filter((slot) => slot.disponivel).length ?? 0,
    [lookup]
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!barbeiroId || !servicoId || !horaInicio) {
      setErro("Preencha todos os campos e selecione um horario disponivel.");
      return;
    }

    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      await createPublicBooking({
        barbearia_id: barbeariaId,
        cliente_nome: nomeCliente.trim(),
        cliente_telefone: normalizarTelefone(telefoneCliente),
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
        data,
        hora_inicio: horaInicio,
      });

      setSucesso("Agendamento confirmado. Enviamos a confirmacao no WhatsApp.");
      setHoraInicio(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Nao foi possivel concluir o agendamento.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.pageInner}>
          <div className={styles.stateCard}>
            <p className={styles.stateText}>Carregando pagina de agendamento...</p>
          </div>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
      <main className={styles.page}>
        <div className={styles.pageInner}>
          <div className={styles.stateCard}>
            <p className={`${styles.stateText} ${styles.errorText}`}>
              {erro ?? "Barbearia nao encontrada."}
            </p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.pageInner}>
        <section className={styles.summaryCard}>
          <div className={styles.summaryTop}>
            <div>
              <p className={styles.eyebrow}>Agendamento</p>
              <h1 className={styles.title}>{lookup.nome}</h1>
              <p className={styles.subtitle}>Reserve seu horario em menos de 1 minuto.</p>
            </div>

            <div className={styles.priceCard}>
              <p className={styles.priceLabel}>Valor</p>
              <p className={styles.priceValue}>
                {servicoSelecionado ? moedaBRL(servicoSelecionado.preco) : "-"}
              </p>
            </div>
          </div>

          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <p className={styles.statLabel}>Servico</p>
              <p className={styles.statValue}>
                {servicoSelecionado?.nome ?? "Selecione um servico"}
              </p>
            </div>
            <div className={styles.statCard}>
              <p className={styles.statLabel}>Data</p>
              <p className={styles.statValue}>{formatarDataBR(data)}</p>
            </div>
            <div className={styles.statCard}>
              <p className={styles.statLabel}>Disponiveis</p>
              <p className={styles.statValue}>{horariosDisponiveis}</p>
            </div>
            <div className={styles.statCard}>
              <p className={styles.statLabel}>Selecionado</p>
              <p className={styles.statValue}>{horaInicio ?? "Nenhum horario"}</p>
            </div>
          </div>
        </section>

        <section className={styles.formCard}>
          <form className={styles.form} onSubmit={onSubmit}>
            <div className={styles.stepSection}>
              <div className={styles.stepHeader}>
                <span className={styles.stepBadge}>1</span>
                <h3 className={styles.stepTitle}>Dados pessoais</h3>
              </div>
              <div className={styles.gridTwo}>
                <label className={styles.fieldGroup}>
                  <span className={styles.fieldLabel}>Nome</span>
                  <input
                    className={styles.fieldControl}
                    required
                    value={nomeCliente}
                    onChange={(event) => setNomeCliente(event.target.value)}
                    placeholder="Ex.: Joao Silva"
                  />
                </label>
                <label className={styles.fieldGroup}>
                  <span className={styles.fieldLabel}>Telefone</span>
                  <input
                    className={styles.fieldControl}
                    required
                    value={telefoneCliente}
                    onChange={(event) => setTelefoneCliente(event.target.value)}
                    placeholder="Ex.: (82) 99999-0000"
                  />
                </label>
              </div>
            </div>

            <div className={styles.stepSection}>
              <div className={styles.stepHeader}>
                <span className={styles.stepBadge}>2</span>
                <h3 className={styles.stepTitle}>Servico e profissional</h3>
              </div>
              <div className={styles.gridThree}>
                <label className={styles.fieldGroup}>
                  <span className={styles.fieldLabel}>Barbeiro</span>
                  <select
                    className={styles.fieldControl}
                    value={barbeiroId ?? ""}
                    onChange={(event) => {
                      const valor = Number(event.target.value);
                      setBarbeiroId(Number.isFinite(valor) ? valor : null);
                      setHoraInicio(null);
                    }}
                  >
                    {lookup.barbeiros.map((barbeiro) => (
                      <option key={barbeiro.id} value={barbeiro.id}>
                        {barbeiro.nome}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.fieldGroup}>
                  <span className={styles.fieldLabel}>Servico</span>
                  <select
                    className={styles.fieldControl}
                    value={servicoId ?? ""}
                    onChange={(event) => {
                      const valor = Number(event.target.value);
                      setServicoId(Number.isFinite(valor) ? valor : null);
                      setHoraInicio(null);
                    }}
                  >
                    {lookup.servicos.map((servico) => (
                      <option key={servico.id} value={servico.id}>
                        {servico.nome} - {moedaBRL(servico.preco)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.fieldGroup}>
                  <span className={styles.fieldLabel}>Data</span>
                  <input
                    className={styles.fieldControl}
                    type="date"
                    min={hojeISO()}
                    value={data}
                    onChange={(event) => {
                      setData(event.target.value);
                      setHoraInicio(null);
                    }}
                  />
                </label>
              </div>
            </div>

            <div className={styles.stepSection}>
              <div className={styles.scheduleHeader}>
                <div className={styles.stepHeader}>
                  <span className={styles.stepBadge}>3</span>
                  <h3 className={styles.stepTitle}>Escolha o horario</h3>
                </div>
                <p className={styles.scheduleHint}>Horarios indisponiveis ficam desativados</p>
              </div>

              <div className={styles.timeGrid}>
                {lookup.horarios_grade.map((slot) => {
                  const selected = horaInicio === slot.hora;
                  const timeClasses = [styles.timeSlot];
                  if (slot.disponivel) {
                    timeClasses.push(styles.timeSlotAvailable);
                  } else {
                    timeClasses.push(styles.timeSlotUnavailable);
                  }
                  if (selected) {
                    timeClasses.push(styles.timeSlotSelected);
                  }

                  return (
                    <button
                      key={slot.hora}
                      type="button"
                      disabled={!slot.disponivel}
                      onClick={() => setHoraInicio(slot.hora)}
                      className={timeClasses.join(" ")}
                    >
                      <span className={slot.disponivel ? "" : styles.timeLabelUnavailable}>
                        {slot.hora}
                      </span>
                      {!slot.disponivel && (
                        <span className={styles.unavailableTag}>
                          Indisp.
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {erro && <p className={`${styles.alert} ${styles.alertError}`}>{erro}</p>}
            {sucesso && <p className={`${styles.alert} ${styles.alertSuccess}`}>{sucesso}</p>}

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => {
                  setNomeCliente("");
                  setTelefoneCliente("");
                  setBarbeiroId(lookup.barbeiros[0]?.id ?? null);
                  setServicoId(lookup.servicos[0]?.id ?? null);
                  setData(hojeISO());
                  setHoraInicio(null);
                  setErro(null);
                  setSucesso(null);
                }}
                className={styles.clearButton}
              >
                Limpar
              </button>
              <button
                className={styles.submitButton}
                type="submit"
                disabled={submitting}
              >
                {submitting ? "Agendando..." : "Confirmar agendamento"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
