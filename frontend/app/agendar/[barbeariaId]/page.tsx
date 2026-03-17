"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  createPublicBooking,
  lookupPublicBarbershopById,
  lookupClienteByTelefone,
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
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function normalizarTelefone(valor: string) {
  return valor.replace(/\D/g, "");
}

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
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
  const [emailCliente, setEmailCliente] = useState("");
  const [welcomeMsg, setWelcomeMsg] = useState<string | null>(null);
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [today, setToday] = useState("");
  const [data, setData] = useState("");
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    const currentDate = hojeISO();
    setToday(currentDate);
    setData(currentDate);
  }, []);

  useEffect(() => {
    let ativo = true;

    async function carregar() {
      if (!Number.isFinite(barbeariaId)) return;
      setLoading(true);
      setErro(null);

      try {
        const base = await lookupPublicBarbershopById({ barbearia_id: barbeariaId });
        if (!ativo) return;
        setLookup(base);
        setBarbeiroId(base.barbeiros[0]?.id ?? null);
        setServicoId(base.servicos[0]?.id ?? null);
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Nao foi possivel carregar a agenda.");
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
      if (!Number.isFinite(barbeariaId) || !barbeiroId || !servicoId || !data) return;
      try {
        const atualizado = await lookupPublicBarbershopById({
          barbearia_id: barbeariaId,
          data,
          barbeiro_id: barbeiroId,
          servico_id: servicoId,
        });
        if (!ativo) return;
        setLookup(atualizado);
        setHoraInicio((atual) => {
          if (!atual) return atual;
          return atualizado.horarios_grade.some((slot) => slot.hora === atual && slot.disponivel)
            ? atual
            : null;
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

    if (!barbeiroId || !servicoId || !horaInicio || !data) {
      setErro("Selecione um horario disponivel.");
      return;
    }

    if (!nomeCliente.trim() || !normalizarTelefone(telefoneCliente) || !emailCliente.trim()) {
      setErro("Preencha nome, telefone e email.");
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
        cliente_email: emailCliente.trim().toLowerCase(),
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
        data,
        hora_inicio: horaInicio,
      });

      setSucesso("Agendamento criado. Enviamos a confirmacao para seu email.");
      setHoraInicio(null);

      const atualizado = await lookupPublicBarbershopById({
        barbearia_id: barbeariaId,
        data,
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
      });
      setLookup(atualizado);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Nao foi possivel concluir o agendamento.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onTelefoneBlur() {
    const digits = normalizarTelefone(telefoneCliente);
    if (!digits || digits.length < 8) return;
    const cliente = await lookupClienteByTelefone(barbeariaId, digits).catch(() => null);
    if (!cliente) {
      setWelcomeMsg(null);
      return;
    }
    if (!nomeCliente) setNomeCliente(cliente.nome);
    if (!emailCliente && cliente.email) setEmailCliente(cliente.email);
    setWelcomeMsg(`Bem-vindo de volta, ${cliente.nome}! ✓`);
  }

  function limparFormulario() {
    setNomeCliente("");
    setTelefoneCliente("");
    setEmailCliente("");
    setBarbeiroId(lookup?.barbeiros[0]?.id ?? null);
    setServicoId(lookup?.servicos[0]?.id ?? null);
    setData(today);
    setHoraInicio(null);
    setErro(null);
    setSucesso(null);
    setWelcomeMsg(null);
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.card}>
          <p className={styles.stateText}>Carregando agenda...</p>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
      <main className={styles.page}>
        <div className={styles.card}>
          <p className={cx(styles.stateText, styles.errorText)}>
            {erro ?? "Barbearia nao encontrada."}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <form className={styles.card} onSubmit={onSubmit}>
        <div className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Agendamento</p>
            <h1 className={styles.title}>{lookup.nome}</h1>
            <p className={styles.subtitle}>Escolha o servico e confirme seu horario.</p>
          </div>
          <div className={styles.summary}>
            <span>{servicoSelecionado ? moedaBRL(servicoSelecionado.preco) : "-"}</span>
            <span>{horaInicio ?? `${horariosDisponiveis} horarios livres`}</span>
          </div>
        </div>

        <div className={styles.gridThree}>
          <label className={styles.field}>
            <span className={styles.label}>Nome</span>
            <input
              className={styles.control}
              required
              value={nomeCliente}
              onChange={(event) => setNomeCliente(event.target.value)}
              placeholder="Seu nome"
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Telefone</span>
            <input
              className={styles.control}
              required
              value={telefoneCliente}
              onChange={(event) => { setTelefoneCliente(event.target.value); setWelcomeMsg(null); }}
              onBlur={onTelefoneBlur}
              placeholder="(82) 99999-0000"
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Email</span>
            <input
              className={styles.control}
              required
              type="email"
              value={emailCliente}
              onChange={(event) => setEmailCliente(event.target.value)}
              placeholder="voce@email.com"
            />
          </label>
        </div>

        <div className={styles.gridThree}>
          <label className={styles.field}>
            <span className={styles.label}>Barbeiro</span>
            <select
              className={styles.control}
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

          <label className={styles.field}>
            <span className={styles.label}>Servico</span>
            <select
              className={styles.control}
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

          <label className={styles.field}>
            <span className={styles.label}>Data</span>
            <input
              className={styles.control}
              type="date"
              min={today || undefined}
              value={data}
              onChange={(event) => {
                setData(event.target.value);
                setHoraInicio(null);
              }}
            />
          </label>
        </div>

        <div className={styles.metaRow}>
          <span>{servicoSelecionado?.nome ?? "Sem servico"}</span>
          <span>{servicoSelecionado ? `${servicoSelecionado.duracao} min` : "-"}</span>
          <span>{formatarDataBR(data)}</span>
        </div>

        <div className={styles.legendRow}>
          <span className={cx(styles.legendPill, styles.legendAvailable)}>Livre</span>
          <span className={cx(styles.legendPill, styles.legendSelected)}>Selecionado</span>
          <span className={cx(styles.legendPill, styles.legendUnavailable)}>Barbeiro indisponivel</span>
        </div>

        {lookup.horarios_grade.length === 0 ? (
          <div className={styles.emptySlots}>
            Nenhum horario aparece nesta data. Esse barbeiro pode estar indisponivel hoje.
          </div>
        ) : (
          <div className={styles.slotGrid}>
            {lookup.horarios_grade.map((slot) => (
              <button
                key={slot.hora}
                type="button"
                disabled={!slot.disponivel}
                onClick={() => setHoraInicio(slot.hora)}
                className={cx(
                  styles.slot,
                  slot.disponivel ? styles.slotAvailable : styles.slotUnavailable,
                  horaInicio === slot.hora && styles.slotSelected
                )}
              >
                <span className={styles.slotHour}>{slot.hora}</span>
                <span className={styles.slotHint}>
                  {slot.disponivel ? "Livre" : "Indisp."}
                </span>
              </button>
            ))}
          </div>
        )}

        {welcomeMsg && !sucesso ? <p className={cx(styles.message, styles.messageSuccess)}>{welcomeMsg}</p> : null}
        {erro ? <p className={cx(styles.message, styles.messageError)}>{erro}</p> : null}
        {sucesso ? <p className={cx(styles.message, styles.messageSuccess)}>{sucesso}</p> : null}

        <div className={styles.actions}>
          <button type="button" className={styles.secondaryButton} onClick={limparFormulario}>
            Limpar
          </button>
          <button type="submit" className={styles.primaryButton} disabled={submitting}>
            {submitting ? "Agendando..." : "Confirmar"}
          </button>
        </div>
      </form>
    </main>
  );
}
