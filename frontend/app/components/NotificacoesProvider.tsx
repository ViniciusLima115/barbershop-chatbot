"use client";

import { createContext, useContext } from "react";
import { useNotificacoes, UseNotificacoesReturn } from "@/hooks/useNotificacoes";
import { ToastContainer } from "./ToastNotificacao";

const NotificacoesContext = createContext<UseNotificacoesReturn | null>(null);

export function NotificacoesProvider({ children }: { children: React.ReactNode }) {
  const notif = useNotificacoes();
  return (
    <NotificacoesContext.Provider value={notif}>
      {children}
      <ToastContainer
        toastsNovos={notif.toastsNovos}
        onClose={notif.limparToast}
        onConfirmarPresenca={notif.confirmarPresencaNotif}
      />
    </NotificacoesContext.Provider>
  );
}

export function useNotificacoesContext(): UseNotificacoesReturn {
  const ctx = useContext(NotificacoesContext);
  if (!ctx) throw new Error("useNotificacoesContext must be used inside NotificacoesProvider");
  return ctx;
}
