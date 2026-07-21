import { getAuthSession, logout } from "./auth";

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const _rawApiUrl = (process.env.NEXT_PUBLIC_API_URL?.trim() || DEFAULT_API_URL).replace(/\/+$/, "");
// Força HTTPS apenas quando não for localhost/127.0.0.1 (evita quebrar dev local)
function resolveApiUrl(): string {
  const normalized = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(_rawApiUrl)
    ? _rawApiUrl
    : _rawApiUrl.replace(/^http:\/\//i, "https://");

  if (typeof window === "undefined") return normalized;

  try {
    const apiUrl = new URL(normalized);
    const browserHost = window.location.hostname;
    const loopbackHosts = new Set(["localhost", "127.0.0.1"]);
    if (loopbackHosts.has(apiUrl.hostname) && loopbackHosts.has(browserHost)) {
      apiUrl.hostname = browserHost;
      return apiUrl.toString().replace(/\/$/, "");
    }
  } catch {
    return normalized;
  }

  return normalized;
}

export const API_URL = resolveApiUrl();

export type AgendaSlot = {
  hora: string;
  cliente: string;
  servico: string;
  telefone?: string;
  status?: string;
  payment_status?: string;
  payment_amount?: number | null;
  payment_method?: string | null;
  inicio?: string;
  fim?: string;
};

export type AgendaBarbeiro = {
  id: number;
  nome: string;
  horarios: string[];
  agendamentos: AgendaSlot[];
};

/** Alias genérico para AgendaBarbeiro */
export type AgendaProfissional = AgendaBarbeiro;

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
  pagamento_adiantado_obrigatorio?: boolean;
  advance_payment_type?: "full" | "signal" | null;
  advance_payment_amount?: number | null;
  payment_description_override?: string | null;
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
  cliente_email?: string | null;
  barbeiro_nome: string;
  servico_nome: string;
  data_hora_inicio: string;
  data_hora_fim: string;
  status:
    | "pending_payment"
    | "pendente"
    | "confirmado"
    | "payment_review_required"
    | "cancelado"
    | "failed"
    | "reagendamento_solicitado"
    | "compareceu"
    | "no_show"
    | "expired";
  payment_status?: "not_required" | "pending" | "approved" | "rejected" | "cancelled" | "refunded" | "charged_back" | "expired";
  payment_required?: boolean;
  payment_amount?: number | null;
  payment_type?: "full" | "signal" | null;
};

export type TipoNotificacao =
  | "novo_agendamento"
  | "agendamento_confirmado"
  | "pendente_confirmacao"
  | "pagamento_aprovado"
  | "pagamento_expirado"
  | "pagamento_falhou"
  | "conta_pagamento_desconectada";

export type Notificacao = {
  id: number;
  agendamento_id: number | null;
  tipo: TipoNotificacao;
  titulo: string;
  corpo: string | null;
  lida: boolean;
  criada_em: string;
  lida_em: string | null;
};

export type LoginResponse = {
  is_admin: boolean;
  tenant_id: number | null;
  tenant_name: string | null;
  plano: "basico" | "premium" | null;
  access_token?: string | null;
  token_type: "bearer";
  mfa_required?: boolean;
  mfa_challenge?: string | null;
  mfa_setup_required?: boolean;
};

export type AdminMfaStatus = {
  enabled: boolean;
  recovery_codes_remaining: number;
};

export type AdminMfaSetup = {
  manual_key: string;
  otpauth_uri: string;
  qr_code_data_url: string;
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
  pagamento_adiantado_obrigatorio?: boolean;
  pagamento_adiantado_obrigatorio_efetivo?: boolean;
  advance_payment_type?: "full" | "signal" | null;
  advance_payment_amount?: number | null;
};

export type PublicHorarioGrade = {
  hora: string;
  disponivel: boolean;
};

export type PublicLookupResponse = {
  estabelecimento_id: number;
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
  estabelecimento_id: number;
  slug: string;
  cliente_nome: string;
  cliente_telefone: string;
  cliente_email?: string | null;
  barbeiro_id: number;
  servico_id: number;
  data_hora_inicio: string;
  data_hora_fim: string;
  status: string;
  confirmation_token: string;
  lembretes_agendados: number;
};

export type PublicAgendamentoTokenResponse = {
  id: number;
  estabelecimento_id: number;
  slug?: string | null;
  confirmation_token: string;
  cliente_nome: string;
  cliente_email?: string | null;
  barbeiro_id: number;
  barbeiro_nome: string;
  servico_id: number;
  servico_nome: string;
  data_hora_inicio: string;
  data_hora_fim: string;
  status: "pending_payment" | "pendente" | "confirmado" | "cancelado" | "failed" | "reagendamento_solicitado";
};

