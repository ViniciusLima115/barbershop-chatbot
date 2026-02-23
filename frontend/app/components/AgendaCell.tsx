import { AgendaSlot } from "@/services/api";

type AgendaCellProps = {
  hora: string;
  barbeiroNome: string;
  agendamento?: AgendaSlot;
  isSelected?: boolean;
  onSelect: () => void;
};

export default function AgendaCell({
  hora,
  barbeiroNome,
  agendamento,
  isSelected = false,
  onSelect,
}: AgendaCellProps) {
  const confirmado = agendamento?.status === "confirmado";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`relative aspect-square w-full rounded-lg border p-2 text-left transition-all ${
        confirmado
          ? "border-green-400 bg-green-100 text-green-900 hover:bg-green-200"
          : "border-gray-300 bg-white text-gray-900 hover:border-gray-400 hover:bg-gray-50"
      } ${isSelected ? "ring-2 ring-blue-500 ring-offset-1" : ""} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500`}
      aria-label={`${barbeiroNome} as ${hora}`}
    >
      <div className="flex h-full flex-col justify-between">
        <p className="text-sm font-bold">{hora}</p>

        {agendamento ? (
          <div>
            <p className="line-clamp-2 text-xs font-semibold">
              {agendamento.cliente}
            </p>
            <p className="mt-1 text-[11px] font-medium uppercase opacity-80">
              {confirmado ? "Confirmado" : "Agendado"}
            </p>
          </div>
        ) : (
          <p className="text-[11px] font-medium uppercase text-gray-500">
            Livre
          </p>
        )}
      </div>
    </button>
  );
}
