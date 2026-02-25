import { API_URL } from "./api";
import { getAuthSession } from "./auth";

export type PlanoBarbearia = "basico" | "premium";
export type StatusManualBarbearia = "ativo" | "inativo";
export type StatusAssinaturaBarbearia = "ativo" | "trial" | "bloqueado_atraso" | "inativo";

export type BarbeariaAdmin = {
  id: number;
  nome: string;
  login: string;
  senha: string;
  megaInstanceKey: string;
  megaToken: string;
  whatsappNumber: string;
  plano: PlanoBarbearia;
  statusManual: StatusManualBarbearia;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm: string | null;
  ultimoAcessoEm: string | null;
  pagamentoRecusado: boolean;
  criadoEm: string;
};

type BarbeariaApi = {
  id: number;
  nome: string;
  login: string | null;
  senha: string | null;
  mega_instance_key: string | null;
  mega_token: string | null;
  whatsapp_number: string | null;
  plano: PlanoBarbearia | null;
  status_manual: StatusManualBarbearia | null;
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

function toUi(item: BarbeariaApi): BarbeariaAdmin {
  return {
    id: item.id,
    nome: item.nome,
    login: item.login ?? "",
    senha: item.senha ?? "",
    megaInstanceKey: item.mega_instance_key ?? "",
    megaToken: item.mega_token ?? "",
    whatsappNumber: item.whatsapp_number ?? "",
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

export async function listBarbeariasAdmin(): Promise<BarbeariaAdmin[]> {
  const res = await fetch(`${API_URL}/barbearias/`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  const data = (await parseOrThrow(res, "Falha ao carregar barbearias.")) as BarbeariaApi[];
  return data.map(toUi);
}

export async function createBarbeariaAdmin(payload: {
  nome: string;
  login: string;
  senha: string;
  megaInstanceKey?: string;
  megaToken?: string;
  whatsappNumber?: string;
  plano: PlanoBarbearia;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm?: string | null;
  pagamentoRecusado?: boolean;
}): Promise<BarbeariaAdmin> {
  const res = await fetch(`${API_URL}/barbearias/`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      mega_instance_key: payload.megaInstanceKey?.trim() || null,
      mega_token: payload.megaToken?.trim() || null,
      whatsapp_number: payload.whatsappNumber?.trim() || null,
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

  const data = (await parseOrThrow(res, "Falha ao cadastrar barbearia.")) as BarbeariaApi;
  return toUi(data);
}

export async function updateBarbeariaAdmin(
  id: number,
  payload: {
    nome: string;
    login: string;
    senha: string;
    megaInstanceKey?: string;
    megaToken?: string;
    whatsappNumber?: string;
    plano: PlanoBarbearia;
    statusManual: StatusManualBarbearia;
    vencimentoEm: string;
    trialAtivo: boolean;
    trialFimEm: string | null;
    ultimoAcessoEm: string | null;
    pagamentoRecusado: boolean;
  }
): Promise<BarbeariaAdmin> {
  const res = await fetch(`${API_URL}/barbearias/${id}`, {
    method: "PUT",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      mega_instance_key: payload.megaInstanceKey?.trim() || null,
      mega_token: payload.megaToken?.trim() || null,
      whatsapp_number: payload.whatsappNumber?.trim() || null,
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

  const data = (await parseOrThrow(res, "Falha ao atualizar barbearia.")) as BarbeariaApi;
  return toUi(data);
}

export async function deleteBarbeariaAdmin(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/barbearias/${id}`, {
    method: "DELETE",
    headers: getAdminHeaders(),
  });
  await parseOrThrow(res, "Falha ao excluir barbearia.");
}

export function getStatusAssinaturaBarbearia(item: BarbeariaAdmin): StatusAssinaturaBarbearia {
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
