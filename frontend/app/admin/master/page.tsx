"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BellRing, Building2, KeyRound, Lock, Search, ShieldCheck, Trash2, UserRound } from "lucide-react";
import Alert from "../../components/Alert";
import Button from "../../components/Button";
import Card from "../../components/Card";
import FormInput from "../../components/FormInput";
import Modal from "../../components/Modal";
import StatCard from "../../components/StatCard";
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
  plano: "basico" as PlanoBarbearia,
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
  const [editForm, setEditForm] = useState({
    nome: "",
    login: "",
    senha: "",
    plano: "basico" as PlanoBarbearia,
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
      setError(err instanceof Error ? err.message : "Falha ao carregar barbearias.");
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
    <main className="min-h-screen bg-gray-50">
      <div className="py-8">
        <div className="app-container space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Painel do Administrador</h1>
            <p className="mt-1 text-gray-600">
              Gerencie estabelecimentos, planos, login e senha de todos os clientes.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <StatCard label="Total de Estabelecimentos" value={barbearias.length} icon={<Building2 size={22} />} color="blue" />
            <StatCard label="Plano Basico" value={totalBasico} icon={<ShieldCheck size={22} />} color="amber" />
            <StatCard label="Plano Premium" value={totalPremium} icon={<ShieldCheck size={22} />} color="green" />
            <StatCard label="Em Trial" value={totalTrial} icon={<ShieldCheck size={22} />} color="blue" />
            <StatCard label="Bloqueados" value={totalBloqueadas} icon={<Lock size={22} />} color="red" />
          </div>

          {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
          {success && <Alert type="success" message={success} onClose={() => setSuccess(null)} />}

          {loading && (
            <Card title="Carregando" subtitle="Buscando estabelecimentos no backend">
              <p className="text-sm text-gray-600">Aguarde...</p>
            </Card>
          )}

          <Card
            title="Notificacoes Automaticas"
            subtitle="Alertas de vencimento, pagamento recusado e baixa atividade"
          >
            {notificacoes.length === 0 ? (
              <p className="text-sm text-gray-600">Nenhuma notificacao no momento.</p>
            ) : (
              <div className="space-y-3">
                {notificacoes.map((n) => (
                  <div
                    key={n.id}
                    className={`flex items-start gap-3 rounded-lg border p-3 ${
                      n.tipo === "danger"
                        ? "border-red-200 bg-red-50"
                        : "border-amber-200 bg-amber-50"
                    }`}
                  >
                    <div className={`mt-0.5 ${n.tipo === "danger" ? "text-red-600" : "text-amber-600"}`}>
                      {n.tipo === "danger" ? <AlertTriangle size={16} /> : <BellRing size={16} />}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{n.titulo}</p>
                      <p className="text-sm text-gray-700">{n.descricao}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card
              title="Cadastrar Estabelecimento"
              subtitle="Crie login/senha e defina o plano do novo estabelecimento"
            >
              <form onSubmit={submitCadastro} className="space-y-4">
                <FormInput
                  label="Nome do Estabelecimento"
                  value={form.nome}
                  placeholder="Ex: Barbearia Central / Salão Beleza"
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
                <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
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
                <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.pagamentoRecusado}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, pagamentoRecusado: e.target.checked }))
                    }
                  />
                  Pagamento recusado
                </label>

                <div className="pt-3">
                  <Button type="submit">
                    <Building2 size={17} />
                    Cadastrar Estabelecimento
                  </Button>
                </div>
              </form>
            </Card>

            <Card
              title="Acoes Rapidas"
              subtitle="Controle visualizacao de senhas e recarregue a base"
            >
              <div className="space-y-3">
                <Button
                  variant={showPasswords ? "danger" : "secondary"}
                  onClick={() => setShowPasswords((prev) => !prev)}
                >
                  <Lock size={17} />
                  {showPasswords ? "Ocultar Senhas" : "Exibir Senhas"}
                </Button>
                <Button variant="secondary" onClick={recarregar}>
                  <KeyRound size={17} />
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
            </Card>
          </div>

          <Card title="Busca e Filtros" subtitle="Filtre por plano, status, nome/login, periodo e atividade">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
          </Card>

          <Card title="Estabelecimentos Cadastrados" subtitle="Visualize login/senha e altere senha quando necessario">
            {barbeariasFiltradas.length === 0 ? (
              <p className="text-sm text-gray-600">Nenhum estabelecimento cadastrado ainda.</p>
            ) : (
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Estabelecimento</th>
                      <th>Login</th>
                      <th>Senha</th>
                      <th>Plano</th>
                      <th>Status</th>
                      <th>Vencimento</th>
                      <th>Trial</th>
                      <th>Atividade</th>
                      <th className="text-right">Acoes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {barbeariasFiltradas.map((item) => {
                      const status = getStatusAssinaturaBarbearia(item);
                      return (
                      <tr key={item.id}>
                        <td className="font-medium">{item.nome}</td>
                        <td>{item.login}</td>
                        <td>{showPasswords ? item.senha : "••••••••"}</td>
                        <td>
                          <span
                            className={`badge ${
                              item.plano === "premium" ? "badge-success" : "badge-pending"
                            }`}
                          >
                            {item.plano === "premium" ? "Premium" : "Basico"}
                          </span>
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              status === "bloqueado_atraso"
                                ? "badge-danger"
                                : status === "trial"
                                  ? "badge-pending"
                                  : status === "inativo"
                                    ? "badge-danger"
                                    : "badge-success"
                            }`}
                          >
                            {statusLabel(status)}
                          </span>
                        </td>
                        <td>{item.vencimentoEm}</td>
                        <td>{item.trialAtivo ? item.trialFimEm ?? "Sem data" : "Nao"}</td>
                        <td>{item.ultimoAcessoEm ? item.ultimoAcessoEm.slice(0, 10) : "Nunca"}</td>
                        <td className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="secondary" size="sm" onClick={() => abrirModalSenha(item)}>
                              Editar
                            </Button>
                            <Button variant="danger" size="sm" onClick={() => excluirBarbearia(item)}>
                              <Trash2 size={14} />
                              Excluir
                            </Button>
                          </div>
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>

      <Modal
        isOpen={Boolean(selected)}
        onClose={() => setSelected(null)}
        title="Editar Barbearia"
      >
        {!selected ? null : (
          <form onSubmit={salvarNovaSenha} className="space-y-4">
            <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
              <p className="font-semibold text-gray-900">{selected.nome}</p>
              <p className="mt-1 inline-flex items-center gap-1">
                <UserRound size={14} />
                Login: {selected.login}
              </p>
            </div>

            <FormInput
              label="Nome da Barbearia"
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
            <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
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
            <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
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
