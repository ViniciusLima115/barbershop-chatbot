"use client";

import { useEffect, useRef, useState } from "react";
import { Notificacao } from "@/services/api";
import styles from "./NotificacoesSino.module.css";

const TIPO_CONFIG = {
  novo_agendamento:    { cor: "#3b82f6", labelCor: "#60a5fa", label: "📅 Novo agendamento" },
  agendamento_confirmado: { cor: "#22c55e", labelCor: "#4ade80", label: "✅ Confirmado pelo cliente" },
  pendente_confirmacao:   { cor: "#f59e0b", labelCor: "#fbbf24", label: "⏳ Confirmar presença" },
};

function formatHora(criada_em: string): string {
  const d = new Date(criada_em);
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
}

export function NotificacoesSino({
  notificacoes,
  naoLidas,
  marcarLida,
  marcarTodasLidas,
  confirmarPresencaNotif,
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
      {/* Bell button */}
      <button className={styles.sinoBtn} onClick={() => setAberto((v) => !v)} aria-label="Notificações">
        <span className={styles.sinoIcon}>🔔</span>
        {naoLidas > 0 && <span className={styles.badge}>{naoLidas}</span>}
      </button>

      {/* Dropdown */}
      {aberto && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>
            <span className={styles.dropdownTitle}>Notificações</span>
            <button className={styles.marcarTodasBtn} onClick={marcarTodasLidas}>
              Marcar todas como lidas
            </button>
          </div>

          <div className={styles.lista}>
            {notificacoes.length === 0 && (
              <div className={styles.vazio}>Sem notificações</div>
            )}
            {notificacoes.map((n) => {
              const config = TIPO_CONFIG[n.tipo];
              return (
                <div
                  key={n.id}
                  className={`${styles.item} ${n.lida ? styles.lida : ""}`}
                  style={{ borderLeftColor: config.cor, background: `${config.cor}08` }}
                  onClick={() => { if (!n.lida) marcarLida(n.id); }}
                >
                  <div className={styles.itemHeader}>
                    <div className={styles.itemLabel} style={{ color: config.labelCor }}>
                      {config.label}
                    </div>
                    <span className={styles.itemHora}>{formatHora(n.criada_em)}</span>
                  </div>
                  <div className={`${styles.itemCorpo} ${n.lida ? styles.itemCorpoLido : ""}`}>
                    {n.titulo}
                    {n.corpo && <span className={styles.itemCorpoExtra}> · {n.corpo}</span>}
                  </div>
                  {n.tipo === "pendente_confirmacao" && !n.lida && (
                    <div className={styles.actions}>
                      <button
                        className={styles.btnCompareceu}
                        onClick={(e) => { e.stopPropagation(); handlePresenca(n, true); }}
                      >
                        ✓ Compareceu
                      </button>
                      <button
                        className={styles.btnFaltou}
                        onClick={(e) => { e.stopPropagation(); handlePresenca(n, false); }}
                      >
                        ✕ Faltou
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className={styles.footer}>
            <span className={styles.footerLink}>Ver todas as notificações →</span>
          </div>
        </div>
      )}
    </div>
  );
}
