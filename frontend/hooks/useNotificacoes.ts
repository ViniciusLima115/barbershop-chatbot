"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  confirmarPresenca,
  listNotificacoes,
  marcarNotificacaoLida,
  marcarTodasNotificacoesLidas,
  Notificacao,
} from "@/services/api";

const POLL_INTERVAL_MS = 15_000;

export interface UseNotificacoesReturn {
  notificacoes: Notificacao[];
  naoLidas: number;
  toastsNovos: Notificacao[];          // notificações novas a exibir como toast
  marcarLida: (id: number) => Promise<void>;
  marcarTodasLidas: () => Promise<void>;
  confirmarPresencaNotif: (agendamentoId: number, compareceu: boolean) => Promise<void>;
  limparToast: (id: number) => void;   // remove toast da fila
}

export function useNotificacoes(): UseNotificacoesReturn {
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [toastsNovos, setToastsNovos] = useState<Notificacao[]>([]);
  const seenIds = useRef<Set<number>>(new Set());

  const fetchNotificacoes = useCallback(async () => {
    try {
      const data = await listNotificacoes(false, 30);
      setNotificacoes(data);
      // Detect new unseen notifications → add to toasts queue
      const novas = data.filter((n) => !seenIds.current.has(n.id));
      if (novas.length > 0) {
        seenIds.current = new Set([...seenIds.current, ...novas.map((n) => n.id)]);
        setToastsNovos((prev) => {
          // max 3 toasts: keep newest 3
          const merged = [...prev, ...novas];
          return merged.slice(-3);
        });
      }
    } catch {
      // silently ignore polling errors
    }
  }, []);

  useEffect(() => {
    fetchNotificacoes();
    const interval = setInterval(fetchNotificacoes, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchNotificacoes]);

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

  const confirmarPresencaNotif = useCallback(
    async (agendamentoId: number, compareceu: boolean) => {
      await confirmarPresenca(agendamentoId, compareceu);
      // refresh to reflect new status
      await fetchNotificacoes();
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
  };
}
