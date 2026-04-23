"use client";

import { ComponentType, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Agendamento,
  BarbershopWorkingHours,
  Barbeiro,
  Cliente,
  Servico,
  createAgendamento,
  createBarbeiro,
  createCliente,
  createServico,
  defaultBarbershopWorkingHours,
  deleteAgendamento,
  deleteBarbeiro,
  deleteCliente,
  deleteServico,
  getBarbershopWorkingHours,
  getMercadoPagoStatus,
  listAgendamentos,
  listBarbeiros,
  listClientes,
  listServicos,
  type PaymentAccountStatus,
  updateAgendamento,
  updateBarbeiro,
  updateBarbershopWorkingHours,
  updateCliente,
  updateServico,
} from "@/services/api";
import { useAuthSession } from "@/services/auth";
import { useRouter } from "next/navigation";
import {
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Edit2,
  Plus,
  RefreshCw,
  Scissors,
  Trash2,
  Users,
} from "lucide-react";
import styles from "./page.module.css";

type Tab = "agendamentos" | "clientes" | "servicos" | "funcionamento";

const initialCliente = { nome: "", telefone: "" };
const initialServico = {
  nome: "",
  duracao_minutos: 40,
  preco: 40,
  pagamento_adiantado_obrigatorio: false,
  advance_payment_type: "full" as "full" | "signal",
  advance_payment_amount: null as number | null,
  payment_description_override: "",
};
const MAX_BARBEIROS_PREMIUM = 3;
const MAX_BARBEIROS_BASICO = 1;
const tabs: Array<{
  key: Tab;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number }>;
}> = [
  {
    key: "agendamentos",
    label: "Agenda",
    description: "Equipe, agenda e operacao diaria",
    icon: CalendarDays,
  },
  {
    key: "clientes",
    label: "Clientes",
    description: "Base de contatos do estabelecimento",
    icon: Users,
  },
  {
    key: "servicos",
    label: "Servicos",
    description: "Catalogo e duracao dos atendimentos",
    icon: Scissors,
  },
  {
    key: "funcionamento",
    label: "Funcionamento",
    description: "Dias e horarios aceitos na agenda",
    icon: Clock3,
  },
];
const workingDays = [
  { key: "seg", label: "Segunda" },
  { key: "ter", label: "Terca" },
  { key: "qua", label: "Quarta" },
  { key: "qui", label: "Quinta" },
  { key: "sex", label: "Sexta" },
  { key: "sab", label: "Sabado" },
  { key: "dom", label: "Domingo" },
] as const;

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function toBackendDateTime(localValue: string): string {
  return `${localValue}:00`;
}

function toDateTimeLocalInput(value: string): string {
  const normalized = value.trim().replace(" ", "T");
  const [datePart, timePart = ""] = normalized.split("T");
  const hhmm = timePart.slice(0, 5);
  return `${datePart}T${hhmm}`;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function summarizeWorkingHours(funcionamento: BarbershopWorkingHours) {
  const ativos = workingDays.filter((day) => funcionamento[day.key].ativo);
  if (ativos.length === 0) return "Nenhum dia ativo";

  const primeiro = ativos[0];
  const ultimo = ativos[ativos.length - 1];
  const intervalo = `${funcionamento[primeiro.key].inicio} - ${funcionamento[ultimo.key].fim}`;

  if (ativos.length === 1) {
    return `${primeiro.label}: ${funcionamento[primeiro.key].inicio} - ${funcionamento[primeiro.key].fim}`;
  }

  return `${primeiro.label} a ${ultimo.label} · ${intervalo}`;
}

function cloneWorkingHours(source?: BarbershopWorkingHours | null): BarbershopWorkingHours {
  const base = source ?? defaultBarbershopWorkingHours();
  return {
    seg: { ...base.seg },
    ter: { ...base.ter },
    qua: { ...base.qua },
    qui: { ...base.qui },
    sex: { ...base.sex },
    sab: { ...base.sab },
    dom: { ...base.dom },
  };
}

function createBarbeiroForm(source?: BarbershopWorkingHours | null) {
  return {
    nome: "",
    horarios_funcionamento: cloneWorkingHours(source),
  };
}

function getWorkingDayKeyFromDateTime(value: string) {
  if (!value) return null;
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return null;
  return workingDays[target.getDay() === 0 ? 6 : target.getDay() - 1]?.key ?? null;
}

type NoticeTone = "success" | "error" | "warning";

function Notice({
  tone,
  message,
  onClose,
}: {
  tone: NoticeTone;
  message: string;
  onClose?: () => void;
}) {
  return (
    <div
      className={cx(
        styles.notice,
        tone === "success" && styles.noticeSuccess,
        tone === "error" && styles.noticeError,
        tone === "warning" && styles.noticeWarning
      )}
    >
      <div className={styles.noticeIcon}>
        {tone === "success" ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}
      </div>
      <p className={styles.noticeText}>{message}</p>
      {onClose ? (
        <button type="button" onClick={onClose} className={styles.noticeClose} aria-label="Fechar aviso">
          x
        </button>
      ) : null}
    </div>
  );
}

function Panel({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          {eyebrow ? <p className={styles.panelEyebrow}>{eyebrow}</p> : null}
          <h2 className={styles.panelTitle}>{title}</h2>
          {description ? <p className={styles.panelDescription}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.panelActions}>{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function ActionButton({
  children,
  variant = "primary",
  type = "button",
  onClick,
  disabled = false,
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  type?: "button" | "submit" | "reset";
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        styles.actionButton,
        variant === "primary" && styles.actionButtonPrimary,
        variant === "secondary" && styles.actionButtonSecondary,
        variant === "ghost" && styles.actionButtonGhost
      )}
    >
      {children}
    </button>
  );
}

function IconActionButton({
  label,
  tone = "secondary",
  onClick,
  children,
}: {
  label: string;
  tone?: "secondary" | "danger";
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        styles.iconActionButton,
        tone === "secondary" && styles.iconActionButtonSecondary,
        tone === "danger" && styles.iconActionButtonDanger
      )}
      aria-label={label}
      title={label}
    >
      <span className={styles.iconActionButtonGlyph}>{children}</span>
    </button>
  );
}

function Field({
  label,
  required = false,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>
        {label}
        {required ? <span className={styles.requiredMark}>*</span> : null}
      </span>
      {children}
      {hint ? <span className={styles.fieldHint}>{hint}</span> : null}
    </label>
  );
}

