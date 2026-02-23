export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://34.121.162.107";

export type AgendaSlot = {
  hora: string;
  cliente: string;
  servico: string;
  telefone?: string;
  status?: string;
  inicio?: string;
  fim?: string;
};

export type AgendaBarbeiro = {
  id: number;
  nome: string;
  agendamentos: AgendaSlot[];
};

export type AgendaDiaResponse = {
  data?: string;
  horarios: string[];
  barbeiros: AgendaBarbeiro[];
};

export async function getAgendaDia(data: string): Promise<AgendaDiaResponse> {
  const res = await fetch(`${API_URL}/agenda/dia?data=${data}`, {
  cache: "no-store",
})
;

  if (!res.ok) {
    throw new Error("Falha ao carregar agenda.");
  }

  return res.json();
}

export type Cliente = {
  id: number;
  telefone: string;
  nome: string;
  etapa_atual: string;
  data_criacao: string;
};

export type Servico = {
  id: number;
  nome: string;
  duracao_minutos: number;
  preco: number;
};

export type Barbeiro = {
  id: number;
  nome: string;
};

export type Agendamento = {
  id: number;
  cliente_nome: string;
  telefone: string;
  barbeiro_nome: string;
  servico_nome: string;
  data_hora_inicio: string;
  data_hora_fim: string;
  status: "pendente" | "confirmado" | "cancelado";
};

async function parseOrThrow(res: Response, fallbackMessage: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  throw new Error(body?.detail || fallbackMessage);
}

export async function listClientes(): Promise<Cliente[]> {
  const res = await fetch(`${API_URL}/clientes/`, { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar clientes.");
}

export async function createCliente(payload: {
  nome: string;
  telefone: string;
  etapa_atual?: string;
}): Promise<Cliente> {
  const res = await fetch(`${API_URL}/clientes/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar cliente.");
}

export async function updateCliente(
  id: number,
  payload: { nome: string; telefone: string; etapa_atual?: string }
): Promise<Cliente> {
  const res = await fetch(`${API_URL}/clientes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar cliente.");
}

export async function deleteCliente(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/clientes/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover cliente.");
}

export async function listServicos(): Promise<Servico[]> {
  const res = await fetch(`${API_URL}/servicos/`, { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar serviços.");
}

export async function createServico(payload: {
  nome: string;
  duracao_minutos: number;
  preco: number;
}): Promise<Servico> {
  const res = await fetch(`${API_URL}/servicos/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar serviço.");
}

export async function updateServico(
  id: number,
  payload: { nome: string; duracao_minutos: number; preco: number }
): Promise<Servico> {
  const res = await fetch(`${API_URL}/servicos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar serviço.");
}

export async function deleteServico(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/servicos/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover serviço.");
}

export async function listBarbeiros(): Promise<Barbeiro[]> {
  const res = await fetch(`${API_URL}/barbeiros/`, { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar barbeiros.");
}

export async function listAgendamentos(): Promise<Agendamento[]> {
  const res = await fetch(`${API_URL}/agendamentos/`, { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar agendamentos.");
}

export async function createAgendamento(payload: {
  telefone: string;
  nome_cliente: string;
  barbeiro_id: number;
  servico_id: number;
  data_hora_inicio: string;
  status: "pendente" | "confirmado" | "cancelado";
}): Promise<Agendamento> {
  const res = await fetch(`${API_URL}/agendamentos/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar agendamento.");
}

export async function updateAgendamento(
  id: number,
  payload: {
    barbeiro_id: number;
    servico_id: number;
    data_hora_inicio: string;
    status: "pendente" | "confirmado" | "cancelado";
  }
): Promise<Agendamento> {
  const res = await fetch(`${API_URL}/agendamentos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar agendamento.");
}

export async function deleteAgendamento(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/agendamentos/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover agendamento.");
}