export type PublicPaymentInitResponse = {
  agendamento_id: number;
  external_reference: string;
  preference_id: string;
  checkout_url: string;
  amount: number;
  pagamento_status: "pending" | "approved" | "rejected" | "cancelled" | "refunded" | "charged_back" | "expired";
  agendamento_status: "pending_payment" | "pendente" | "confirmado" | "payment_review_required" | "cancelado" | "failed" | "expired";
  expires_at?: string | null;
};

export type PublicPaymentStatusResponse = {
  external_reference: string;
  agendamento_id: number;
  pagamento_status: "pending" | "approved" | "rejected" | "cancelled" | "refunded" | "charged_back" | "expired";
  agendamento_status: "pending_payment" | "pendente" | "confirmado" | "payment_review_required" | "cancelado" | "failed" | "expired";
  amount: number;
};

export type PaymentAccountStatus = {
  connected: boolean;
  provider: string;
  status: "pending" | "active" | "inactive" | "revoked" | "error" | "pending_validation" | "disconnected";
  establishment_id: number;
  environment?: "sandbox" | "production" | null;
  external_account_email_masked?: string | null;
  external_user_id_masked?: string | null;
  last_sync_at?: string | null;
  token_expires_at?: string | null;
  checkout_hold_minutes?: number;
  validation_status?: "valid" | "invalid" | "not_validated" | "error" | null;
  validation_error?: string | null;
};

export type WorkingDayKey = "seg" | "ter" | "qua" | "qui" | "sex" | "sab" | "dom";

export type WorkingHoursDay = {
  ativo: boolean;
  inicio: string;
  fim: string;
};

export type BarbershopWorkingHours = Record<WorkingDayKey, WorkingHoursDay> & {
  intervalo_minutos?: number;
};