function StatusPill({ status }: { status: Agendamento["status"] }) {
  const labelByStatus: Record<string, string> = {
    confirmado: "Confirmado",
    pendente: "Pendente",
    pending_payment: "Aguardando pagamento",
    cancelado: "Cancelado",
    expired: "Expirado",
    no_show: "Nao compareceu",
    compareceu: "Concluido",
    reagendamento_solicitado: "Reagendamento",
    failed: "Falhou",
  };
  const label = labelByStatus[status] ?? status;

  return (
    <span
      className={cx(
        styles.statusPill,
        status === "confirmado" && styles.statusConfirmado,
        (status === "pendente" || status === "pending_payment") && styles.statusPendente,
        (status === "cancelado" || status === "failed" || status === "expired") && styles.statusCancelado
      )}
    >
      {label}
    </span>
  );
}

function PaymentPill({
  paymentStatus,
  required,
}: {
  paymentStatus?: Agendamento["payment_status"];
  required?: boolean;
}) {
  if (!required) {
    return <span className={styles.statusPill}>Nao obrigatorio</span>;
  }

  const value = paymentStatus || "pending";
  const labels: Record<string, string> = {
    pending: "Aguardando",
    approved: "Pago",
    rejected: "Recusado",
    cancelled: "Cancelado",
    refunded: "Estornado",
    expired: "Expirado",
    not_required: "Nao obrigatorio",
  };

  return (
    <span
      className={cx(
        styles.statusPill,
        value === "approved" && styles.statusConfirmado,
        value === "pending" && styles.statusPendente,
        (value === "rejected" || value === "cancelled" || value === "expired") && styles.statusCancelado
      )}
    >
      {labels[value] ?? value}
    </span>
  );
}

function StatCard({
  icon,
  label,
  value,
  helper,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <article className={styles.statCard}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statContent}>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value}</strong>
        <span className={styles.statHelper}>{helper}</span>
      </div>
    </article>
  );
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className={styles.emptyState}>
      <h3 className={styles.emptyTitle}>{title}</h3>
      <p className={styles.emptyDescription}>{description}</p>
      {action ? <div className={styles.emptyAction}>{action}</div> : null}
    </div>
  );
}

function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  size = "md",
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  size?: "md" | "lg";
}) {
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay} role="presentation" onClick={onClose}>
      <div
        className={cx(styles.modalCard, size === "lg" && styles.modalCardLarge)}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.modalHeader}>
          <div>
            <h2 className={styles.modalTitle}>{title}</h2>
            {subtitle ? <p className={styles.modalSubtitle}>{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className={styles.modalClose} aria-label="Fechar">
            x
          </button>
        </div>
        <div className={styles.modalBody}>{children}</div>
      </div>
    </div>
  );
}

