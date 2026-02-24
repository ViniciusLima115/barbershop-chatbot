import { useSyncExternalStore } from "react";

export const AUTH_STORAGE_KEY = "barbershop_auth_session";
const AUTH_CHANGE_EVENT = "barbershop_auth_changed";

let cachedRawSession: string | null = null;
let cachedParsedSession: AuthSession | null = null;

export type AuthSession = {
  email: string;
  tenantId: string;
  tenantName: string;
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
    if (!parsed.email || !parsed.tenantId || !parsed.tenantName) {
      cachedParsedSession = null;
      return null;
    }

    cachedParsedSession = {
      email: parsed.email,
      tenantId: parsed.tenantId,
      tenantName: parsed.tenantName,
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
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function logout(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
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
