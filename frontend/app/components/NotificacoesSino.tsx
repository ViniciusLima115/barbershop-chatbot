"use client";

import { useEffect, useRef, useState } from "react";
import { Notificacao } from "@/services/api";
import styles from "./NotificacoesSino.module.css";

const TIPO_CONFIG = {
  novo_agendamento: { cor: "#3b82f6", labelCor: "#60a5fa", label: "Novo agendamento" },
  agendamento_confirmado: { cor: "#22c55e", labelCor: "#4ade80", label: "Agendamento confirmado" },
  pendente_confirmacao: { cor: "#f59e0b", labelCor: "#fbbf24", label: "Confirmar presenca" },
  pagamento_aprovado: { cor: "#16a34a", labelCor: "#22c55e", label: "Pagamento aprovado" },
  pagamento_expirado: { cor: "#d97706", labelCor: "#f59e0b", label: "Pagamento expirado" },
  pagamento_falhou: { cor: "#dc2626", labelCor: "#ef4444", label: "Pagamento nao concluido" },
  conta_pagamento_desconectada: {
    cor: "#7c3aed",
    labelCor: "#8b5cf6",
    label: "Conta Mercado Pago desconectada",
  },
} as const;

function formatHora(criadaEm: string): string {
  const d = new Date(criadaEm);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86_400_000);
  const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (itemDay.getTime() === today.getTime()) {
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }
  if (itemDay.getTime() === yesterday.getTime()) return "ontem";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

interface NotificacoesSinoProps {
  notificacoes: Notificacao[];
  naoLidas: number;
  marcarLida: (id: number) => Promise<void>;
  marcarTodasLidas: () => Promise<void>;
  confirmarPresencaNotif: (agendamentoId: number, compareceu: boolean) => Promise<void>;
  marcarNovoAgendamentoLido: () => Promise<void>;
}

export function NotificacoesSino({
  notificacoes,
  naoLidas,
  marcarLida,
  marcarTodasLidas,
  confirmarPresencaNotif,
  marcarNovoAgendamentoLido,
}: NotificacoesSinoProps) {
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setAberto(false);
      }
    }
    if (aberto) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [aberto]);

  async function handlePresenca(n: Notificacao, compareceu: boolean) {
    if (n.agendamento_id != null) {
      await confirmarPresencaNotif(n.agendamento_id, compareceu);
    }
  }

  return (
    <div className={styles.wrapper} ref={ref}>
<<<<<<< HEAD
      {/* Bell button */}
      <button
        className={styles.sinoBtn}
        onClick={() => {
          setAberto((v) => {
            if (!v) marcarNovoAgendamentoLido();
            return !v;
          });
        }}
        aria-label="Notificações"
      >
        <span className={styles.sinoIcon}>🔔</span>
=======
      <button className={styles.sinoBtn} onClick={() => setAberto((v) => !v)} aria-label="Notificacoes">
        <span className={styles.sinoIcon}>!</span>
>>>>>>> d1b47bb (add-mercadoPago)
        {naoLidas > 0 && <span className={styles.badge}>{naoLidas}</span>}
      </button>

      {aberto && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>
            <span className={styles.dropdownTitle}>Notificacoes</span>
            <button className={styles.marcarTodasBtn} onClick={marcarTodasLidas}>
              Marcar todas como lidas
            </button>
          </div>

          <div className={styles.lista}>
            {notificacoes.length === 0 && <div className={styles.vazio}>Sem notificacoes</div>}
            {notificacoes.map((n) => {
              const config =
                TIPO_CONFIG[n.tipo] ?? {
                  cor: "#64748b",
                  labelCor: "#94a3b8",
                  label: "Notificacao",
                };
              return (
                <div
                  key={n.id}
                  className={`${styles.item} ${n.lida ? styles.lida : ""}`}
                  style={{ borderLeftColor: config.cor, background: `${config.cor}08` }}
                  onClick={() => {
                    if (!n.lida) void marcarLida(n.id);
                  }}
                >
                  <div className={styles.itemHeader}>
                    <div className={styles.itemLabel} style={{ color: config.labelCor }}>
                      {config.label}
                    </div>
                    <span className={styles.itemHora}>{formatHora(n.criada_em)}</span>
                  </div>
                  <div className={`${styles.itemCorpo} ${n.lida ? styles.itemCorpoLido : ""}`}>
                    {n.titulo}
                    {n.corpo && <span className={styles.itemCorpoExtra}> - {n.corpo}</span>}
                  </div>
                  {n.tipo === "pendente_confirmacao" && !n.lida && (
                    <div className={styles.actions}>
                      <button
                        className={styles.btnCompareceu}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePresenca(n, true);
                        }}
                      >
                        Compareceu
                      </button>
                      <button
                        className={styles.btnFaltou}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePresenca(n, false);
                        }}
                      >
                        Faltou
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className={styles.footer}>
            <span className={styles.footerLink}>Atualize para ver novos eventos</span>
          </div>
        </div>
      )}
    </div>
  );
}
