"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  createPublicBooking,
  lookupPublicBarbershop,
  PublicLookupResponse,
} from "@/services/api";

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function moedaBRL(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(valor);
}

function normalizarTelefone(valor: string) {
  return valor.replace(/\D/g, "");
}

export default function PublicBookingPage() {
  const params = useParams<{ slug: string }>();
  const slug = (params?.slug || "").trim().toLowerCase();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [lookup, setLookup] = useState<PublicLookupResponse | null>(null);

  const [nomeCliente, setNomeCliente] = useState("");
  const [telefoneCliente, setTelefoneCliente] = useState("");
  const [emailCliente, setEmailCliente] = useState("");
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [data, setData] = useState(hojeISO());
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;

    async function carregarInicial() {
      if (!slug) return;
      setLoading(true);
      setErro(null);
      try {
        const base = await lookupPublicBarbershop({ slug });
        if (!ativo) return;
        setLookup(base);

        const primeiroBarbeiro = base.barbeiros[0]?.id ?? null;
        const primeiroServico = base.servicos[0]?.id ?? null;
        setBarbeiroId(primeiroBarbeiro);
        setServicoId(primeiroServico);
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Nao foi possivel carregar o estabelecimento.");
      } finally {
        if (ativo) setLoading(false);
      }
    }

    carregarInicial();
    return () => {
      ativo = false;
    };
  }, [slug]);

  useEffect(() => {
    let ativo = true;

    async function carregarDisponibilidade() {
      if (!slug || !barbeiroId || !servicoId) return;
      setErro(null);
      try {
        const atualizado = await lookupPublicBarbershop({
          slug,
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
  }, [slug, barbeiroId, servicoId, data]);

  const servicoSelecionado = useMemo(() => {
    if (!lookup || !servicoId) return null;
    return lookup.servicos.find((item) => item.id === servicoId) ?? null;
  }, [lookup, servicoId]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || !barbeiroId || !servicoId || !horaInicio) {
      setErro("Preencha todos os campos e selecione um horario disponivel.");
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
        slug,
        cliente_nome: nomeCliente.trim(),
        cliente_telefone: normalizarTelefone(telefoneCliente),
        cliente_email: emailCliente.trim().toLowerCase(),
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
        data,
        hora_inicio: horaInicio,
      });

      setSucesso("Agendamento criado. Enviamos a confirmacao por email.");
      setHoraInicio(null);

      const atualizado = await lookupPublicBarbershop({
        slug,
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

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-100 px-4 py-10">
        <div className="mx-auto max-w-4xl rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-600">Carregando pagina de agendamento...</p>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
      <main className="min-h-screen bg-slate-100 px-4 py-10">
        <div className="mx-auto max-w-4xl rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-red-600">
            {erro ?? "Estabelecimento nao encontrado para este link."}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-800 px-4 py-8">
      <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-[1.05fr_1.4fr]">
        <section className="rounded-2xl border border-amber-400/30 bg-zinc-900/70 p-6 text-zinc-100 shadow-xl backdrop-blur">
          <p className="text-xs uppercase tracking-[0.2em] text-amber-300">Agendamento Online</p>
          <h1 className="mt-2 text-3xl font-black leading-tight">{lookup.nome}</h1>
          <p className="mt-3 text-sm text-zinc-300">
            Preencha seus dados, escolha o corte e selecione um horario.
          </p>
          <div className="mt-6 rounded-xl border border-zinc-700 bg-zinc-950/80 p-4">
            <p className="text-xs text-zinc-400">Servico selecionado</p>
            <p className="mt-1 text-lg font-bold text-amber-300">
              {servicoSelecionado ? `${servicoSelecionado.nome} - ${moedaBRL(servicoSelecionado.preco)}` : "-"}
            </p>
            <p className="text-xs text-zinc-400">
              Duracao: {servicoSelecionado ? `${servicoSelecionado.duracao} min` : "-"}
            </p>
          </div>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-xl">
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Nome do cliente</span>
                <input
                  className="input"
                  required
                  value={nomeCliente}
                  onChange={(event) => setNomeCliente(event.target.value)}
                  placeholder="Ex.: Joao Silva"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Telefone (WhatsApp)</span>
                <input
                  className="input"
                  required
                  value={telefoneCliente}
                  onChange={(event) => setTelefoneCliente(event.target.value)}
                  placeholder="Ex.: (82) 99999-0000"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
                <input
                  className="input"
                  required
                  type="email"
                  value={emailCliente}
                  onChange={(event) => setEmailCliente(event.target.value)}
                  placeholder="Ex.: cliente@email.com"
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Barbeiro</span>
                <select
                  className="select"
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

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Tipo de corte</span>
                <select
                  className="select"
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

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Data</span>
                <input
                  className="input"
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

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">Horarios</span>
                <span className="text-xs text-slate-500">Indisponivel = X sobre o horario</span>
              </div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
                {lookup.horarios_grade.map((slot) => {
                  const selecionado = horaInicio === slot.hora;
                  return (
                    <button
                      key={slot.hora}
                      type="button"
                      disabled={!slot.disponivel}
                      onClick={() => setHoraInicio(slot.hora)}
                      className={[
                        "relative rounded-lg border px-2 py-2 text-sm font-semibold transition",
                        slot.disponivel
                          ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                          : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400",
                        selecionado ? "ring-2 ring-blue-500" : "",
                      ].join(" ")}
                    >
                      <span>{slot.hora}</span>
                      {!slot.disponivel && (
                        <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-lg text-red-500">
                          X
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</p>}
            {sucesso && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{sucesso}</p>}

            <button className="btn btn-success w-full" type="submit" disabled={submitting}>
              {submitting ? "Agendando..." : "Confirmar Agendamento"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
