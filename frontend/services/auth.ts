import { useSyncExternalStore } from "react";
import { API_URL } from "./api";

export type MeResponse = {
  id?: number;
  nome: string;
  plano: string;
  is_admin: boolean;
  tipo_servico?: string | null;
};

export async function fetchMe(accessToken: string): Promise<MeResponse | null> {
  try {
    const resp = await fetch(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}

export const AUTH_STORAGE_KEY = "barbershop_auth_session";
const AUTH_CHANGE_EVENT = "barbershop_auth_changed";

let cachedRawSession: string | null = null;
let cachedParsedSession: AuthSession | null = null;
const TOKEN_COOKIE_NAME = "token";

export type AuthSession = {
  email: string;
  tenantId: string;
  tenantName: string;
  plan: "basico" | "premium";
  accessToken: string;
};

export function getAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (raw === cachedRawSession) {
    return cachedParsedSession;
  }

  cachedRawSession = raw;
  if (!raw) {
    cachedParsedSession = null;
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (!parsed.email || !parsed.tenantId || !parsed.tenantName || !parsed.accessToken) {
      cachedParsedSession = null;
      return null;
    }
    const rawPlan = parsed.plan;
    const plan = rawPlan === "premium" ? "premium" : "basico";

    cachedParsedSession = {
      email: parsed.email,
      tenantId: parsed.tenantId,
      tenantName: parsed.tenantName,
      plan,
      accessToken: parsed.accessToken,
    };
    return cachedParsedSession;
  } catch {
    cachedParsedSession = null;
    return null;
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthSession());
}

export function login(session: AuthSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${TOKEN_COOKIE_NAME}=${encodeURIComponent(session.accessToken)}; Path=/; SameSite=Lax${secure}`;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function logout(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${TOKEN_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};

  const onStorage = () => onStoreChange();
  const onAuthChanged = () => onStoreChange();

  window.addEventListener("storage", onStorage);
  window.addEventListener(AUTH_CHANGE_EVENT, onAuthChanged);

  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(AUTH_CHANGE_EVENT, onAuthChanged);
  };
}

export function useAuthSession(): AuthSession | null {
  return useSyncExternalStore(subscribe, getAuthSession, () => null);
}
