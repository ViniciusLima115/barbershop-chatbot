"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  createPublicBooking,
  lookupPublicBarbershopById,
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
      <main className="min-h-screen bg-gradient-to-b from-slate-100 to-white flex items-center justify-center p-6">
        <div className="w-full max-w-3xl rounded-2xl bg-white p-8 shadow-lg">
          <p className="text-sm text-slate-600">Carregando página de agendamento…</p>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-slate-100 to-white flex items-center justify-center p-6">
        <div className="w-full max-w-3xl rounded-2xl bg-white p-8 shadow-lg">
          <p className="text-sm font-medium text-red-600">{erro ?? "Barbearia não encontrada."}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center py-10 px-4">
      <div className="w-full max-w-5xl grid gap-6 md:grid-cols-2 items-start">
        {/* Left - Hero / Summary */}
        <aside className="order-2 md:order-1 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-800 p-6 text-slate-100 shadow-2xl md:sticky md:top-20">
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-300">Agendamento Online</p>
          <h1 className="mt-2 text-3xl font-extrabold leading-tight">{lookup.nome}</h1>
          <p className="mt-3 text-sm text-slate-300">Escolha o serviço e horário para confirmar seu atendimento.</p>

          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-950/30 p-4">
            <p className="text-xs text-slate-400">Serviço selecionado</p>
            <p className="mt-1 text-lg font-bold text-emerald-300">
              {servicoSelecionado ? `${servicoSelecionado.nome} • ${moedaBRL(servicoSelecionado.preco)}` : "-"}
            </p>
            <p className="text-xs text-slate-400">Duração: {servicoSelecionado ? `${servicoSelecionado.duracao} min` : "-"}</p>
            <div className="mt-4 flex gap-3 text-xs text-slate-400">
              <span className="inline-flex items-center gap-2 rounded-full bg-slate-800/40 px-3 py-1">Barbeiros: {lookup.barbeiros.length}</span>
              <span className="inline-flex items-center gap-2 rounded-full bg-slate-800/40 px-3 py-1">Horários: {lookup.horarios_grade.length}</span>
            </div>
          </div>
        </aside>

        {/* Right - Form */}
        <section className="order-1 md:order-2 rounded-2xl bg-white p-6 shadow-lg">
          <form className="space-y-5" onSubmit={onSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Nome</span>
                <input
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300"
                  required
                  value={nomeCliente}
                  onChange={(event) => setNomeCliente(event.target.value)}
                  placeholder="Ex.: João Silva"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Telefone</span>
                <input
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300"
                  required
                  value={telefoneCliente}
                  onChange={(event) => setTelefoneCliente(event.target.value)}
                  placeholder="Ex.: (82) 99999-0000"
                />
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Barbeiro</span>
                <select
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
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
                <span className="mb-1 block text-sm font-medium text-slate-700">Serviço</span>
                <select
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
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
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
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
                <span className="text-sm font-medium text-slate-700">Horários</span>
                <span className="text-xs text-slate-500">Indisponível = X</span>
              </div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
                {lookup.horarios_grade.map((slot) => (
                  <button
                    key={slot.hora}
                    type="button"
                    disabled={!slot.disponivel}
                    onClick={() => setHoraInicio(slot.hora)}
                    className={[
                      "relative rounded-lg border px-3 py-2 text-sm font-semibold transition",
                      slot.disponivel
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                        : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400",
                      horaInicio === slot.hora ? "ring-2 ring-blue-500" : "",
                    ].join(" ")}
                  >
                    <span>{slot.hora}</span>
                    {!slot.disponivel && (
                      <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-lg text-red-500">X</span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</p>}
            {sucesso && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{sucesso}</p>}

            <div className="flex gap-3">
              <button
                className="flex-1 rounded-lg bg-emerald-500 px-4 py-3 text-sm font-bold text-white shadow hover:bg-emerald-600 disabled:opacity-60"
                type="submit"
                disabled={submitting}
              >
                {submitting ? "Agendando..." : "Confirmar Agendamento"}
              </button>
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
                className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Limpar
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
