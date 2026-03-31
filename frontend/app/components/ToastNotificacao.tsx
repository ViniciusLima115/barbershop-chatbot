"use client";

import { useEffect } from "react";
import { Notificacao } from "@/services/api";
import styles from "./ToastNotificacao.module.css";

const TIPO_CONFIG = {
  novo_agendamento: { cor: "#3b82f6", labelCor: "#60a5fa", label: "📅 Novo agendamento" },
  agendamento_confirmado: { cor: "#22c55e", labelCor: "#4ade80", label: "✅ Confirmado pelo cliente" },
  pendente_confirmacao: { cor: "#f59e0b", labelCor: "#fbbf24", label: "⏳ Confirmar presença" },
};

interface ToastProps {
  notificacao: Notificacao;
  onClose: (id: number) => void;
  onConfirmarPresenca: (agendamentoId: number, compareceu: boolean) => Promise<void>;
}

export function ToastNotificacao({ notificacao, onClose, onConfirmarPresenca }: ToastProps) {
  const config = TIPO_CONFIG[notificacao.tipo];
  const isPendente = notificacao.tipo === "pendente_confirmacao";

  useEffect(() => {
    if (!isPendente) {
      const t = setTimeout(() => onClose(notificacao.id), 5000);
      return () => clearTimeout(t);
    }
  }, [isPendente, notificacao.id, onClose]);

  async function handlePresenca(compareceu: boolean) {
    if (notificacao.agendamento_id != null) {
      await onConfirmarPresenca(notificacao.agendamento_id, compareceu);
    }
    onClose(notificacao.id);
  }

  return (
    <div
      className={styles.toast}
      style={{ borderLeftColor: config.cor }}
    >
      <div className={styles.header}>
        <span className={styles.label} style={{ color: config.labelCor }}>
          {config.label}
        </span>
        <button className={styles.closeBtn} onClick={() => onClose(notificacao.id)}>
          ✕
        </button>
      </div>
      <div className={styles.titulo}>{notificacao.titulo}</div>
      {notificacao.corpo && <div className={styles.corpo}>{notificacao.corpo}</div>}
      {isPendente && (
        <div className={styles.actions}>
          <button className={styles.btnCompareceu} onClick={() => handlePresenca(true)}>
            ✓ Compareceu
          </button>
          <button className={styles.btnFaltou} onClick={() => handlePresenca(false)}>
            ✕ Faltou
          </button>
        </div>
      )}
    </div>
  );
}

interface ContainerProps {
  toastsNovos: Notificacao[];
  onClose: (id: number) => void;
  onConfirmarPresenca: (agendamentoId: number, compareceu: boolean) => Promise<void>;
}

export function ToastContainer({ toastsNovos, onClose, onConfirmarPresenca }: ContainerProps) {
  if (toastsNovos.length === 0) return null;
  return (
    <div className={styles.container}>
      {toastsNovos.map((n) => (
        <ToastNotificacao
          key={n.id}
          notificacao={n}
          onClose={onClose}
          onConfirmarPresenca={onConfirmarPresenca}
        />
      ))}
    </div>
  );
}
