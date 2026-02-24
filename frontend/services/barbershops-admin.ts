export type PlanoBarbearia = "basico" | "premium";
export type StatusManualBarbearia = "ativo" | "inativo";
export type StatusAssinaturaBarbearia = "ativo" | "trial" | "bloqueado_atraso" | "inativo";

export type BarbeariaAdmin = {
  id: string;
  nome: string;
  login: string;
  senha: string;
  plano: PlanoBarbearia;
  statusManual: StatusManualBarbearia;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm: string | null;
  ultimoAcessoEm: string | null;
  pagamentoRecusado: boolean;
  criadoEm: string;
};

const STORAGE_KEY = "barbershop_admin_records";

function isPlanoValido(value: unknown): value is PlanoBarbearia {
  return value === "basico" || value === "premium";
}

function isStatusManualValido(value: unknown): value is StatusManualBarbearia {
  return value === "ativo" || value === "inativo";
}

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

function normalizeRow(item: Partial<BarbeariaAdmin>): BarbeariaAdmin | null {
  if (!item.id || !item.nome || !item.login || !item.senha || !item.criadoEm) return null;
  if (!isPlanoValido(item.plano)) return null;

  return {
    id: item.id,
    nome: item.nome,
    login: item.login,
    senha: item.senha,
    plano: item.plano,
    statusManual: isStatusManualValido(item.statusManual) ? item.statusManual : "ativo",
    vencimentoEm: item.vencimentoEm ?? plusDays(30),
    trialAtivo: Boolean(item.trialAtivo),
    trialFimEm: item.trialFimEm ?? null,
    ultimoAcessoEm: item.ultimoAcessoEm ?? null,
    pagamentoRecusado: Boolean(item.pagamentoRecusado),
    criadoEm: item.criadoEm,
  };
}

function parseStorage(raw: string | null): BarbeariaAdmin[] {
  if (!raw) return [];

  try {
    const data = JSON.parse(raw) as unknown;
    if (!Array.isArray(data)) return [];

    return data
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        return normalizeRow(item as Partial<BarbeariaAdmin>);
      })
      .filter((item): item is BarbeariaAdmin => Boolean(item));
  } catch {
    return [];
  }
}

function saveAll(barbearias: BarbeariaAdmin[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(barbearias));
}

export function listBarbeariasAdmin(): BarbeariaAdmin[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return parseStorage(raw).sort((a, b) => b.criadoEm.localeCompare(a.criadoEm));
}

export function createBarbeariaAdmin(payload: {
  nome: string;
  login: string;
  senha: string;
  plano: PlanoBarbearia;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm?: string | null;
  pagamentoRecusado?: boolean;
}): BarbeariaAdmin {
  const current = listBarbeariasAdmin();
  const normalizedLogin = payload.login.trim().toLowerCase();

  const loginExiste = current.some((item) => item.login.trim().toLowerCase() === normalizedLogin);
  if (loginExiste) {
    throw new Error("Ja existe uma barbearia com esse login.");
  }

  const nova: BarbeariaAdmin = {
    id: crypto.randomUUID(),
    nome: payload.nome.trim(),
    login: payload.login.trim(),
    senha: payload.senha,
    plano: payload.plano,
    statusManual: "ativo",
    vencimentoEm: payload.vencimentoEm,
    trialAtivo: payload.trialAtivo,
    trialFimEm: payload.trialAtivo ? payload.trialFimEm ?? null : null,
    ultimoAcessoEm: null,
    pagamentoRecusado: Boolean(payload.pagamentoRecusado),
    criadoEm: new Date().toISOString(),
  };

  saveAll([nova, ...current]);
  return nova;
}

export function updateBarbeariaSenhaAdmin(id: string, novaSenha: string): BarbeariaAdmin {
  const current = listBarbeariasAdmin();
  let updated: BarbeariaAdmin | null = null;

  const next = current.map((item) => {
    if (item.id !== id) return item;
    updated = { ...item, senha: novaSenha };
    return updated;
  });

  if (!updated) {
    throw new Error("Barbearia nao encontrada.");
  }

  saveAll(next);
  return updated;
}

export function updateBarbeariaAdmin(
  id: string,
  payload: {
    nome: string;
    login: string;
    senha: string;
    plano: PlanoBarbearia;
    statusManual: StatusManualBarbearia;
    vencimentoEm: string;
    trialAtivo: boolean;
    trialFimEm: string | null;
    ultimoAcessoEm: string | null;
    pagamentoRecusado: boolean;
  }
): BarbeariaAdmin {
  const current = listBarbeariasAdmin();
  const normalizedLogin = payload.login.trim().toLowerCase();

  const conflitoLogin = current.some(
    (item) => item.id !== id && item.login.trim().toLowerCase() === normalizedLogin
  );
  if (conflitoLogin) {
    throw new Error("Ja existe outra barbearia com esse login.");
  }

  let updated: BarbeariaAdmin | null = null;

  const next = current.map((item) => {
    if (item.id !== id) return item;

    updated = {
      ...item,
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      plano: payload.plano,
      statusManual: payload.statusManual,
      vencimentoEm: payload.vencimentoEm,
      trialAtivo: payload.trialAtivo,
      trialFimEm: payload.trialAtivo ? payload.trialFimEm : null,
      ultimoAcessoEm: payload.ultimoAcessoEm,
      pagamentoRecusado: payload.pagamentoRecusado,
    };

    return updated;
  });

  if (!updated) {
    throw new Error("Barbearia nao encontrada.");
  }

  saveAll(next);
  return updated;
}

export function deleteBarbeariaAdmin(id: string): void {
  const current = listBarbeariasAdmin();
  const next = current.filter((item) => item.id !== id);

  if (next.length === current.length) {
    throw new Error("Barbearia nao encontrada.");
  }

  saveAll(next);
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