function getTenantId(): string | null {
  const tenantId = getAuthSession()?.tenantId ?? null;
  if (!tenantId) return null;
  return /^\d+$/.test(tenantId) ? tenantId : null;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const tenantId = getTenantId();
  const headers = new Headers(init?.headers);

  if (tenantId) {
    headers.set("X-Estabelecimento-Id", tenantId);
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error("Nao foi possivel conectar com a API. Verifique a URL e a disponibilidade do backend.");
  }

  if (res.status === 401) {
    logout();
    if (typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }

  return res;
}

async function parseOrThrow(res: Response, fallbackMessage: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  if (res.status === 429) {
    throw new Error("Muitas tentativas em pouco tempo. Aguarde um minuto e tente novamente.");
  }
  throw new Error(body?.detail || body?.error || fallbackMessage);
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
  pagamento_adiantado_obrigatorio?: boolean;
  advance_payment_type?: "full" | "signal" | null;
  advance_payment_amount?: number | null;
  payment_description_override?: string | null;
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
  payload: {
    nome: string;
    duracao_minutos: number;
    preco: number;
    pagamento_adiantado_obrigatorio?: boolean;
    advance_payment_type?: "full" | "signal" | null;
    advance_payment_amount?: number | null;
    payment_description_override?: string | null;
  }
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
  const res = await apiFetch("/profissionais/", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar barbeiros.");
}

export async function createBarbeiro(payload: {
  nome: string;
  horarios_funcionamento?: BarbershopWorkingHours | null;
}): Promise<Barbeiro> {
  const res = await apiFetch("/profissionais/", {
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
  const res = await apiFetch(`/profissionais/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao atualizar barbeiro.");
}

export async function deleteBarbeiro(id: number): Promise<void> {
  const res = await apiFetch(`/profissionais/${id}`, { method: "DELETE" });
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
  cliente_email?: string;
  barbeiro_id: number;
  servico_id: number;
  data_hora_inicio: string;
  status:
    | "pending_payment"
    | "pendente"
    | "confirmado"
    | "cancelado"
    | "reagendamento_solicitado"
    | "compareceu"
    | "no_show"
    | "failed"
    | "expired";
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
    cliente_email?: string;
    status:
      | "pending_payment"
      | "pendente"
      | "confirmado"
      | "payment_review_required"
      | "cancelado"
      | "reagendamento_solicitado"
      | "compareceu"
      | "no_show"
      | "failed"
      | "expired";
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
  const res = await apiFetch("/estabelecimentos/me/funcionamento", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar horarios de funcionamento.");
}

export async function updateBarbershopWorkingHours(
  payload: BarbershopWorkingHours
): Promise<BarbershopWorkingHours> {
  const res = await apiFetch("/estabelecimentos/me/funcionamento", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao salvar horarios de funcionamento.");
}

export async function getMercadoPagoStatus(): Promise<PaymentAccountStatus> {
  const res = await apiFetch("/integrations/mercadopago/status", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar status da conta Mercado Pago.");
}

export async function deleteAgendamento(id: number): Promise<void> {
  const res = await apiFetch(`/agendamentos/${id}`, { method: "DELETE" });
  await parseOrThrow(res, "Falha ao remover agendamento.");
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

export async function verificarMfaAdmin(payload: {
  challenge: string;
  code: string;
}): Promise<LoginResponse> {
  const res = await apiFetch("/auth/admin/mfa/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao validar o codigo de seguranca.");
}

export async function obterStatusMfaAdmin(): Promise<AdminMfaStatus> {
  const res = await apiFetch("/auth/admin/mfa/status", { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar a seguranca da conta.");
}

export async function iniciarMfaAdmin(senha: string): Promise<AdminMfaSetup> {
  const res = await apiFetch("/auth/admin/mfa/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ senha }),
  });
  return parseOrThrow(res, "Falha ao iniciar a configuracao do autenticador.");
}

export async function confirmarMfaAdmin(code: string): Promise<{ recovery_codes: string[] }> {
  const res = await apiFetch("/auth/admin/mfa/setup/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  return parseOrThrow(res, "Falha ao confirmar o autenticador.");
}

export async function desativarMfaAdmin(payload: { senha: string; code: string }): Promise<void> {
  const res = await apiFetch("/auth/admin/mfa/disable", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await parseOrThrow(res, "Falha ao desativar a verificacao em duas etapas.");
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

  const res = await fetch(`${API_URL}/public/estabelecimento/${params.slug}${suffix}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar disponibilidade publica.");
}

export async function lookupPublicBarbershopById(params: {
  estabelecimento_id: number;
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

  const res = await fetch(`${API_URL}/public/estabelecimento-id/${params.estabelecimento_id}${suffix}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar disponibilidade publica.");
}

export async function listPublicServicos(barbeariaId: number): Promise<PublicServico[]> {
  const res = await fetch(`${API_URL}/public/servicos?estabelecimento_id=${barbeariaId}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar servicos publicos.");
}

export async function listPublicBarbeiros(barbeariaId: number): Promise<PublicBarbeiro[]> {
  const res = await fetch(`${API_URL}/public/barbeiros?estabelecimento_id=${barbeariaId}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar barbeiros publicos.");
}

export async function listPublicHorarios(params: {
  estabelecimento_id: number;
  barbeiro_id: number;
  servico_id: number;
  data: string;
}): Promise<{ horarios_disponiveis: string[]; horarios_grade: PublicHorarioGrade[] }> {
  const query = new URLSearchParams({
    estabelecimento_id: String(params.estabelecimento_id),
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
  estabelecimento_id?: number;
  cliente_nome: string;
  cliente_telefone: string;
  cliente_email?: string;
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

export async function startPublicBookingPayment(payload: {
  slug?: string;
  estabelecimento_id?: number;
  cliente_nome: string;
  cliente_telefone: string;
  cliente_email?: string;
  barbeiro_id: number;
  servico_id: number;
  data: string;
  hora_inicio: string;
}): Promise<PublicPaymentInitResponse> {
  const res = await fetch(`${API_URL}/public/agendamentos/pagamento/iniciar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao iniciar pagamento do agendamento.");
}

export async function getPublicPaymentStatus(externalReference: string): Promise<PublicPaymentStatusResponse> {
  const params = new URLSearchParams({ external_reference: externalReference });
  const res = await fetch(`${API_URL}/public/pagamentos/status?${params.toString()}`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao consultar status do pagamento.");
}

export async function getBookingByToken(token: string): Promise<PublicAgendamentoTokenResponse> {
  const res = await fetch(`${API_URL}/agendamentos/${token}/dados`, {
    cache: "no-store",
  });
  return parseOrThrow(res, "Falha ao carregar dados do agendamento.");
}

export async function confirmBookingByToken(token: string): Promise<PublicAgendamentoTokenResponse> {
  const res = await fetch(`${API_URL}/agendamentos/${token}/confirmar`, {
    method: "POST",
  });
  return parseOrThrow(res, "Falha ao confirmar presenca.");
}

export async function cancelBookingByToken(token: string): Promise<PublicAgendamentoTokenResponse> {
  const res = await fetch(`${API_URL}/agendamentos/${token}/cancelar`, {
    method: "POST",
  });
  return parseOrThrow(res, "Falha ao cancelar agendamento.");
}

export async function requestRescheduleByToken(token: string): Promise<PublicAgendamentoTokenResponse> {
  const res = await fetch(`${API_URL}/agendamentos/${token}/reagendar`, {
    method: "POST",
  });
  return parseOrThrow(res, "Falha ao solicitar reagendamento.");
}

export async function rescheduleBookingByToken(
  token: string,
  data_hora_inicio: string,
): Promise<PublicAgendamentoTokenResponse> {
  const res = await fetch(`${API_URL}/agendamentos/${token}/remarcar`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data_hora_inicio }),
  });
  return parseOrThrow(res, "Falha ao reagendar agendamento.");
}

// ─── DASHBOARD PREMIUM ───────────────────────────────────────────────────────

export type HistoricoMes = {
  mes: string;
  faturamento: number;
  total_agendamentos: number;
};

export type FinanceiroResponse = {
  faturamento_mes_atual: number;
  faturamento_mes_anterior: number;
  variacao_percentual: number | null;
  ticket_medio: number;
  total_agendamentos: number;
  historico_12_meses: HistoricoMes[];
  valor_recebido_hoje?: number;
  agendamentos_pagos?: number;
  taxa_conversao_pagamento?: number | null;
  pagamentos_pendentes?: number;
  pagamentos_expirados?: number;
};

export type ServicoMaisVendido = {
  nome: string;
  preco: number;
  total_vendas: number;
  receita_total: number;
};

export type ServicosMaisVendidosResponse = {
  servicos: ServicoMaisVendido[];
};

export type TopCliente = {
  nome: string;
  telefone: string;
  total_visitas: number;
  valor_total_gasto: number;
  ultima_visita: string;
};

export type ClientesResponse = {
  total_clientes: number;
  clientes_novos: number;
  clientes_recorrentes: number;
  taxa_cancelamento: number;
  top_5_clientes: TopCliente[];
};

export async function getDashboardFinanceiro(barbeariaId: string): Promise<FinanceiroResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/financeiro`);
  return parseOrThrow(res, "Falha ao carregar dados financeiros do dashboard.");
}

export async function getDashboardServicos(barbeariaId: string): Promise<ServicosMaisVendidosResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/servicos-mais-vendidos`);
  return parseOrThrow(res, "Falha ao carregar servicos mais vendidos.");
}

export async function getDashboardClientes(barbeariaId: string): Promise<ClientesResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/clientes`);
  return parseOrThrow(res, "Falha ao carregar dados de clientes do dashboard.");
}

// ─── DASHBOARD ANÁLISE ───────────────────────────────────────────────────────

export type ResumoMes = {
  agendamentos: number;
  faturamento: number;
  ticket_medio: number;
  ocupacao: number;
};

export type DiaSemana = {
  dia: string;
  clientes: number;
};

export type HorarioCheio = {
  hora: string;
  atendimentos: number;
};

export type ServicoAnalise = {
  nome: string;
  total: number;
};

export type ClientesAnalise = {
  novos: number;
  recorrentes: number;
  cancelamentos: number;
  no_show: number;
};

export type AnaliseResponse = {
  resumo: ResumoMes;
  semana: DiaSemana[];
  horarios: HorarioCheio[];
  servicos: ServicoAnalise[];
  clientes: ClientesAnalise;
};

export async function getDashboardAnalise(barbeariaId: string): Promise<AnaliseResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/analise`);
  return parseOrThrow(res, "Falha ao carregar dados de análise do dashboard.");
}

// ─── DASHBOARD BÁSICO ──────────────────────────────────────────────────────

export type ResumoBasicoResponse = {
  total_agendamentos_mes: number;
  agendamentos_confirmados_mes: number;
  agendamentos_cancelados_mes: number;
  faturamento_estimado_mes: number;
  total_clientes_unicos_mes: number;
  agendamentos_hoje: number;
  valor_recebido_hoje?: number;
  pagamentos_pendentes?: number;
  pagamentos_expirados?: number;
};

export async function getDashboardResumoBasico(barbeariaId: string): Promise<ResumoBasicoResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/resumo-basico`);
  return parseOrThrow(res, "Falha ao carregar resumo do dashboard.");
}

// ─── NOTIFICAÇÕES ──────────────────────────────────────────────────────────

export async function listNotificacoes(
  apenas_nao_lidas: boolean = false,
  limite: number = 30
): Promise<Notificacao[]> {
  const params = new URLSearchParams({
    apenas_nao_lidas: String(apenas_nao_lidas),
    limite: String(limite),
  });
  const res = await apiFetch(`/notificacoes?${params}`);
  return parseOrThrow(res, "Falha ao listar notificações.");
}

export async function marcarNotificacaoLida(id: number): Promise<Notificacao> {
  const res = await apiFetch(`/notificacoes/${id}/lida`, { method: "PATCH" });
  return parseOrThrow(res, "Falha ao marcar notificação como lida.");
}

export async function marcarTodasNotificacoesLidas(): Promise<{ marcadas: number }> {
  const res = await apiFetch("/notificacoes/marcar-todas-lidas", {
    method: "POST",
  });
  return parseOrThrow(res, "Falha ao marcar todas as notificações como lidas.");
}

export async function confirmarPresenca(
  agendamentoId: number,
  compareceu: boolean
): Promise<void> {
  const res = await apiFetch(`/agendamentos/${agendamentoId}/confirmar-presenca`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ compareceu }),
  });
  await parseOrThrow(res, "Falha ao confirmar presença.");
}
