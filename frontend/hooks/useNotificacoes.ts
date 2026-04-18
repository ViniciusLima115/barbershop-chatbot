"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  confirmarPresenca,
  listNotificacoes,
  marcarNotificacaoLida,
  marcarTodasNotificacoesLidas,
  Notificacao,
} from "@/services/api";
<<<<<<< HEAD
import { getAuthSession } from "@/services/auth";
=======
import { useAuthSession } from "@/services/auth";
>>>>>>> d1b47bb (add-mercadoPago)

const POLL_INTERVAL_MS = 15_000;

function getSeenStorageKey(): string {
  const tenantId = getAuthSession()?.tenantId ?? "anon";
  return `notif_seen_${tenantId}`;
}

function loadSeenIds(): Set<number> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(getSeenStorageKey());
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as number[]);
  } catch {
    return new Set();
  }
}

function saveSeenIds(ids: Set<number>): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(getSeenStorageKey(), JSON.stringify([...ids]));
  } catch {
    // ignore
  }
}

export interface UseNotificacoesReturn {
  notificacoes: Notificacao[];
  naoLidas: number;
  toastsNovos: Notificacao[];
  marcarLida: (id: number) => Promise<void>;
  marcarTodasLidas: () => Promise<void>;
  confirmarPresencaNotif: (agendamentoId: number, compareceu: boolean) => Promise<void>;
  limparToast: (id: number) => void;
  marcarNovoAgendamentoLido: () => Promise<void>;
}

export function useNotificacoes(): UseNotificacoesReturn {
  const session = useAuthSession();
  const tenantIdValido = Boolean(session?.tenantId && /^\d+$/.test(session.tenantId));
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [toastsNovos, setToastsNovos] = useState<Notificacao[]>([]);
  const seenIds = useRef<Set<number>>(new Set());
  const initialized = useRef(false);

  const fetchNotificacoes = useCallback(async () => {
    if (!tenantIdValido) return;
    try {
      const data = await listNotificacoes(false, 30);
      setNotificacoes(data);

      // Inicializa seenIds do localStorage na primeira chamada
      if (!initialized.current) {
        initialized.current = true;
        seenIds.current = loadSeenIds();
      }

      const novas = data.filter((n) => !seenIds.current.has(n.id));
      if (novas.length > 0) {
        seenIds.current = new Set([...seenIds.current, ...novas.map((n) => n.id)]);
        saveSeenIds(seenIds.current);
        setToastsNovos((prev) => {
          const merged = [...prev, ...novas];
          return merged.slice(-3);
        });
      }
    } catch (err) {
      console.error("[notificacoes] falha ao buscar notificações:", err);
    }
  }, [tenantIdValido]);

  useEffect(() => {
    if (!tenantIdValido) {
      setNotificacoes([]);
      setToastsNovos([]);
      seenIds.current = new Set();
      return;
    }
    fetchNotificacoes();
    const interval = setInterval(fetchNotificacoes, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchNotificacoes, tenantIdValido]);

  const marcarLida = useCallback(async (id: number) => {
    const updated = await marcarNotificacaoLida(id);
    setNotificacoes((prev) =>
      prev.map((n) => (n.id === id ? updated : n))
    );
  }, []);

  const marcarTodasLidas = useCallback(async () => {
    await marcarTodasNotificacoesLidas();
    setNotificacoes((prev) => prev.map((n) => ({ ...n, lida: true })));
  }, []);

  // Marca como lidas todas as notificações de novo_agendamento não lidas (chamado ao abrir o sino)
  const marcarNovoAgendamentoLido = useCallback(async () => {
    const naoLidasNovos = notificacoes.filter(
      (n) => n.tipo === "novo_agendamento" && !n.lida
    );
    await Promise.all(naoLidasNovos.map((n) => marcarNotificacaoLida(n.id)));
    if (naoLidasNovos.length > 0) {
      setNotificacoes((prev) =>
        prev.map((n) =>
          n.tipo === "novo_agendamento" ? { ...n, lida: true } : n
        )
      );
    }
  }, [notificacoes]);

  const confirmarPresencaNotif = useCallback(
    async (agendamentoId: number, compareceu: boolean) => {
      await confirmarPresenca(agendamentoId, compareceu);
      await fetchNotificacoes();
      // Dispara evento para que o dashboard saiba que deve recarregar
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("presenca-confirmada"));
      }
    },
    [fetchNotificacoes]
  );

  const limparToast = useCallback((id: number) => {
    setToastsNovos((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const naoLidas = notificacoes.filter((n) => !n.lida).length;

  return {
    notificacoes,
    naoLidas,
    toastsNovos,
    marcarLida,
    marcarTodasLidas,
    confirmarPresencaNotif,
    limparToast,
    marcarNovoAgendamentoLido,
  };
}
