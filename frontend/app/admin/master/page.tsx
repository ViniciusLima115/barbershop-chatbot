"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BellRing, Building2, CalendarDays, ChevronLeft, ChevronRight, Clock, KeyRound, Lock, RefreshCw, Search, ShieldCheck, Trash2, UserRound, X } from "lucide-react";
import Alert from "../../components/Alert";
import Button from "../../components/Button";
import FormInput from "../../components/FormInput";
import Modal from "../../components/Modal";
import styles from "./master.module.css";
import {
  BarbeariaAdmin,
  PlanoBarbearia,
  createBarbeariaAdmin,
  deleteBarbeariaAdmin,
  getStatusAssinaturaBarbearia,
  listBarbeariasAdmin,
  StatusManualBarbearia,
  StatusAssinaturaBarbearia,
  updateBarbeariaAdmin,
} from "@/services/estabelecimentos-admin";

function plusDaysISO(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function statusLabel(status: StatusAssinaturaBarbearia): string {
  if (status === "trial") return "Trial";
  if (status === "bloqueado_atraso") return "Bloqueado por atraso";
  if (status === "inativo") return "Inativo";
  return "Ativo";
}

const initialForm = {
  nome: "",
  login: "",
  senha: "",
  plano: "gratis" as PlanoBarbearia,
  vencimentoEm: plusDaysISO(30),
  trialAtivo: false,
  trialFimEm: plusDaysISO(7),
  pagamentoRecusado: false,
};

const initialFiltros = {
  busca: "",
  plano: "todos",
  status: "todos",
  atividade: "todos",
  dataDe: "",
  dataAte: "",
};

export default function AdminPage() {
  const [barbearias, setBarbearias] = useState<BarbeariaAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(initialForm);
  const [filtros, setFiltros] = useState(initialFiltros);
  const [showPasswords, setShowPasswords] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selected, setSelected] = useState<BarbeariaAdmin | null>(null);
  const [pagina, setPagina] = useState(1);
  const [buscaRapida, setBuscaRapida] = useState("");
  const POR_PAGINA = 15;
  const [editForm, setEditForm] = useState({
    nome: "",
    login: "",
    senha: "",
    plano: "gratis" as PlanoBarbearia,
    statusManual: "ativo" as StatusManualBarbearia,
    vencimentoEm: plusDaysISO(30),
    trialAtivo: false,
    trialFimEm: plusDaysISO(7),
    ultimoAcessoEm: "",
    pagamentoRecusado: false,
  });

  async function recarregar() {
    try {
      setLoading(true);
      const items = await listBarbeariasAdmin();
      setBarbearias(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar estabelecimentos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    recarregar();
  }, []);

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(null), 3500);
    return () => clearTimeout(t);
  }, [success]);

  const totalGratis = useMemo(
    () => barbearias.filter((b) => b.plano === "gratis").length,
    [barbearias]
  );
  const totalBasico = useMemo(
    () => barbearias.filter((b) => b.plano === "basico").length,
    [barbearias]
  );
  const totalPremium = useMemo(
    () => barbearias.filter((b) => b.plano === "premium").length,
    [barbearias]
  );
  const totalBloqueadas = useMemo(
    () => barbearias.filter((b) => getStatusAssinaturaBarbearia(b) === "bloqueado_atraso").length,
    [barbearias]
  );
  const totalTrial = useMemo(
    () => barbearias.filter((b) => getStatusAssinaturaBarbearia(b) === "trial").length,
    [barbearias]
  );
  const barbeariasFiltradas = useMemo(() => {
    const busca = filtros.busca.trim().toLowerCase();

    return barbearias.filter((item) => {
      const status = getStatusAssinaturaBarbearia(item);
      const nomeBarbearia = item.nome.toLowerCase();

      const matchBusca = !busca || nomeBarbearia.includes(busca);
      const matchPlano = filtros.plano === "todos" || item.plano === filtros.plano;
      const matchStatus = filtros.status === "todos" || status === filtros.status;

      const criadoDia = item.criadoEm.slice(0, 10);
      const matchDataDe = !filtros.dataDe || criadoDia >= filtros.dataDe;
      const matchDataAte = !filtros.dataAte || criadoDia <= filtros.dataAte;

      let matchAtividade = true;
      if (filtros.atividade === "nunca") {
        matchAtividade = !item.ultimoAcessoEm;
      } else if (filtros.atividade === "com_acesso") {
        matchAtividade = Boolean(item.ultimoAcessoEm);
      } else if (filtros.atividade === "acesso_7d") {
        if (!item.ultimoAcessoEm) {
          matchAtividade = false;
        } else {
          const limite = new Date();
          limite.setDate(limite.getDate() - 7);
          matchAtividade = item.ultimoAcessoEm >= limite.toISOString();
        }
      } else if (filtros.atividade === "sem_acesso_7d") {
        if (!item.ultimoAcessoEm) {
          matchAtividade = true;
        } else {
          const limite = new Date();
          limite.setDate(limite.getDate() - 7);
          matchAtividade = item.ultimoAcessoEm < limite.toISOString();
        }
      }

      return matchBusca && matchPlano && matchStatus && matchDataDe && matchDataAte && matchAtividade;
    });
  }, [barbearias, filtros]);

  // reset page when filters or quick-search change
  useEffect(() => { setPagina(1); }, [filtros, buscaRapida]);

  const listaFiltradaComBusca = useMemo(() => {
    const q = buscaRapida.trim().toLowerCase();
    if (!q) return barbeariasFiltradas;
    return barbeariasFiltradas.filter(
      (b) => b.nome.toLowerCase().includes(q) || b.login.toLowerCase().includes(q)
    );
  }, [barbeariasFiltradas, buscaRapida]);

  const totalPaginas = Math.max(1, Math.ceil(listaFiltradaComBusca.length / POR_PAGINA));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const listaVisivelSlice = listaFiltradaComBusca.slice(
    (paginaAtual - 1) * POR_PAGINA,
    paginaAtual * POR_PAGINA
  );

  const notificacoes = useMemo(() => {
    const today = plusDaysISO(0);
    const dueSoon = plusDaysISO(3);
    const seteDiasAtras = new Date();
    seteDiasAtras.setDate(seteDiasAtras.getDate() - 7);

    const items: Array<{
      id: string;
      tipo: "warning" | "danger";
      titulo: string;
      descricao: string;
    }> = [];

    barbearias.forEach((item) => {
      const status = getStatusAssinaturaBarbearia(item);
      if (status === "inativo") return;

      if (item.pagamentoRecusado) {
        items.push({
          id: `${item.id}-pagamento`,
          tipo: "danger",
          titulo: "Pagamento recusado",
          descricao: `${item.nome}: houve recusa no pagamento da assinatura.`,
        });
      }

      if (item.vencimentoEm < today) {
        items.push({
          id: `${item.id}-vencido`,
          tipo: "danger",
          titulo: "Assinatura vencida",
          descricao: `${item.nome}: assinatura vencida em ${item.vencimentoEm}.`,
        });
      } else if (item.vencimentoEm >= today && item.vencimentoEm <= dueSoon) {
        items.push({
          id: `${item.id}-vence-breve`,
          tipo: "warning",
          titulo: "Vencimento proximo",
          descricao: `${item.nome}: assinatura vence em ${item.vencimentoEm}.`,
        });
      }

      const semAcessoRecente =
        !item.ultimoAcessoEm || item.ultimoAcessoEm < seteDiasAtras.toISOString();
      if (semAcessoRecente) {
        items.push({
          id: `${item.id}-atividade`,
          tipo: "warning",
          titulo: "Baixa atividade",
          descricao: `${item.nome}: sem acesso recente nos ultimos 7 dias.`,
        });
      }
    });

    return items;
  }, [barbearias]);

  function limparMensagens() {
    setError(null);
    setSuccess(null);
  }

  async function submitCadastro(e: FormEvent) {
    e.preventDefault();
    limparMensagens();

    if (!form.nome.trim() || !form.login.trim() || !form.senha.trim()) {
      setError("Preencha nome, login e senha para cadastrar.");
      return;
    }
    if (!form.vencimentoEm) {
      setError("Informe a data de vencimento.");
      return;
    }
    if (form.trialAtivo && !form.trialFimEm) {
      setError("Informe a data final do trial.");
      return;
    }

    try {
      await createBarbeariaAdmin(form);
      setSuccess("Estabelecimento cadastrado com sucesso!");
      setForm(initialForm);
      await recarregar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao cadastrar estabelecimento.");
    }
  }

  function abrirModalSenha(item: BarbeariaAdmin) {
    setSelected(item);
    setEditForm({
      nome: item.nome,
      login: item.login,
      senha: item.senha,
      plano: item.plano,
      statusManual: item.statusManual,
      vencimentoEm: item.vencimentoEm,
      trialAtivo: item.trialAtivo,
      trialFimEm: item.trialFimEm ?? plusDaysISO(7),
      ultimoAcessoEm: item.ultimoAcessoEm ? item.ultimoAcessoEm.slice(0, 10) : "",
      pagamentoRecusado: item.pagamentoRecusado,
    });
    limparMensagens();
  }

  async function salvarNovaSenha(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    if (!editForm.nome.trim() || !editForm.login.trim() || !editForm.senha.trim()) {
      setError("Preencha nome, login e senha.");
      return;
    }
    if (!editForm.vencimentoEm) {
      setError("Informe o vencimento.");
      return;
    }
    if (editForm.trialAtivo && !editForm.trialFimEm) {
      setError("Informe a data de fim do trial.");
      return;
    }

    try {
      await updateBarbeariaAdmin(selected.id, {
        nome: editForm.nome.trim(),
        login: editForm.login.trim(),
        senha: editForm.senha,
        plano: editForm.plano,
        statusManual: editForm.statusManual,
        vencimentoEm: editForm.vencimentoEm,
        trialAtivo: editForm.trialAtivo,
        trialFimEm: editForm.trialAtivo ? editForm.trialFimEm : null,
        ultimoAcessoEm: editForm.ultimoAcessoEm ? `${editForm.ultimoAcessoEm}T00:00:00.000Z` : null,
        pagamentoRecusado: editForm.pagamentoRecusado,
      });
      setSuccess(`Estabelecimento "${selected.nome}" atualizado com sucesso.`);
      setSelected(null);
      await recarregar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar estabelecimento.");
    }
  }

  async function excluirBarbearia(item: BarbeariaAdmin) {
    limparMensagens();
    const confirmar = window.confirm(
      `Tem certeza que deseja excluir o estabelecimento "${item.nome}"? Essa acao nao pode ser desfeita.`
    );
    if (!confirmar) return;

    try {
      await deleteBarbeariaAdmin(item.id);
      setSuccess(`Estabelecimento "${item.nome}" excluido com sucesso.`);
      await recarregar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir estabelecimento.");
    }
  }

  return (
    <main className={styles.page}>
      <div className={`app-container ${styles.shell}`}>

        {/* ── Hero ──────────────────────────────────────────── */}
        <div className={styles.hero}>
          <p className={styles.eyebrow}>Master Admin</p>
          <h1 className={styles.heroTitle}>Painel do Administrador</h1>
          <p className={styles.heroSubtitle}>
            Gerencie estabelecimentos, planos, login e senha de todos os clientes.
          </p>
        </div>

        {/* ── Stats ─────────────────────────────────────────── */}
        <div className={styles.statsRow}>
          <div className={styles.statCard}>
            <div className={styles.statIcon}><Building2 size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Total</span>
              <span className={styles.statValue}>{barbearias.length}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statIcon}><ShieldCheck size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Plano Gratis</span>
              <span className={styles.statValue}>{totalGratis}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statIcon}><ShieldCheck size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Plano Basico</span>
              <span className={styles.statValue}>{totalBasico}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.statIconSuccess}`}><ShieldCheck size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Plano Premium</span>
              <span className={styles.statValue}>{totalPremium}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.statIconWarning}`}><ShieldCheck size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Em Trial</span>
              <span className={styles.statValue}>{totalTrial}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.statIconDanger}`}><Lock size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Bloqueados</span>
              <span className={styles.statValue}>{totalBloqueadas}</span>
            </div>
          </div>
        </div>

        {/* ── Section stack ─────────────────────────────────── */}
        <div className={styles.sections}>

          {/* Alerts */}
          {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
          {success && <Alert type="success" message={success} onClose={() => setSuccess(null)} />}

          {/* Loading */}
          {loading && (
            <div className={styles.panel}>
              <div className={styles.loadingState}>
                <div className={styles.loadingPulse} />
                <p className={styles.panelSubtitle}>Buscando estabelecimentos...</p>
              </div>
            </div>
          )}

          {/* Notifications */}
          <div className={styles.panel}>
            <div className={styles.panelHeader}>
              <p className={styles.panelTitle}>Notificacoes</p>
              <p className={styles.panelSubtitle}>
                Alertas de vencimento, pagamento recusado e baixa atividade.
              </p>
            </div>
            {notificacoes.length === 0 ? (
              <p className={styles.empty}>Nenhuma notificacao no momento.</p>
            ) : (
              <div className={styles.notifList}>
                {notificacoes.map((n) => (
                  <div
                    key={n.id}
                    className={`${styles.notifItem} ${n.tipo === "danger" ? styles.notifDanger : styles.notifWarning}`}
                  >
                    <div className={n.tipo === "danger" ? styles.notifIconDanger : styles.notifIconWarning}>
                      {n.tipo === "danger" ? <AlertTriangle size={16} /> : <BellRing size={16} />}
                    </div>
                    <div>
                      <p className={styles.notifTitle}>{n.titulo}</p>
                      <p className={styles.notifDesc}>{n.descricao}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Cadastro + Quick Actions */}
          <div className={styles.twoCol}>
            {/* Cadastrar */}
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <p className={styles.panelTitle}>Cadastrar Estabelecimento</p>
                <p className={styles.panelSubtitle}>
                  Crie login/senha e defina o plano do novo estabelecimento.
                </p>
              </div>
              <form onSubmit={submitCadastro} className={styles.formStack}>
                <FormInput
                  label="Nome do Estabelecimento"
                  value={form.nome}
                  placeholder="Ex: Barbearia Central / Salao Beleza"
                  onChange={(e) => setForm((prev) => ({ ...prev, nome: e.target.value }))}
                  required
                />
                <FormInput
                  label="Login"
                  value={form.login}
                  placeholder="Ex: estabelecimento.central"
                  onChange={(e) => setForm((prev) => ({ ...prev, login: e.target.value }))}
                  required
                />
                <FormInput
                  label="Senha"
                  type="text"
                  value={form.senha}
                  placeholder="Defina uma senha inicial"
                  onChange={(e) => setForm((prev) => ({ ...prev, senha: e.target.value }))}
                  required
                />
                <FormInput
                  as="select"
                  label="Plano"
                  value={form.plano}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, plano: e.target.value as PlanoBarbearia }))
                  }
                >
                  <option value="gratis">Plano Gratis</option>
                  <option value="basico">Plano Basico</option>
                  <option value="premium">Plano Premium</option>
                </FormInput>
                <FormInput
                  label="Vencimento da Assinatura"
                  type="date"
                  value={form.vencimentoEm}
                  onChange={(e) => setForm((prev) => ({ ...prev, vencimentoEm: e.target.value }))}
                  required
                />
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={form.trialAtivo}
                    onChange={(e) => setForm((prev) => ({ ...prev, trialAtivo: e.target.checked }))}
                  />
                  Habilitar trial
                </label>
                {form.trialAtivo && (
                  <FormInput
                    label="Trial ate"
                    type="date"
                    value={form.trialFimEm}
                    onChange={(e) => setForm((prev) => ({ ...prev, trialFimEm: e.target.value }))}
                    required
                  />
                )}
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={form.pagamentoRecusado}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, pagamentoRecusado: e.target.checked }))
                    }
                  />
                  Pagamento recusado
                </label>
                <div className={styles.formFooter}>
                  <Button type="submit">
                    <Building2 size={17} />
                    Cadastrar Estabelecimento
                  </Button>
                </div>
              </form>
            </div>

            {/* Quick actions */}
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <p className={styles.panelTitle}>Acoes Rapidas</p>
                <p className={styles.panelSubtitle}>
                  Controle de senhas e recarregamento da base.
                </p>
              </div>
              <div className={styles.actionsStack}>
                <Button
                  variant={showPasswords ? "danger" : "secondary"}
                  onClick={() => setShowPasswords((prev) => !prev)}
                >
                  {showPasswords ? <X size={17} /> : <Lock size={17} />}
                  {showPasswords ? "Ocultar Senhas" : "Exibir Senhas"}
                </Button>
                <Button variant="secondary" onClick={recarregar}>
                  <RefreshCw size={17} />
                  Recarregar Lista
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setFiltros(initialFiltros)}
                >
                  <Search size={17} />
                  Limpar Filtros
                </Button>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className={styles.panel}>
            <div className={styles.panelHeader}>
              <p className={styles.panelTitle}>Busca e Filtros</p>
              <p className={styles.panelSubtitle}>
                Filtre por plano, status, nome/login, periodo e atividade.
              </p>
            </div>
            <div className={styles.filtersGrid}>
              <FormInput
                label="Busca (Estabelecimento)"
                value={filtros.busca}
                placeholder="Ex: Barbearia Central"
                onChange={(e) => setFiltros((prev) => ({ ...prev, busca: e.target.value }))}
              />
              <FormInput
                as="select"
                label="Plano"
                value={filtros.plano}
                onChange={(e) => setFiltros((prev) => ({ ...prev, plano: e.target.value }))}
              >
                <option value="todos">Todos</option>
                <option value="gratis">Gratis</option>
                <option value="basico">Basico</option>
                <option value="premium">Premium</option>
              </FormInput>
              <FormInput
                as="select"
                label="Status"
                value={filtros.status}
                onChange={(e) => setFiltros((prev) => ({ ...prev, status: e.target.value }))}
              >
                <option value="todos">Todos</option>
                <option value="ativo">Ativo</option>
                <option value="trial">Trial</option>
                <option value="bloqueado_atraso">Bloqueado por atraso</option>
                <option value="inativo">Inativo</option>
              </FormInput>
              <FormInput
                label="Cadastro de"
                type="date"
                value={filtros.dataDe}
                onChange={(e) => setFiltros((prev) => ({ ...prev, dataDe: e.target.value }))}
              />
              <FormInput
                label="Cadastro ate"
                type="date"
                value={filtros.dataAte}
                onChange={(e) => setFiltros((prev) => ({ ...prev, dataAte: e.target.value }))}
              />
              <FormInput
                as="select"
                label="Atividade"
                value={filtros.atividade}
                onChange={(e) => setFiltros((prev) => ({ ...prev, atividade: e.target.value }))}
              >
                <option value="todos">Todos</option>
                <option value="acesso_7d">Acesso nos ultimos 7 dias</option>
                <option value="sem_acesso_7d">Sem acesso nos ultimos 7 dias</option>
                <option value="com_acesso">Com ultimo acesso</option>
                <option value="nunca">Nunca acessou</option>
              </FormInput>
            </div>
          </div>

          {/* Establishments list */}
          <div className={styles.panel}>
            <div className={styles.panelHeaderRow}>
              <div className={styles.panelHeaderText}>
                <p className={styles.panelTitle}>
                  Estabelecimentos Cadastrados
                  {!loading && (
                    <> —{" "}
                      <span style={{ fontWeight: 400, color: "var(--ink-muted)" }}>
                        {listaFiltradaComBusca.length} resultado{listaFiltradaComBusca.length !== 1 ? "s" : ""}
                      </span>
                    </>
                  )}
                </p>
                <p className={styles.panelSubtitle}>
                  Visualize login/senha e altere dados quando necessario.
                </p>
              </div>
              <label className={styles.inlineSearch}>
                <Search size={15} />
                <input
                  className={styles.inlineSearchInput}
                  placeholder="Buscar por nome ou login..."
                  value={buscaRapida}
                  onChange={(e) => setBuscaRapida(e.target.value)}
                />
                {buscaRapida && (
                  <button
                    onClick={() => setBuscaRapida("")}
                    style={{ background: "none", border: "none", cursor: "pointer", display: "flex", color: "var(--ink-subtle)", padding: 0 }}
                    aria-label="Limpar busca"
                  >
                    <X size={14} />
                  </button>
                )}
              </label>
            </div>

            {listaFiltradaComBusca.length === 0 && !loading ? (
              <p className={styles.empty}>Nenhum estabelecimento encontrado.</p>
            ) : (
              <>
              <div className={styles.estabList}>
                {listaVisivelSlice.map((item) => {
                  const status = getStatusAssinaturaBarbearia(item);
                  return (
                    <div key={item.id} className={styles.estabRow}>
                      {/* Avatar */}
                      <div className={styles.estabAvatar}>
                        {item.nome.charAt(0).toUpperCase()}
                      </div>

                      {/* Name + login */}
                      <div className={styles.estabInfo}>
                        <p className={styles.estabName}>{item.nome}</p>
                        <p className={styles.estabLogin}>{item.login}</p>
                      </div>

                      {/* Badges */}
                      <div className={styles.estabBadges}>
                        <span className={`badge ${
                          item.plano === "premium"
                            ? "badge-confirmado"
                            : item.plano === "basico"
                              ? "badge-pendente"
                              : "badge-livre"
                        }`}>
                          {item.plano === "premium" ? "Premium" : item.plano === "basico" ? "Basico" : "Gratis"}
                        </span>
                        <span className={`badge ${
                          status === "bloqueado_atraso" || status === "inativo"
                            ? "badge-cancelado"
                            : status === "trial"
                              ? "badge-pendente"
                              : "badge-confirmado"
                        }`}>
                          {statusLabel(status)}
                        </span>
                      </div>

                      {/* Meta: vencimento + atividade */}
                      <div className={styles.estabMeta}>
                        <span className={styles.estabMetaItem}>
                          <CalendarDays size={12} />
                          Vence {item.vencimentoEm}
                        </span>
                        <span className={styles.estabMetaItem}>
                          <Clock size={12} />
                          {item.ultimoAcessoEm ? item.ultimoAcessoEm.slice(0, 10) : "Nunca acessou"}
                        </span>
                      </div>

                      {/* Password */}
                      <span className={styles.estabSenha}>
                        {showPasswords ? item.senha : "••••••••"}
                      </span>

                      {/* Actions */}
                      <div className={styles.estabActions}>
                        <Button variant="secondary" size="sm" onClick={() => abrirModalSenha(item)}>
                          Editar
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => excluirBarbearia(item)}>
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {totalPaginas > 1 && (
                <div className={styles.pagination}>
                  <span className={styles.paginationInfo}>
                    {(paginaAtual - 1) * POR_PAGINA + 1}–{Math.min(paginaAtual * POR_PAGINA, listaFiltradaComBusca.length)} de {listaFiltradaComBusca.length}
                  </span>
                  <div className={styles.paginationControls}>
                    <button
                      className={styles.pageBtn}
                      onClick={() => setPagina((p) => Math.max(1, p - 1))}
                      disabled={paginaAtual === 1}
                      aria-label="Pagina anterior"
                    >
                      <ChevronLeft size={15} />
                    </button>
                    {Array.from({ length: totalPaginas }, (_, i) => i + 1)
                      .filter((p) => p === 1 || p === totalPaginas || Math.abs(p - paginaAtual) <= 1)
                      .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                        if (idx > 0 && (p as number) - (arr[idx - 1] as number) > 1) acc.push("…");
                        acc.push(p);
                        return acc;
                      }, [])
                      .map((p, idx) =>
                        p === "…" ? (
                          <span key={`ellipsis-${idx}`} className={styles.paginationInfo} style={{ padding: "0 4px" }}>…</span>
                        ) : (
                          <button
                            key={p}
                            className={`${styles.pageBtn} ${p === paginaAtual ? styles.pageBtnActive : ""}`}
                            onClick={() => setPagina(p as number)}
                          >
                            {p}
                          </button>
                        )
                      )}
                    <button
                      className={styles.pageBtn}
                      onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
                      disabled={paginaAtual === totalPaginas}
                      aria-label="Proxima pagina"
                    >
                      <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
          </div>

        </div>
      </div>

      {/* ── Edit Modal ─────────────────────────────────────── */}
      <Modal
        isOpen={Boolean(selected)}
        onClose={() => setSelected(null)}
        title="Editar Estabelecimento"
      >
        {!selected ? null : (
          <form onSubmit={salvarNovaSenha} className={styles.formStack}>
            <div className={styles.modalInfoBox}>
              <p className={styles.modalInfoName}>{selected.nome}</p>
              <p className={styles.modalInfoLogin}>
                <UserRound size={14} />
                Login: {selected.login}
              </p>
            </div>

            <FormInput
              label="Nome do Estabelecimento"
              value={editForm.nome}
              onChange={(e) => setEditForm((prev) => ({ ...prev, nome: e.target.value }))}
              required
            />
            <FormInput
              label="Login"
              value={editForm.login}
              onChange={(e) => setEditForm((prev) => ({ ...prev, login: e.target.value }))}
              required
            />
            <FormInput
              label="Senha"
              type="text"
              value={editForm.senha}
              onChange={(e) => setEditForm((prev) => ({ ...prev, senha: e.target.value }))}
              required
            />
            <FormInput
              as="select"
              label="Plano"
              value={editForm.plano}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, plano: e.target.value as PlanoBarbearia }))
              }
            >
              <option value="gratis">Plano Gratis</option>
              <option value="basico">Plano Basico</option>
              <option value="premium">Plano Premium</option>
            </FormInput>
            <FormInput
              as="select"
              label="Status Manual"
              value={editForm.statusManual}
              onChange={(e) =>
                setEditForm((prev) => ({ ...prev, statusManual: e.target.value as StatusManualBarbearia }))
              }
            >
              <option value="ativo">Ativo</option>
              <option value="inativo">Inativo</option>
            </FormInput>
            <FormInput
              label="Vencimento"
              type="date"
              value={editForm.vencimentoEm}
              onChange={(e) => setEditForm((prev) => ({ ...prev, vencimentoEm: e.target.value }))}
              required
            />
            <label className={styles.checkLabel}>
              <input
                type="checkbox"
                checked={editForm.trialAtivo}
                onChange={(e) => setEditForm((prev) => ({ ...prev, trialAtivo: e.target.checked }))}
              />
              Trial ativo
            </label>
            {editForm.trialAtivo && (
              <FormInput
                label="Trial ate"
                type="date"
                value={editForm.trialFimEm}
                onChange={(e) => setEditForm((prev) => ({ ...prev, trialFimEm: e.target.value }))}
                required
              />
            )}
            <label className={styles.checkLabel}>
              <input
                type="checkbox"
                checked={editForm.pagamentoRecusado}
                onChange={(e) =>
                  setEditForm((prev) => ({ ...prev, pagamentoRecusado: e.target.checked }))
                }
              />
              Pagamento recusado
            </label>
            <FormInput
              label="Ultimo acesso (opcional)"
              type="date"
              value={editForm.ultimoAcessoEm}
              onChange={(e) => setEditForm((prev) => ({ ...prev, ultimoAcessoEm: e.target.value }))}
            />

            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setSelected(null)}>
                Cancelar
              </Button>
              <Button type="submit">
                <KeyRound size={16} />
                Salvar Alteracoes
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </main>
  );
}
