import { getAuthSession } from "./auth";

const DEFAULT_API_URL = "https://api.virtualbarber.shop";
export const API_URL = (process.env.NEXT_PUBLIC_API_URL?.trim() || DEFAULT_API_URL).replace(/\/+$/, "");

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
  horarios: string[];
  agendamentos: AgendaSlot[];
};

export type AgendaDiaResponse = {
  data?: string;
  horarios: string[];
  barbeiros: AgendaBarbeiro[];
};

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
  ativo?: boolean;
  tempo_por_servico?: Record<string, number> | null;
  horarios_funcionamento?: BarbershopWorkingHours | null;
  barbershop_id?: number;
  barbearia_id?: number;
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

export type AdminCheckResponse = {
  is_admin: boolean;
};

export type LoginResponse = {
  is_admin: boolean;
  tenant_id: number | null;
  tenant_name: string | null;
  plano: "basico" | "premium" | null;
  access_token: string;
  token_type: "bearer";
};

export type PublicBarbeiro = {
  id: number;
  nome: string;
  tempo_por_servico?: Record<string, number> | null;
};

export type PublicServico = {
  id: number;
  nome: string;
  duracao: number;
  preco: number;
};

export type PublicHorarioGrade = {
  hora: string;
  disponivel: boolean;
};

export type PublicLookupResponse = {
  barbearia_id: number;
  nome: string;
  slug: string;
  barbeiros: PublicBarbeiro[];
  servicos: PublicServico[];
  horarios_disponiveis: string[];
  horarios_grade: PublicHorarioGrade[];
};

export type PublicAgendamentoResponse = {
  id: number;
  tenant_id: number;
  barbearia_id: number;
  slug: string;
  cliente_nome: string;
  cliente_telefone: string;
  barbeiro_id: number;
  servico_id: number;
  data_hora_inicio: string;
  data_hora_fim: string;
  status: string;
  lembretes_agendados: number;
};

export type WorkingDayKey = "seg" | "ter" | "qua" | "qui" | "sex" | "sab" | "dom";

export type WorkingHoursDay = {
  ativo: boolean;
  inicio: string;
  fim: string;
};

export type BarbershopWorkingHours = Record<WorkingDayKey, WorkingHoursDay>;

function getAccessToken(): string | null {
  const accessToken = getAuthSession()?.accessToken ?? null;
  return accessToken || null;
}

function getTenantId(): string | null {
  const tenantId = getAuthSession()?.tenantId ?? null;
  if (!tenantId) return null;
  return /^\d+$/.test(tenantId) ? tenantId : null;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const accessToken = getAccessToken();
  const tenantId = getTenantId();
  const headers = new Headers(init?.headers);

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  if (tenantId) {
    headers.set("X-Barbearia-Id", tenantId);
  }

  try {
    return await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new Error("Nao foi possivel conectar com a API. Verifique a URL e a disponibilidade do backend.");
  }
}

async function parseOrThrow(res: Response, fallbackMessage: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  throw new Error(body?.detail || fallbackMessage);
}

