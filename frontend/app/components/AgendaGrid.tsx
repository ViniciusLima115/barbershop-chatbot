import AgendaCell from "./AgendaCell";
import { AgendaDiaResponse, AgendaSlot } from "@/services/api";

export type SelectedAgendamento = {
  hora: string;
  barbeiroId: number;
  barbeiroNome: string;
  agendamento?: AgendaSlot;
};

type AgendaGridProps = {
  data: AgendaDiaResponse;
  selectedKey?: string;
  onSelect: (item: SelectedAgendamento) => void;
};

export default function AgendaGrid({ data, selectedKey, onSelect }: AgendaGridProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      {data.barbeiros.map((barbeiro) => (
        <section
          key={barbeiro.id}
          className="rounded-xl border border-gray-200 bg-white p-4"
        >
          <h3 className="mb-3 text-base font-bold text-gray-900">{barbeiro.nome}</h3>

          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {data.horarios.map((hora) => {
              const agendamento = barbeiro.agendamentos.find((a) => a.hora === hora);
              const disponivel = barbeiro.horarios.includes(hora);
              const key = `${barbeiro.id}-${hora}`;

              return (
                <AgendaCell
                  key={key}
                  hora={hora}
                  barbeiroNome={barbeiro.nome}
                  agendamento={agendamento}
                  disponivel={disponivel}
                  isSelected={selectedKey === key}
                  onSelect={() => {
                    if (!disponivel && !agendamento) return;
                    onSelect({
                      hora,
                      barbeiroId: barbeiro.id,
                      barbeiroNome: barbeiro.nome,
                      agendamento,
                    });
                  }}
                />
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
