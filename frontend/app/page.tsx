"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarDays, Clock3, Users, Wrench } from "lucide-react";
import Button from "./components/Button";
import Card from "./components/Card";
import Loading from "./components/Loading";
import StatCard from "./components/StatCard";
import { listAgendamentos, listClientes, listServicos } from "@/services/api";

type DashboardData = {
  totalAgendamentos: number;
  totalClientes: number;
  totalServicos: number;
  agendamentosConfirmados: number;
};

export default function Home() {
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
          agendamentosConfirmados: agendamentos.filter((a) => a.status === "confirmado").length,
        });
      } catch {
        setError("Nao foi possivel carregar os indicadores. Verifique a conexao com a API.");
      } finally {
        setLoading(false);
      }
    };

    carregarResumo();
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="py-8">
        <div className="app-container space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Painel Operacional</h1>
            <p className="mt-1 text-gray-600">
              Visao geral da operacao da barbearia.
            </p>
          </div>

          {loading ? (
            <Loading />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Agendamentos"
                value={data.totalAgendamentos}
                icon={<CalendarDays size={22} />}
                color="blue"
              />
              <StatCard
                label="Confirmados"
                value={data.agendamentosConfirmados}
                icon={<Clock3 size={22} />}
                color="green"
              />
              <StatCard
                label="Clientes"
                value={data.totalClientes}
                icon={<Users size={22} />}
                color="amber"
              />
              <StatCard
                label="Servicos"
                value={data.totalServicos}
                icon={<Wrench size={22} />}
                color="blue"
              />
            </div>
          )}

          {error && (
            <Card>
              <p className="text-sm font-medium text-red-600">{error}</p>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Acessos Rapidos">
              <div className="flex flex-wrap gap-3">
                <Link href="/agenda">
                  <Button>
                    <CalendarDays size={18} />
                    Abrir Agenda
                  </Button>
                </Link>
                <Link href="/gestao">
                  <Button variant="secondary">
                    <Wrench size={18} />
                    Abrir Gestao
                  </Button>
                </Link>
              </div>
            </Card>

            <Card title="Fluxo Recomendado">
              <ol className="list-decimal space-y-2 pl-5 text-sm text-gray-700">
                <li>Verifique os horarios e disponibilidade na agenda.</li>
                <li>Cadastre ou atualize clientes e servicos no modulo de gestao.</li>
                <li>Confirme ou ajuste agendamentos conforme demanda do dia.</li>
              </ol>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}