export default function GestaoPage() {
  const authSession = useAuthSession();
  const router = useRouter();
  const isPremiumPlan = authSession?.plan === "premium";
  const [tab, setTab] = useState<Tab>("agendamentos");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [showClienteModal, setShowClienteModal] = useState(false);
  const [showServicoModal, setShowServicoModal] = useState(false);
  const [showAgendamentoModal, setShowAgendamentoModal] = useState(false);
  const [showBarbeiroModal, setShowBarbeiroModal] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [barbeiros, setBarbeiros] = useState<Barbeiro[]>([]);
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  const [funcionamento, setFuncionamento] = useState<BarbershopWorkingHours>(
    defaultBarbershopWorkingHours()
  );
  const [savingFuncionamento, setSavingFuncionamento] = useState(false);
  const [intervaloMinutos, setIntervaloMinutos] = useState<number>(30);
  const [paymentAccount, setPaymentAccount] = useState<PaymentAccountStatus | null>(null);

  const [novoCliente, setNovoCliente] = useState(initialCliente);
  const [editClienteId, setEditClienteId] = useState<number | null>(null);

  const [novoServico, setNovoServico] = useState(initialServico);
  const [editServicoId, setEditServicoId] = useState<number | null>(null);
  const [novoBarbeiro, setNovoBarbeiro] = useState(() => createBarbeiroForm());
  const [editBarbeiroId, setEditBarbeiroId] = useState<number | null>(null);

  const [formAgendamento, setFormAgendamento] = useState({
    clienteId: "",
    barbeiroId: "",
    servicoId: "",
    dataHora: "",
    status: "confirmado" as
      | "pending_payment"
      | "pendente"
      | "confirmado"
      | "cancelado"
      | "reagendamento_solicitado"
      | "compareceu"
      | "no_show"
      | "failed"
      | "expired",
  });
  const [editAgendamentoId, setEditAgendamentoId] = useState<number | null>(null);

  const limiteBarbeiros = isPremiumPlan ? MAX_BARBEIROS_PREMIUM : MAX_BARBEIROS_BASICO;
  const limiteBarbeirosAtingido = barbeiros.length >= limiteBarbeiros;

  async function carregarTudo() {
    setLoading(true);
    setError(null);
    try {
      const [cs, ss, bs, ags, workingHours] = await Promise.all([
        listClientes(),
        listServicos(),
        listBarbeiros(),
        listAgendamentos(),
        getBarbershopWorkingHours(),
      ]);
      setClientes(cs);
      setServicos(ss);
      setBarbeiros(bs);
      setAgendamentos(ags);
      setFuncionamento(workingHours);
      setIntervaloMinutos(workingHours.intervalo_minutos ?? 30);
      try {
        const status = await getMercadoPagoStatus();
        setPaymentAccount(status);
      } catch {
        setPaymentAccount(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    carregarTudo();
  }, [authSession?.tenantId]);

  useEffect(() => {
    if (!success) return;
    const timeout = window.setTimeout(() => setSuccess(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [success]);

  const clientesById = useMemo(() => Object.fromEntries(clientes.map((c) => [c.id, c])), [clientes]);
  const funcionamentoResumo = useMemo(() => summarizeWorkingHours(funcionamento), [funcionamento]);
  const proximoAgendamento = useMemo(() => {
    const futuros = agendamentos
      .filter((item) => new Date(item.data_hora_inicio).getTime() >= Date.now())
      .sort(
        (left, right) =>
          new Date(left.data_hora_inicio).getTime() - new Date(right.data_hora_inicio).getTime()
      );
    return futuros[0] ?? null;
  }, [agendamentos]);
  const barbeiroSelecionadoAgendamento = useMemo(
    () => barbeiros.find((item) => String(item.id) === formAgendamento.barbeiroId) ?? null,
    [barbeiros, formAgendamento.barbeiroId]
  );
  const dicaFuncionamentoBarbeiro = useMemo(() => {
    if (!barbeiroSelecionadoAgendamento || !formAgendamento.dataHora) return null;
    const dayKey = getWorkingDayKeyFromDateTime(formAgendamento.dataHora);
    if (!dayKey) return null;

    const dia = workingDays.find((item) => item.key === dayKey);
    const schedule = barbeiroSelecionadoAgendamento.horarios_funcionamento ?? funcionamento;
    const item = schedule[dayKey];
    if (!item.ativo) {
      return `${barbeiroSelecionadoAgendamento.nome} nao atende em ${dia?.label.toLowerCase() ?? "esse dia"}.`;
    }
    return `${barbeiroSelecionadoAgendamento.nome} atende em ${dia?.label.toLowerCase() ?? "esse dia"} das ${item.inicio} as ${item.fim}.`;
  }, [barbeiroSelecionadoAgendamento, formAgendamento.dataHora, funcionamento]);
  const mercadoPagoConectado = Boolean(paymentAccount?.connected && paymentAccount.status === "active");

  const limparMensagens = () => {
    setError(null);
    setSuccess(null);
  };

  function fecharClienteModal() {
    setShowClienteModal(false);
    limparMensagens();
  }

  function fecharServicoModal() {
    setShowServicoModal(false);
    limparMensagens();
  }

  function fecharBarbeiroModal() {
    setShowBarbeiroModal(false);
    limparMensagens();
  }

  function fecharModalAgendamento() {
    setShowAgendamentoModal(false);
    setError(null);
  }

  async function salvarFuncionamento(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    setSavingFuncionamento(true);

    try {
      const atualizado = await updateBarbershopWorkingHours({
        ...funcionamento,
        intervalo_minutos: intervaloMinutos,
      });
      setFuncionamento(atualizado);
      setSuccess("Horarios de funcionamento salvos com sucesso!");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar horarios.");
    } finally {
      setSavingFuncionamento(false);
    }
  }

  async function submitCliente(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    try {
      if (editClienteId) {
        await updateCliente(editClienteId, { ...novoCliente, etapa_atual: "menu" });
        setSuccess("Cliente atualizado com sucesso!");
      } else {
        await createCliente({ ...novoCliente, etapa_atual: "menu" });
        setSuccess("Cliente criado com sucesso!");
      }
      setNovoCliente(initialCliente);
      setEditClienteId(null);
      setShowClienteModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar cliente.");
    }
  }

  function abrirModalCliente(cliente?: Cliente) {
    limparMensagens();
    if (cliente) {
      setEditClienteId(cliente.id);
      setNovoCliente({ nome: cliente.nome, telefone: cliente.telefone });
    } else {
      setEditClienteId(null);
      setNovoCliente(initialCliente);
    }
    setShowClienteModal(true);
  }

  async function submitServico(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    try {
      const exigePagamento = Boolean(novoServico.pagamento_adiantado_obrigatorio);
      const tipoPagamento = exigePagamento ? novoServico.advance_payment_type ?? "full" : null;
      const valorSinal = novoServico.advance_payment_amount;

      if (exigePagamento && tipoPagamento === "signal") {
        const valor = Number(valorSinal ?? 0);
        if (!Number.isFinite(valor) || valor <= 0) {
          setError("Informe um valor de sinal maior que zero.");
          return;
        }
        if (valor > Number(novoServico.preco || 0)) {
          setError("O valor do sinal nao pode ser maior que o preco do servico.");
          return;
        }
      }

      const payloadServico = {
        ...novoServico,
        advance_payment_type: tipoPagamento,
        advance_payment_amount:
          exigePagamento && tipoPagamento === "signal"
            ? Number(novoServico.advance_payment_amount)
            : null,
        payment_description_override: exigePagamento
          ? novoServico.payment_description_override?.trim() || null
          : null,
      };

      if (editServicoId) {
        await updateServico(editServicoId, payloadServico);
        setSuccess("Servico atualizado com sucesso!");
      } else {
        await createServico(payloadServico);
        setSuccess("Servico criado com sucesso!");
      }
      setNovoServico(initialServico);
      setEditServicoId(null);
      setShowServicoModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar servico.");
    }
  }

  function abrirModalServico(servico?: Servico) {
    limparMensagens();
    if (servico) {
      setEditServicoId(servico.id);
      setNovoServico({
        nome: servico.nome,
        duracao_minutos: servico.duracao_minutos,
        preco: servico.preco,
        pagamento_adiantado_obrigatorio: Boolean(servico.pagamento_adiantado_obrigatorio),
        advance_payment_type: servico.advance_payment_type ?? "full",
        advance_payment_amount:
          servico.advance_payment_amount !== undefined && servico.advance_payment_amount !== null
            ? Number(servico.advance_payment_amount)
            : null,
        payment_description_override: servico.payment_description_override ?? "",
      });
    } else {
      setEditServicoId(null);
      setNovoServico(initialServico);
    }
    setShowServicoModal(true);
  }

  async function submitBarbeiro(e: FormEvent) {
    e.preventDefault();
    limparMensagens();

    try {
      if (editBarbeiroId) {
        await updateBarbeiro(editBarbeiroId, novoBarbeiro);
        setSuccess("Barbeiro atualizado com sucesso!");
      } else {
        await createBarbeiro(novoBarbeiro);
        setSuccess("Barbeiro criado com sucesso!");
      }

      setNovoBarbeiro(createBarbeiroForm(funcionamento));
      setEditBarbeiroId(null);
      setShowBarbeiroModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar profissional.");
    }
  }

  function abrirModalBarbeiro(barbeiro?: Barbeiro) {
    limparMensagens();
    if (barbeiro) {
      setEditBarbeiroId(barbeiro.id);
      setNovoBarbeiro({
        nome: barbeiro.nome,
        horarios_funcionamento: cloneWorkingHours(barbeiro.horarios_funcionamento ?? funcionamento),
      });
    } else {
      setEditBarbeiroId(null);
      setNovoBarbeiro(createBarbeiroForm(funcionamento));
    }

    setShowBarbeiroModal(true);
  }

  function abrirModalOuUpgrade() {
    if (!isPremiumPlan && limiteBarbeirosAtingido) {
      setShowUpgradeModal(true);
    } else {
      abrirModalBarbeiro();
    }
  }

  async function submitAgendamento(e: FormEvent) {
    e.preventDefault();
    limparMensagens();

    const cliente = clientesById[Number(formAgendamento.clienteId)];
    if (!cliente) {
      setError("Selecione um cliente valido.");
      return;
    }

    try {
      if (editAgendamentoId) {
        await updateAgendamento(editAgendamentoId, {
          barbeiro_id: Number(formAgendamento.barbeiroId),
          servico_id: Number(formAgendamento.servicoId),
          data_hora_inicio: toBackendDateTime(formAgendamento.dataHora),
          status: formAgendamento.status,
        });
        setSuccess("Agendamento atualizado com sucesso!");
      } else {
        await createAgendamento({
          telefone: cliente.telefone,
          nome_cliente: cliente.nome,
          barbeiro_id: Number(formAgendamento.barbeiroId),
          servico_id: Number(formAgendamento.servicoId),
          data_hora_inicio: toBackendDateTime(formAgendamento.dataHora),
          status: formAgendamento.status,
        });
        setSuccess("Agendamento criado com sucesso!");
      }
      setFormAgendamento({
        clienteId: "",
        barbeiroId: "",
        servicoId: "",
        dataHora: "",
        status: "confirmado",
      });
      setEditAgendamentoId(null);
      setShowAgendamentoModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar agendamento.");
    }
  }

  function abrirModalAgendamento(agendamento?: Agendamento) {
    limparMensagens();
    if (agendamento) {
      const cliente = clientes.find((c) => c.telefone === agendamento.telefone);
      const barbeiro = barbeiros.find((b) => b.nome === agendamento.barbeiro_nome);
      const servico = servicos.find((s) => s.nome === agendamento.servico_nome);
      setEditAgendamentoId(agendamento.id);
      setFormAgendamento({
        clienteId: cliente ? String(cliente.id) : "",
        barbeiroId: barbeiro ? String(barbeiro.id) : "",
        servicoId: servico ? String(servico.id) : "",
        dataHora: toDateTimeLocalInput(agendamento.data_hora_inicio),
        status: agendamento.status,
      });
    } else {
      setEditAgendamentoId(null);
      setFormAgendamento({
        clienteId: "",
        barbeiroId: "",
        servicoId: "",
        dataHora: "",
        status: "confirmado",
      });
    }
    setShowAgendamentoModal(true);
  }

  const deleteClienteHandler = async (id: number) => {
    if (!confirm("Tem certeza que deseja remover este cliente?")) return;
    try {
      limparMensagens();
      await deleteCliente(id);
      setSuccess("Cliente removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover cliente.");
    }
  };

  const deleteServicoHandler = async (id: number) => {
    if (!confirm("Tem certeza que deseja remover este servico?")) return;
    try {
      limparMensagens();
      await deleteServico(id);
      setSuccess("Servico removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover servico.");
    }
  };

  const deleteAgendamentoHandler = async (id: number) => {
    if (!confirm("Tem certeza que deseja remover este agendamento?")) return;
    try {
      limparMensagens();
      await deleteAgendamento(id);
      setSuccess("Agendamento removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover agendamento.");
    }
  };

  const deleteBarbeiroHandler = async (id: number) => {
    if (!confirm("Tem certeza que deseja remover este profissional?")) return;

    try {
      limparMensagens();
      await deleteBarbeiro(id);
      setSuccess("Barbeiro removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover profissional.");
    }
  };

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.hero}>
          <div className={styles.heroContent}>
            <span className={styles.eyebrow}>Painel de gestao</span>
            <h1 className={styles.heroTitle}>{authSession?.tenantName ?? "Gestao do Estabelecimento"}</h1>
            <p className={styles.heroSubtitle}>
              Organize agenda, equipe, servicos e horarios em um painel claro para o dia a dia.
            </p>
            <div className={styles.heroMeta}>
              <span className={styles.metaPill}>
                Plano {isPremiumPlan ? "Premium" : "Basico"}
              </span>
              <span className={styles.metaPill}>{funcionamentoResumo}</span>
              {proximoAgendamento ? (
                <span className={styles.metaPill}>
                  Proximo: {formatDateTime(proximoAgendamento.data_hora_inicio)}
                </span>
              ) : null}
            </div>
          </div>
          <ActionButton variant="secondary" onClick={carregarTudo}>
            <RefreshCw size={16} />
            Atualizar dados
          </ActionButton>
        </header>

        <section className={styles.statsGrid}>
          <StatCard
            icon={<CalendarDays size={20} />}
            label="Agendamentos"
            value={String(agendamentos.length)}
            helper={proximoAgendamento ? "Com proximos horarios cadastrados" : "Nenhum horario futuro"}
          />
          <StatCard
            icon={<Users size={20} />}
            label="Clientes"
            value={String(clientes.length)}
            helper={clientes.length > 0 ? "Base pronta para novos atendimentos" : "Comece criando o primeiro cliente"}
          />
          <StatCard
            icon={<Scissors size={20} />}
            label="Servicos"
            value={String(servicos.length)}
            helper={servicos.length > 0 ? "Catalogo ativo para agendamentos" : "Adicione servicos para liberar a agenda"}
          />
          <StatCard
            icon={<Clock3 size={20} />}
            label="Funcionamento"
            value={`${workingDays.filter((day) => funcionamento[day.key].ativo).length} dias`}
            helper={funcionamentoResumo}
          />
        </section>

        {error ? <Notice tone="error" message={error} onClose={() => setError(null)} /> : null}
        {success ? <Notice tone="success" message={success} onClose={() => setSuccess(null)} /> : null}

        <div className={styles.workspace}>
          <aside className={styles.sidebar}>
            <div className={styles.sidebarIntro}>
              <p className={styles.sidebarEyebrow}>Navegacao</p>
              <h2 className={styles.sidebarTitle}>Escolha a area que voce quer ajustar</h2>
              <p className={styles.sidebarText}>
                Cada aba concentra uma tarefa principal para reduzir clique e evitar erro operacional.
              </p>
            </div>

            <nav className={styles.tabList} aria-label="Abas da gestao">
              {tabs.map((item) => {
                const Icon = item.icon;
                const active = tab === item.key;

                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setTab(item.key)}
                    className={cx(styles.tabButton, active && styles.tabButtonActive)}
                    aria-current={active ? "page" : undefined}
                  >
                    <span className={styles.tabIcon}>
                      <Icon size={18} />
                    </span>
                    <span className={styles.tabCopy}>
                      <span className={styles.tabLabel}>{item.label}</span>
                      <span className={styles.tabDescription}>{item.description}</span>
                    </span>
                  </button>
                );
              })}
            </nav>
          </aside>

          <div className={styles.contentArea}>
            {loading ? (
              <div className={styles.loadingState}>
                <div className={styles.loadingPulse} />
                <p>Carregando painel de gestao...</p>
              </div>
            ) : null}

            {!loading && tab === "agendamentos" ? (
              <div className={styles.sectionStack}>
                <Panel
                  eyebrow="Equipe"
                  title="Profissionais ativos"
                  description="Cadastre quem aparece na agenda e acompanhe o limite do seu plano."
                  actions={
                    <ActionButton variant="primary" onClick={abrirModalOuUpgrade}>
                      <Plus size={16} />
                      Adicionar profissional
                    </ActionButton>
                  }
                >
                  <div className={styles.inlineSummary}>
                    <div className={styles.summaryTile}>
                      <span className={styles.summaryLabel}>Ativos</span>
                      <strong className={styles.summaryValue}>
                        {barbeiros.length} / {limiteBarbeiros}
                      </strong>
                    </div>
                    <div className={styles.summaryTile}>
                      <span className={styles.summaryLabel}>Plano atual</span>
                      <strong className={styles.summaryValue}>{isPremiumPlan ? "Premium" : "Basico"}</strong>
                    </div>
                  </div>

                  {!isPremiumPlan && limiteBarbeirosAtingido ? (
                    <Notice
                      tone="warning"
                      message="Limite do plano basico atingido. Para mais profissionais, faca upgrade para o premium."
                    />
                  ) : null}
                  {isPremiumPlan && limiteBarbeirosAtingido ? (
                    <Notice tone="warning" message="Limite de 3 profissionais ativos atingido no plano premium." />
                  ) : null}

                  {barbeiros.length === 0 ? (
                    <EmptyState
                      title="Nenhum profissional cadastrado"
                      description="Adicione a equipe para liberar criacao de agendamentos com responsavel definido."
                      action={
                        <ActionButton variant="secondary" onClick={abrirModalOuUpgrade}>
                          <Plus size={16} />
                          Criar primeiro profissional
                        </ActionButton>
                      }
                    />
                  ) : (
                    <div className={styles.personList}>
                      {barbeiros.map((barbeiro) => (
                        <article key={barbeiro.id} className={styles.personRow}>
                          <div>
                            <strong className={styles.personName}>{barbeiro.nome}</strong>
                            <p className={styles.personMeta}>
                              Disponibilidade: {summarizeWorkingHours(barbeiro.horarios_funcionamento ?? funcionamento)}
                            </p>
                          </div>
                          <div className={styles.rowActions}>
                            <IconActionButton label="Editar profissional" onClick={() => abrirModalBarbeiro(barbeiro)}>
                              <Edit2 size={16} />
                            </IconActionButton>
                            <IconActionButton
                              label="Remover profissional"
                              tone="danger"
                              onClick={() => deleteBarbeiroHandler(barbeiro.id)}
                            >
                              <Trash2 size={16} />
                            </IconActionButton>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </Panel>

                <Panel
                  eyebrow="Agenda"
                  title="Agendamentos do sistema"
                  description="Crie novos horarios e acompanhe rapidamente o que ja esta reservado."
                  actions={
                    <ActionButton
                      variant="primary"
                      onClick={() => abrirModalAgendamento()}
                      disabled={clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0}
                    >
                      <Plus size={16} />
                      Novo agendamento
                    </ActionButton>
                  }
                >
                  {clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0 ? (
                    <Notice
                      tone="warning"
                      message="Cadastre clientes, servicos e profissionais antes de criar um agendamento."
                    />
                  ) : null}

                  {agendamentos.length === 0 ? (
                    <EmptyState
                      title="Nenhum agendamento cadastrado"
                      description="Depois que a estrutura estiver pronta, seus horarios vao aparecer aqui."
                      action={
                        <ActionButton
                          variant="secondary"
                          onClick={() => abrirModalAgendamento()}
                          disabled={clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0}
                        >
                          <Plus size={16} />
                          Criar primeiro agendamento
                        </ActionButton>
                      }
                    />
                  ) : (
                    <div className={styles.tableWrap}>
                      <table className={styles.dataTable}>
                        <thead>
                          <tr>
                            <th>Cliente</th>
                            <th>Servico</th>
                            <th>Profissional</th>
                            <th>Horario</th>
                            <th>Status</th>
                            <th>Pagamento</th>
                            <th>Valor</th>
                            <th className={styles.actionsColumn}>Acoes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {agendamentos.map((agendamento) => (
                            <tr key={agendamento.id}>
                              <td>
                                <strong>{agendamento.cliente_nome}</strong>
                              </td>
                              <td>{agendamento.servico_nome}</td>
                              <td>{agendamento.barbeiro_nome}</td>
                              <td>{formatDateTime(agendamento.data_hora_inicio)}</td>
                              <td>
                                <StatusPill status={agendamento.status} />
                              </td>
                              <td>
                                <PaymentPill
                                  paymentStatus={agendamento.payment_status}
                                  required={agendamento.payment_required}
                                />
                              </td>
                              <td>
                                {agendamento.payment_required
                                  ? formatCurrency(Number(agendamento.payment_amount || 0))
                                  : "-"}
                              </td>
                              <td className={styles.actionsColumn}>
                                <div className={styles.rowActions}>
                                  <IconActionButton
                                    label="Editar agendamento"
                                    onClick={() => abrirModalAgendamento(agendamento)}
                                  >
                                    <Edit2 size={16} />
                                  </IconActionButton>
                                  <IconActionButton
                                    label="Remover agendamento"
                                    tone="danger"
                                    onClick={() => deleteAgendamentoHandler(agendamento.id)}
                                  >
                                    <Trash2 size={16} />
                                  </IconActionButton>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Panel>
              </div>
            ) : null}

            {!loading && tab === "clientes" ? (
              <Panel
                eyebrow="Relacionamento"
                title="Clientes cadastrados"
                description="Mantenha os contatos organizados para agilizar novos atendimentos e reagendamentos."
                actions={
                  <ActionButton variant="primary" onClick={() => abrirModalCliente()}>
                    <Plus size={16} />
                    Novo cliente
                  </ActionButton>
                }
              >
                {clientes.length === 0 ? (
                  <EmptyState
                    title="Sua base de clientes esta vazia"
                    description="Cadastre o primeiro contato para iniciar o uso interno da agenda."
                    action={
                      <ActionButton variant="secondary" onClick={() => abrirModalCliente()}>
                        <Plus size={16} />
                        Criar primeiro cliente
                      </ActionButton>
                    }
                  />
                ) : (
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}>
                      <thead>
                        <tr>
                          <th>Nome</th>
                          <th>Telefone</th>
                          <th className={styles.actionsColumn}>Acoes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {clientes.map((cliente) => (
                          <tr key={cliente.id}>
                            <td>
                              <strong>{cliente.nome}</strong>
                            </td>
                            <td>{cliente.telefone}</td>
                            <td className={styles.actionsColumn}>
                              <div className={styles.rowActions}>
                                <IconActionButton label="Editar cliente" onClick={() => abrirModalCliente(cliente)}>
                                  <Edit2 size={16} />
                                </IconActionButton>
                                <IconActionButton
                                  label="Remover cliente"
                                  tone="danger"
                                  onClick={() => deleteClienteHandler(cliente.id)}
                                >
                                  <Trash2 size={16} />
                                </IconActionButton>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            ) : null}

            {!loading && tab === "servicos" ? (
              <Panel
                eyebrow="Catalogo"
                title="Servicos disponiveis"
                description="Defina nome, duracao e valor para refletir corretamente no agendamento."
                actions={
                  <ActionButton variant="primary" onClick={() => abrirModalServico()}>
                    <Plus size={16} />
                    Novo servico
                  </ActionButton>
                }
              >
                {!mercadoPagoConectado ? (
                  <Notice
                    tone="warning"
                    message="Este estabelecimento ainda nao possui conta de pagamento configurada pela administracao. O pagamento online nao ficara disponivel ate essa configuracao ser feita."
                  />
                ) : null}
                {servicos.length === 0 ? (
                  <EmptyState
                    title="Nenhum servico cadastrado"
                    description="Crie os servicos para habilitar a escolha correta no momento de agendar."
                    action={
                      <ActionButton variant="secondary" onClick={() => abrirModalServico()}>
                        <Plus size={16} />
                        Criar primeiro servico
                      </ActionButton>
                    }
                  />
                ) : (
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}>
                      <thead>
                        <tr>
                          <th>Nome</th>
                          <th>Duracao</th>
                          <th>Preco</th>
                          <th>Pagamento adiantado</th>
                          <th>Tipo</th>
                          <th>Valor online</th>
                          <th className={styles.actionsColumn}>Acoes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {servicos.map((servico) => (
                          <tr key={servico.id}>
                            <td>
                              <strong>{servico.nome}</strong>
                            </td>
                            <td>{servico.duracao_minutos} min</td>
                            <td>{formatCurrency(servico.preco)}</td>
                            <td>{servico.pagamento_adiantado_obrigatorio ? "Obrigatorio" : "Nao"}</td>
                            <td>
                              {servico.pagamento_adiantado_obrigatorio
                                ? servico.advance_payment_type === "signal"
                                  ? "Sinal"
                                  : "Valor total"
                                : "-"}
                            </td>
                            <td>
                              {servico.pagamento_adiantado_obrigatorio
                                ? formatCurrency(
                                    servico.advance_payment_type === "signal"
                                      ? Number(servico.advance_payment_amount || 0)
                                      : servico.preco
                                  )
                                : "-"}
                            </td>
                            <td className={styles.actionsColumn}>
                              <div className={styles.rowActions}>
                                <IconActionButton label="Editar servico" onClick={() => abrirModalServico(servico)}>
                                  <Edit2 size={16} />
                                </IconActionButton>
                                <IconActionButton
                                  label="Remover servico"
                                  tone="danger"
                                  onClick={() => deleteServicoHandler(servico.id)}
                                >
                                  <Trash2 size={16} />
                                </IconActionButton>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            ) : null}

            {!loading && tab === "funcionamento" ? (
              <div className={styles.sectionStack}>
                <Panel
                  eyebrow="Resumo"
                  title="Regras da agenda"
                  description="Esses horarios definem o que o sistema aceita nos agendamentos publicos e internos."
                >
                  <div className={styles.inlineSummary}>
                    <div className={styles.summaryTile}>
                      <span className={styles.summaryLabel}>Dias ativos</span>
                      <strong className={styles.summaryValue}>
                        {workingDays.filter((day) => funcionamento[day.key].ativo).length}
                      </strong>
                    </div>
                    <div className={styles.summaryTile}>
                      <span className={styles.summaryLabel}>Resumo rapido</span>
                      <strong className={styles.summaryValue}>{funcionamentoResumo}</strong>
                    </div>
                  </div>
                </Panel>

                <Panel
                  eyebrow="Configuracao"
                  title="Funcionamento do estabelecimento"
                  description="Ative cada dia de trabalho e defina a janela de horarios em que a agenda pode aceitar reservas."
                >
                  <form onSubmit={salvarFuncionamento} className={styles.workingForm}>
                    <Field
                      label="Intervalo entre horários (minutos)"
                      hint="Define o espaçamento entre os slots disponíveis. Ex: 30 min gera 09:00, 09:30, 10:00..."
                    >
                      <input
                        type="number"
                        min={5}
                        max={120}
                        step={5}
                        value={intervaloMinutos}
                        onChange={(e) => setIntervaloMinutos(Number(e.target.value))}
                        className={styles.input}
                      />
                    </Field>
                    <div className={styles.workingDaysGrid}>
                      {workingDays.map((day) => {
                        const item = funcionamento[day.key];

                        return (
                          <article key={day.key} className={styles.workingCard}>
                            <div className={styles.workingCardHeader}>
                              <div>
                                <h3 className={styles.workingDayTitle}>{day.label}</h3>
                                <p className={styles.workingDayMeta}>
                                  {item.ativo ? "Aceitando horarios" : "Dia bloqueado"}
                                </p>
                              </div>
                              <label className={styles.switchField}>
                                <input
                                  type="checkbox"
                                  checked={item.ativo}
                                  onChange={(e) =>
                                    setFuncionamento((prev) => ({
                                      ...prev,
                                      [day.key]: { ...prev[day.key], ativo: e.target.checked },
                                    }))
                                  }
                                />
                                <span className={styles.switchTrack} />
                                <span className={styles.switchLabel}>{item.ativo ? "Ativo" : "Fechado"}</span>
                              </label>
                            </div>

                            <div className={styles.workingTimeGrid}>
                              <Field label="Inicio">
                                <input
                                  type="time"
                                  value={item.inicio}
                                  disabled={!item.ativo}
                                  className={styles.input}
                                  onChange={(e) =>
                                    setFuncionamento((prev) => ({
                                      ...prev,
                                      [day.key]: { ...prev[day.key], inicio: e.target.value },
                                    }))
                                  }
                                />
                              </Field>
                              <Field label="Fim">
                                <input
                                  type="time"
                                  value={item.fim}
                                  disabled={!item.ativo}
                                  className={styles.input}
                                  onChange={(e) =>
                                    setFuncionamento((prev) => ({
                                      ...prev,
                                      [day.key]: { ...prev[day.key], fim: e.target.value },
                                    }))
                                  }
                                />
                              </Field>
                            </div>
                          </article>
                        );
                      })}
                    </div>

                    <div className={styles.formActions}>
                      <ActionButton type="submit" disabled={savingFuncionamento}>
                        {savingFuncionamento ? "Salvando..." : "Salvar funcionamento"}
                      </ActionButton>
                    </div>
                  </form>
                </Panel>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <Modal
        isOpen={showClienteModal}
        onClose={fecharClienteModal}
        title={editClienteId ? "Editar cliente" : "Novo cliente"}
        subtitle="Cadastre rapidamente o contato para reutilizar em agendamentos."
      >
        <form onSubmit={submitCliente} className={styles.formStack}>
          <Field label="Nome do cliente" required>
            <input
              className={styles.input}
              placeholder="Ex: Joao Silva"
              value={novoCliente.nome}
              onChange={(e) => setNovoCliente((prev) => ({ ...prev, nome: e.target.value }))}
              required
            />
          </Field>
          <Field label="Telefone" required>
            <input
              className={styles.input}
              placeholder="Ex: (11) 98765-4321"
              value={novoCliente.telefone}
              onChange={(e) => setNovoCliente((prev) => ({ ...prev, telefone: e.target.value }))}
              required
            />
          </Field>
          <div className={styles.formActions}>
            <ActionButton variant="ghost" onClick={fecharClienteModal}>
              Cancelar
            </ActionButton>
            <ActionButton type="submit">{editClienteId ? "Atualizar cliente" : "Criar cliente"}</ActionButton>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={showServicoModal}
        onClose={fecharServicoModal}
        title={editServicoId ? "Editar servico" : "Novo servico"}
        subtitle="Mantenha nome, duracao e preco alinhados com a agenda."
      >
        <form onSubmit={submitServico} className={styles.formStack}>
          <Field label="Nome do servico" required>
            <input
              className={styles.input}
              placeholder="Ex: Corte basico"
              value={novoServico.nome}
              onChange={(e) => setNovoServico((prev) => ({ ...prev, nome: e.target.value }))}
              required
            />
          </Field>
          <div className={styles.formGrid}>
            <Field label="Duracao" required hint="Em minutos">
              <input
                className={styles.input}
                type="number"
                value={novoServico.duracao_minutos}
                onChange={(e) =>
                  setNovoServico((prev) => ({ ...prev, duracao_minutos: Number(e.target.value) }))
                }
                required
              />
            </Field>
            <Field label="Preco" required hint="Valor em reais">
              <input
                className={styles.input}
                type="number"
                step="0.01"
                value={novoServico.preco}
                onChange={(e) => setNovoServico((prev) => ({ ...prev, preco: Number(e.target.value) }))}
                required
              />
            </Field>
          </div>
          <label className={styles.switchField}>
            <input
              type="checkbox"
              checked={Boolean(novoServico.pagamento_adiantado_obrigatorio)}
              onChange={(e) =>
                setNovoServico((prev) => ({
                  ...prev,
                  pagamento_adiantado_obrigatorio: e.target.checked,
                  advance_payment_type: e.target.checked ? prev.advance_payment_type ?? "full" : "full",
                  advance_payment_amount: e.target.checked ? prev.advance_payment_amount : null,
                }))
              }
            />
            <span className={styles.switchTrack} />
            <span className={styles.switchLabel}>
              {novoServico.pagamento_adiantado_obrigatorio
                ? "Exigir pagamento adiantado"
                : "Permitir agendamento sem pagamento adiantado"}
            </span>
          </label>
          {novoServico.pagamento_adiantado_obrigatorio ? (
            <div className={styles.inlineInfoCard}>
              <p className={styles.inlineInfoTitle}>Configuracao da cobranca online</p>
              <div className={styles.formGrid}>
                <Field label="Tipo de pagamento adiantado" required>
                  <select
                    className={styles.select}
                    value={novoServico.advance_payment_type ?? "full"}
                    onChange={(e) =>
                      setNovoServico((prev) => ({
                        ...prev,
                        advance_payment_type: e.target.value as "full" | "signal",
                        advance_payment_amount:
                          e.target.value === "signal"
                            ? prev.advance_payment_amount
                            : null,
                      }))
                    }
                  >
                    <option value="full">Valor total</option>
                    <option value="signal">Sinal</option>
                  </select>
                </Field>
                {novoServico.advance_payment_type === "signal" ? (
                  <Field
                    label="Valor do sinal"
                    required
                    hint="O valor do sinal deve ser maior que zero e menor ou igual ao preco do servico."
                  >
                    <input
                      className={styles.input}
                      type="number"
                      step="0.01"
                      min={0}
                      max={novoServico.preco}
                      value={novoServico.advance_payment_amount ?? ""}
                      onChange={(e) =>
                        setNovoServico((prev) => ({
                          ...prev,
                          advance_payment_amount: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                      required
                    />
                  </Field>
                ) : null}
              </div>
              <Field
                label="Descricao opcional no checkout"
                hint="Texto exibido no checkout do cliente (opcional)."
              >
                <input
                  className={styles.input}
                  value={novoServico.payment_description_override ?? ""}
                  onChange={(e) =>
                    setNovoServico((prev) => ({
                      ...prev,
                      payment_description_override: e.target.value,
                    }))
                  }
                  placeholder="Ex: Sinal para reservar horario"
                />
              </Field>
              <p className={styles.inlineInfoText}>
                O agendamento so sera confirmado apos a aprovacao do pagamento. A conta de recebimento e definida pela administracao do sistema.
              </p>
              {!mercadoPagoConectado ? (
                <Notice
                  tone="warning"
                  message="Este estabelecimento ainda nao possui conta de pagamento configurada pela administracao. O pagamento online nao ficara disponivel ate essa configuracao ser feita."
                />
              ) : null}
            </div>
          ) : null}
          <div className={styles.formActions}>
            <ActionButton variant="ghost" onClick={fecharServicoModal}>
              Cancelar
            </ActionButton>
            <ActionButton type="submit">{editServicoId ? "Atualizar servico" : "Criar servico"}</ActionButton>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        title="Limite do plano básico atingido"
        size="md"
      >
        <div className={styles.upgradeModalBody}>
          <p className={styles.upgradeModalText}>
            O plano básico permite <strong>1 profissional</strong> ativo. Com o{" "}
            <strong>Premium</strong> você pode cadastrar até 3 profissionais e ter acesso
            a dashboard financeiro, análise de clientes e suporte prioritário.
          </p>
          <div className={styles.upgradeModalActions}>
            <ActionButton variant="primary" onClick={() => router.push("/upgrade")}>
              Fazer upgrade
            </ActionButton>
            <ActionButton variant="ghost" onClick={() => setShowUpgradeModal(false)}>
              Agora não
            </ActionButton>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showBarbeiroModal}
        onClose={fecharBarbeiroModal}
        title={editBarbeiroId ? "Editar profissional" : "Novo profissional"}
        subtitle="Quem estiver aqui pode aparecer como responsavel pelo atendimento."
        size="lg"
      >
        <form onSubmit={submitBarbeiro} className={styles.formStack}>
          <Field label="Nome do profissional" required>
            <input
              className={styles.input}
              placeholder="Ex: Carlos"
              value={novoBarbeiro.nome}
              onChange={(e) => setNovoBarbeiro((prev) => ({ ...prev, nome: e.target.value }))}
              required
            />
          </Field>
          <div className={styles.inlineInfoCard}>
            <p className={styles.inlineInfoTitle}>Disponibilidade individual</p>
            <p className={styles.inlineInfoText}>
              Esses horarios refinam o funcionamento geral do estabelecimento. Exemplo: se o estabelecimento abre
              08:00 e o profissional comeca 13:00, a manha nao aparece para ele.
            </p>
          </div>
          <div className={styles.workingDaysGrid}>
            {workingDays.map((day) => {
              const item = novoBarbeiro.horarios_funcionamento[day.key];
              return (
                <article key={day.key} className={styles.workingCard}>
                  <div className={styles.workingCardHeader}>
                    <div>
                      <h3 className={styles.workingDayTitle}>{day.label}</h3>
                      <p className={styles.workingDayMeta}>
                        {item.ativo ? "Aceitando agenda" : "Fora do expediente"}
                      </p>
                    </div>
                    <label className={styles.switchField}>
                      <input
                        type="checkbox"
                        checked={item.ativo}
                        onChange={(e) =>
                          setNovoBarbeiro((prev) => ({
                            ...prev,
                            horarios_funcionamento: {
                              ...prev.horarios_funcionamento,
                              [day.key]: {
                                ...prev.horarios_funcionamento[day.key],
                                ativo: e.target.checked,
                              },
                            },
                          }))
                        }
                      />
                      <span className={styles.switchTrack} />
                      <span className={styles.switchLabel}>{item.ativo ? "Ativo" : "Fechado"}</span>
                    </label>
                  </div>

                  <div className={styles.workingTimeGrid}>
                    <Field label="Inicio">
                      <input
                        className={styles.input}
                        type="time"
                        value={item.inicio}
                        disabled={!item.ativo}
                        onChange={(e) =>
                          setNovoBarbeiro((prev) => ({
                            ...prev,
                            horarios_funcionamento: {
                              ...prev.horarios_funcionamento,
                              [day.key]: {
                                ...prev.horarios_funcionamento[day.key],
                                inicio: e.target.value,
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                    <Field label="Fim">
                      <input
                        className={styles.input}
                        type="time"
                        value={item.fim}
                        disabled={!item.ativo}
                        onChange={(e) =>
                          setNovoBarbeiro((prev) => ({
                            ...prev,
                            horarios_funcionamento: {
                              ...prev.horarios_funcionamento,
                              [day.key]: {
                                ...prev.horarios_funcionamento[day.key],
                                fim: e.target.value,
                              },
                            },
                          }))
                        }
                      />
                    </Field>
                  </div>
                </article>
              );
            })}
          </div>
          <div className={styles.formActions}>
            <ActionButton variant="ghost" onClick={fecharBarbeiroModal}>
              Cancelar
            </ActionButton>
            <ActionButton type="submit">{editBarbeiroId ? "Atualizar profissional" : "Criar profissional"}</ActionButton>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={showAgendamentoModal}
        onClose={fecharModalAgendamento}
        title={editAgendamentoId ? "Editar agendamento" : "Novo agendamento"}
        subtitle="Escolha cliente, servico e horario. As regras de funcionamento sao validadas no backend."
        size="lg"
      >
        <form onSubmit={submitAgendamento} className={styles.formStack}>
          {error ? <Notice tone="error" message={error} onClose={() => setError(null)} /> : null}

          <div className={styles.formGrid}>
            <Field label="Cliente" required>
              <select
                className={styles.select}
                value={formAgendamento.clienteId}
                onChange={(e) => setFormAgendamento((prev) => ({ ...prev, clienteId: e.target.value }))}
                required
              >
                <option value="">Selecione um cliente</option>
                {clientes.map((cliente) => (
                  <option key={cliente.id} value={cliente.id}>
                    {cliente.nome} ({cliente.telefone})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Profissional" required>
              <select
                className={styles.select}
                value={formAgendamento.barbeiroId}
                onChange={(e) => setFormAgendamento((prev) => ({ ...prev, barbeiroId: e.target.value }))}
                required
              >
                <option value="">Selecione um profissional</option>
                {barbeiros.map((barbeiro) => (
                  <option key={barbeiro.id} value={barbeiro.id}>
                    {barbeiro.nome}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className={styles.formGrid}>
            <Field label="Servico" required>
              <select
                className={styles.select}
                value={formAgendamento.servicoId}
                onChange={(e) => setFormAgendamento((prev) => ({ ...prev, servicoId: e.target.value }))}
                required
              >
                <option value="">Selecione um servico</option>
                {servicos.map((servico) => (
                  <option key={servico.id} value={servico.id}>
                    {servico.nome} ({servico.duracao_minutos} min - {formatCurrency(servico.preco)})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select
                className={styles.select}
                value={formAgendamento.status}
                onChange={(e) =>
                  setFormAgendamento((prev) => ({
                    ...prev,
                    status: e.target.value as
                      | "pending_payment"
                      | "pendente"
                      | "confirmado"
                      | "cancelado"
                      | "reagendamento_solicitado"
                      | "compareceu"
                      | "no_show"
                      | "failed"
                      | "expired",
                  }))
                }
              >
                <option value="pending_payment">Aguardando pagamento</option>
                <option value="confirmado">Confirmado</option>
                <option value="pendente">Pendente</option>
                <option value="cancelado">Cancelado</option>
                <option value="expired">Expirado</option>
                <option value="reagendamento_solicitado">Reagendamento solicitado</option>
                <option value="compareceu">Compareceu</option>
                <option value="no_show">Nao compareceu</option>
                <option value="failed">Falhou</option>
              </select>
            </Field>
          </div>

          <Field label="Data e hora" required hint="A validacao respeita o funcionamento configurado">
            <input
              className={styles.input}
              type="datetime-local"
              value={formAgendamento.dataHora}
              onChange={(e) => setFormAgendamento((prev) => ({ ...prev, dataHora: e.target.value }))}
              required
            />
          </Field>

          {dicaFuncionamentoBarbeiro ? (
            <div className={styles.inlineInfoCard}>
              <p className={styles.inlineInfoTitle}>Horario do profissional</p>
              <p className={styles.inlineInfoText}>{dicaFuncionamentoBarbeiro}</p>
            </div>
          ) : null}

          <div className={styles.formActions}>
            <ActionButton variant="ghost" onClick={fecharModalAgendamento}>
              Cancelar
            </ActionButton>
            <ActionButton type="submit">
              {editAgendamentoId ? "Atualizar agendamento" : "Criar agendamento"}
            </ActionButton>
          </div>
        </form>
      </Modal>
    </main>
  );
}
