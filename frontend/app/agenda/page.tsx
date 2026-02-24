"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AgendaGrid, { SelectedAgendamento } from "../components/AgendaGrid";
import { AgendaDiaResponse, getAgendaDia } from "@/services/api";
import Alert from "../components/Alert";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import Card from "../components/Card";
import Modal from "../components/Modal";
import { Calendar, Users, Clock, TrendingUp } from "lucide-react";

function getLocalISODate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function calcularDuracaoEmMinutos(inicio?: string, fim?: string): string {
  if (!inicio || !fim) return "Nao informado";

  const inicioDate = new Date(inicio);
  const fimDate = new Date(fim);
  const diffMs = fimDate.getTime() - inicioDate.getTime();

  if (Number.isNaN(diffMs) || diffMs <= 0) return "Nao informado";

  const minutos = Math.round(diffMs / 60000);
  return `${minutos} min`;
}

export default function AgendaPage() {
  const [selectedDate, setSelectedDate] = useState(getLocalISODate());
  const [data, setData] = useState<AgendaDiaResponse | null>(null);
  const [selected, setSelected] = useState<SelectedAgendamento | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
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
        setIsDetailsOpen(false);
      } catch {
        setData(null);
        setSelected(null);
        setIsDetailsOpen(false);
        setError("Falha ao buscar agenda. Confirme se o backend esta acessivel.");
      } finally {
        setLoading(false);
      }
    };

    carregarAgenda();
  }, [selectedDate]);

  const selectedKey = selected ? `${selected.barbeiroId}-${selected.hora}` : undefined;
  const totalSlots = data ? data.horarios.length * data.barbeiros.length : 0;
  const totalOcupados = data
    ? data.barbeiros.reduce((acc, b) => acc + b.agendamentos.length, 0)
    : 0;
  const totalLivres = Math.max(totalSlots - totalOcupados, 0);
  const taxaOcupacao = totalSlots > 0 ? Math.round((totalOcupados / totalSlots) * 100) : 0;

  const abrirDetalhes = (item: SelectedAgendamento) => {
    setSelected(item);
    setIsDetailsOpen(true);
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="py-8">
        <div className="app-container space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Agenda</h1>
              <p className="mt-1 text-gray-600">
                Visualize e gerencie os agendamentos da barbearia
              </p>
            </div>
            <div className="flex gap-3">
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="input"
              />
              <Link href="/gestao">
                <button className="btn btn-secondary">Ir para Gestao</button>
              </Link>
            </div>
          </div>

          {data && !loading && (
            <div className="grid gap-4 md:grid-cols-4">
              <StatCard
                label="Total de Slots"
                value={totalSlots}
                icon={<Calendar size={24} />}
                color="blue"
              />
              <StatCard
                label="Ocupados"
                value={totalOcupados}
                icon={<Users size={24} />}
                color="green"
              />
              <StatCard
                label="Livres"
                value={totalLivres}
                icon={<Clock size={24} />}
                color="amber"
              />
              <StatCard
                label="Taxa de Ocupacao"
                value={`${taxaOcupacao}%`}
                icon={<TrendingUp size={24} />}
                color="blue"
                trend={taxaOcupacao > 70 ? "up" : "down"}
              />
            </div>
          )}

          {error && (
            <Alert type="error" message={error} onClose={() => setError(null)} />
          )}

          {loading && <Loading />}

          {!loading && !error && data && (
            <Card
              title="Grade de Agendamentos"
              subtitle={`Verde: agendamento confirmado. Data: ${new Date(selectedDate).toLocaleDateString("pt-BR", {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              })}`}
            >
              <AgendaGrid
                data={data}
                selectedKey={selectedKey}
                onSelect={abrirDetalhes}
              />
            </Card>
          )}
        </div>
      </div>

      <Modal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        title="Detalhes"
        size="md"
      >
        {!selected && (
          <p className="text-sm text-gray-600">Selecione um horario para ver os detalhes.</p>
        )}

        {selected && (
          <div className="space-y-4">
            <div className="rounded-lg bg-gray-50 p-4">
              <p className="mb-1 text-xs font-semibold uppercase text-gray-600">Profissional</p>
              <p className="text-lg font-bold text-gray-900">{selected.barbeiroNome}</p>
            </div>

            <div className="rounded-lg bg-gray-50 p-4">
              <p className="mb-1 text-xs font-semibold uppercase text-gray-600">Horario</p>
              <p className="text-lg font-bold text-gray-900">{selected.hora}</p>
            </div>

            {!selected.agendamento && (
              <div className="rounded-lg border border-gray-200 bg-white p-4">
                <p className="mb-1 text-xs font-semibold uppercase text-gray-600">Status</p>
                <p className="font-bold text-gray-900">Livre para novo agendamento</p>
              </div>
            )}

            {selected.agendamento && (
              <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-blue-700">Cliente</p>
                  <p className="font-bold text-gray-900">{selected.agendamento.cliente}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-blue-700">Telefone</p>
                  <p className="font-bold text-gray-900">
                    {selected.agendamento.telefone || "Nao informado"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-blue-700">Servico</p>
                  <p className="font-bold text-gray-900">{selected.agendamento.servico}</p>
                </div>
                <div className="border-t border-blue-200 pt-2">
                  <p className="text-xs font-semibold uppercase text-blue-700">Duracao</p>
                  <p className="font-bold text-gray-900">
                    {calcularDuracaoEmMinutos(
                      selected.agendamento.inicio,
                      selected.agendamento.fim
                    )}
                  </p>
                </div>
                <div className="pt-2">
                  <span
                    className={`inline-block rounded-full px-3 py-1 text-xs font-bold ${
                      selected.agendamento.status === "confirmado"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {selected.agendamento.status === "confirmado" ? "Confirmado" : "Agendado"}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </main>
  );
}