export async function getAgendaDia(data: string): Promise<AgendaDiaResponse> {
  const res = await apiFetch(`/agenda/dia?data=${data}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Falha ao carregar agenda.");
  }

  return res.json();
}

export async function listClientes(): Promise<Cliente[]> {
  const res = await apiFetch("/clientes/", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar clientes.");
}

export async function createCliente(payload: {
  nome: string;
  telefone: string;
  etapa_atual?: string;
}): Promise<Cliente> {
  const res = await apiFetch("/clientes/", {
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
  const res = await apiFetch(`/clientes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar cliente.");
}

export async function deleteCliente(id: number): Promise<void> {
  const res = await apiFetch(`/clientes/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover cliente.");
}

export async function listServicos(): Promise<Servico[]> {
  const res = await apiFetch("/servicos/", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar servicos.");
}

export async function createServico(payload: {
  nome: string;
  duracao_minutos: number;
  preco: number;
}): Promise<Servico> {
  const res = await apiFetch("/servicos/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar servico.");
}

export async function updateServico(
  id: number,
  payload: { nome: string; duracao_minutos: number; preco: number }
): Promise<Servico> {
  const res = await apiFetch(`/servicos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar servico.");
}

export async function deleteServico(id: number): Promise<void> {
  const res = await apiFetch(`/servicos/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover servico.");
}

export async function listBarbeiros(): Promise<Barbeiro[]> {
  const res = await apiFetch("/barbeiros/", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar barbeiros.");
}

export async function createBarbeiro(payload: {
  nome: string;
  horarios_funcionamento?: BarbershopWorkingHours | null;
}): Promise<Barbeiro> {
  const res = await apiFetch("/barbeiros/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar barbeiro.");
}

export async function updateBarbeiro(
  id: number,
  payload: {
    nome: string;
    horarios_funcionamento?: BarbershopWorkingHours | null;
  }
): Promise<Barbeiro> {
  const res = await apiFetch(`/barbeiros/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar barbeiro.");
}

export async function deleteBarbeiro(id: number): Promise<void> {
  const res = await apiFetch(`/barbeiros/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover barbeiro.");
}

export async function listAgendamentos(params?: {
  data?: string;
  barbeiro_id?: number;
}): Promise<Agendamento[]> {
  const search = new URLSearchParams();
  if (params?.data) search.set("data", params.data);
  if (params?.barbeiro_id) search.set("barbeiro_id", String(params.barbeiro_id));
  const suffix = search.toString() ? `?${search.toString()}` : "";
  const res = await apiFetch(`/agendamentos/${suffix}`, { cache: "no-store" });
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
  const res = await apiFetch("/agendamentos/", {
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
  const res = await apiFetch(`/agendamentos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar agendamento.");
}

export function defaultBarbershopWorkingHours(): BarbershopWorkingHours {
  return {
    seg: { ativo: true, inicio: "08:00", fim: "18:00" },
    ter: { ativo: true, inicio: "08:00", fim: "18:00" },
    qua: { ativo: true, inicio: "08:00", fim: "18:00" },
    qui: { ativo: true, inicio: "08:00", fim: "18:00" },
    sex: { ativo: true, inicio: "08:00", fim: "18:00" },
    sab: { ativo: true, inicio: "08:00", fim: "18:00" },
    dom: { ativo: true, inicio: "08:00", fim: "18:00" },
  };
}

export async function getBarbershopWorkingHours(): Promise<BarbershopWorkingHours> {
  const res = await apiFetch("/barbearias/me/funcionamento", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar horarios de funcionamento.");
}

export async function updateBarbershopWorkingHours(
  payload: BarbershopWorkingHours
): Promise<BarbershopWorkingHours> {
  const res = await apiFetch("/barbearias/me/funcionamento", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao salvar horarios de funcionamento.");
}

export async function deleteAgendamento(id: number): Promise<void> {
  const res = await apiFetch(`/agendamentos/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover agendamento.");
}

export async function checkAdminLogin(payload: {
  usuario: string;
  senha: string;
}): Promise<AdminCheckResponse> {
  const res = await apiFetch("/auth/admin-check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseOrThrow(res, "Falha ao validar login.");
}

export async function loginUsuario(payload: {
  usuario: string;
  senha: string;
}): Promise<LoginResponse> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseOrThrow(res, "Falha ao validar login.");
}

export async function lookupPublicBarbershop(params: {
  slug: string;
  data?: string;
  barbeiro_id?: number;
  servico_id?: number;
}): Promise<PublicLookupResponse> {
  const search = new URLSearchParams();
  if (params.data) search.set("data", params.data);
  if (params.barbeiro_id) search.set("barbeiro_id", String(params.barbeiro_id));
  if (params.servico_id) search.set("servico_id", String(params.servico_id));
  const query = search.toString();
  const suffix = query ? `?${query}` : "";

  const res = await fetch(`${API_URL}/public/barbearia/${params.slug}${suffix}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar disponibilidade publica.");
}

export async function lookupPublicBarbershopById(params: {
  barbearia_id: number;
  data?: string;
  barbeiro_id?: number;
  servico_id?: number;
}): Promise<PublicLookupResponse> {
  const search = new URLSearchParams();
  if (params.data) search.set("data", params.data);
  if (params.barbeiro_id) search.set("barbeiro_id", String(params.barbeiro_id));
  if (params.servico_id) search.set("servico_id", String(params.servico_id));
  const query = search.toString();
  const suffix = query ? `?${query}` : "";

  const res = await fetch(`${API_URL}/public/barbearia-id/${params.barbearia_id}${suffix}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar disponibilidade publica.");
}

export async function listPublicServicos(barbeariaId: number): Promise<PublicServico[]> {
  const res = await fetch(`${API_URL}/public/servicos?barbearia_id=${barbeariaId}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar servicos publicos.");
}

export async function listPublicBarbeiros(barbeariaId: number): Promise<PublicBarbeiro[]> {
  const res = await fetch(`${API_URL}/public/barbeiros?barbearia_id=${barbeariaId}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar barbeiros publicos.");
}

export async function listPublicHorarios(params: {
  barbearia_id: number;
  barbeiro_id: number;
  servico_id: number;
  data: string;
}): Promise<{ horarios_disponiveis: string[]; horarios_grade: PublicHorarioGrade[] }> {
  const query = new URLSearchParams({
    barbearia_id: String(params.barbearia_id),
    barbeiro_id: String(params.barbeiro_id),
    servico_id: String(params.servico_id),
    data: params.data,
  });
  const res = await fetch(`${API_URL}/public/horarios-disponiveis?${query.toString()}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar horarios publicos.");
}

export async function createPublicBooking(payload: {
  slug?: string;
  barbearia_id?: number;
  cliente_nome: string;
  cliente_telefone: string;
  barbeiro_id: number;
  servico_id: number;
  data: string;
  hora_inicio: string;
}): Promise<PublicAgendamentoResponse> {
  const res = await fetch(`${API_URL}/public/agendamentos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao criar agendamento publico.");
}
