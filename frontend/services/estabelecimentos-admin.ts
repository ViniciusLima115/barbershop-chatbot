import { API_URL } from "./api";
import { getAuthSession } from "./auth";

export type PlanoEstabelecimento = "basico" | "premium";
export type StatusManualEstabelecimento = "ativo" | "inativo";
export type StatusAssinaturaEstabelecimento = "ativo" | "trial" | "bloqueado_atraso" | "inativo";

export type EstabelecimentoAdmin = {
  id: number;
  nome: string;
  login: string;
  senha: string;
  plano: PlanoEstabelecimento;
  statusManual: StatusManualEstabelecimento;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm: string | null;
  ultimoAcessoEm: string | null;
  pagamentoRecusado: boolean;
  criadoEm: string;
};

// Backward compat aliases
export type BarbeariaAdmin = EstabelecimentoAdmin;
export type PlanoBarbearia = PlanoEstabelecimento;
export type StatusManualBarbearia = StatusManualEstabelecimento;
export type StatusAssinaturaBarbearia = StatusAssinaturaEstabelecimento;

type EstabelecimentoApi = {
  id: number;
  nome: string;
  login: string | null;
  senha: string | null;
  plano: PlanoEstabelecimento | null;
  status_manual: StatusManualEstabelecimento | null;
  vencimento_em: string | null;
  trial_ativo: boolean;
  trial_fim_em: string | null;
  ultimo_acesso_em: string | null;
  pagamento_recusado: boolean;
  criado_em: string;
};

function toISODateOnly(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function plusDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return toISODateOnly(date);
}

function toUi(item: EstabelecimentoApi): EstabelecimentoAdmin {
  return {
    id: item.id,
    nome: item.nome,
    login: item.login ?? "",
    senha: item.senha ?? "",
    plano: item.plano ?? "basico",
    statusManual: item.status_manual ?? "ativo",
    vencimentoEm: item.vencimento_em ?? plusDays(30),
    trialAtivo: Boolean(item.trial_ativo),
    trialFimEm: item.trial_fim_em,
    ultimoAcessoEm: item.ultimo_acesso_em,
    pagamentoRecusado: Boolean(item.pagamento_recusado),
    criadoEm: item.criado_em,
  };
}

async function parseOrThrow(res: Response, fallback: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  throw new Error(body?.detail || fallback);
}

function getAdminHeaders(contentTypeJson: boolean = false): HeadersInit {
  const token = getAuthSession()?.accessToken;
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (contentTypeJson) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

export async function listEstabelecimentosAdmin(): Promise<EstabelecimentoAdmin[]> {
  const res = await fetch(`${API_URL}/estabelecimentos/`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  const data = (await parseOrThrow(res, "Falha ao carregar estabelecimentos.")) as EstabelecimentoApi[];
  return data.map(toUi);
}

// Backward compat alias
export const listBarbeariasAdmin = listEstabelecimentosAdmin;

export async function createEstabelecimentoAdmin(payload: {
  nome: string;
  login: string;
  senha: string;
  plano: PlanoEstabelecimento;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm?: string | null;
  pagamentoRecusado?: boolean;
}): Promise<EstabelecimentoAdmin> {
  const res = await fetch(`${API_URL}/estabelecimentos/`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      plano: payload.plano,
      status_manual: "ativo",
      vencimento_em: payload.vencimentoEm,
      trial_ativo: payload.trialAtivo,
      trial_fim_em: payload.trialAtivo ? payload.trialFimEm ?? null : null,
      ultimo_acesso_em: null,
      pagamento_recusado: Boolean(payload.pagamentoRecusado),
      endereco: "",
    }),
  });

  const data = (await parseOrThrow(res, "Falha ao cadastrar estabelecimento.")) as EstabelecimentoApi;
  return toUi(data);
}

// Backward compat alias
export const createBarbeariaAdmin = createEstabelecimentoAdmin;

export async function updateEstabelecimentoAdmin(
  id: number,
  payload: {
    nome: string;
    login: string;
    senha: string;
    plano: PlanoEstabelecimento;
    statusManual: StatusManualEstabelecimento;
    vencimentoEm: string;
    trialAtivo: boolean;
    trialFimEm: string | null;
    ultimoAcessoEm: string | null;
    pagamentoRecusado: boolean;
  }
): Promise<EstabelecimentoAdmin> {
  const res = await fetch(`${API_URL}/estabelecimentos/${id}`, {
    method: "PUT",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      plano: payload.plano,
      status_manual: payload.statusManual,
      vencimento_em: payload.vencimentoEm,
      trial_ativo: payload.trialAtivo,
      trial_fim_em: payload.trialAtivo ? payload.trialFimEm : null,
      ultimo_acesso_em: payload.ultimoAcessoEm,
      pagamento_recusado: payload.pagamentoRecusado,
      endereco: "",
    }),
  });

  const data = (await parseOrThrow(res, "Falha ao atualizar estabelecimento.")) as EstabelecimentoApi;
  return toUi(data);
}

// Backward compat alias
export const updateBarbeariaAdmin = updateEstabelecimentoAdmin;

export async function deleteEstabelecimentoAdmin(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/estabelecimentos/${id}`, {
    method: "DELETE",
    headers: getAdminHeaders(),
  });
  await parseOrThrow(res, "Falha ao excluir estabelecimento.");
}

// Backward compat alias
export const deleteBarbeariaAdmin = deleteEstabelecimentoAdmin;

export function getStatusAssinaturaEstabelecimento(item: EstabelecimentoAdmin): StatusAssinaturaEstabelecimento {
  if (item.statusManual === "inativo") return "inativo";

  const hoje = toISODateOnly(new Date());
  if (item.trialAtivo && item.trialFimEm && item.trialFimEm >= hoje) {
    return "trial";
  }

  if (item.vencimentoEm < hoje) {
    return "bloqueado_atraso";
  }

  return "ativo";
}

// Backward compat alias
export const getStatusAssinaturaBarbearia = getStatusAssinaturaEstabelecimento;
