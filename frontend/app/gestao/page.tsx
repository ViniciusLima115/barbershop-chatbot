"use client";

import { ComponentType, FormEvent, useEffect, useMemo, useState } from "react";
import {
  Agendamento,
  Barbeiro,
  Cliente,
  Servico,
  createAgendamento,
  createBarbeiro,
  createCliente,
  createServico,
  deleteAgendamento,
  deleteBarbeiro,
  deleteCliente,
  deleteServico,
  listAgendamentos,
  listBarbeiros,
  listClientes,
  listServicos,
  updateAgendamento,
  updateBarbeiro,
  updateCliente,
  updateServico,
} from "@/services/api";
import { useAuthSession } from "@/services/auth";
import Alert from "../components/Alert";
import Loading from "../components/Loading";
import Card from "../components/Card";
import Button from "../components/Button";
import FormInput from "../components/FormInput";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { Trash2, Edit2, Plus, RefreshCw, CalendarDays, Users, Scissors } from "lucide-react";

type Tab = "agendamentos" | "clientes" | "servicos";

const initialCliente = { nome: "", telefone: "" };
const initialServico = { nome: "", duracao_minutos: 40, preco: 40 };
const initialBarbeiro = { nome: "" };
const MAX_BARBEIROS_PREMIUM = 3;
const MAX_BARBEIROS_BASICO = 1;
const tabs: Array<{ key: Tab; label: string; icon: ComponentType<{ size?: number }> }> = [
  { key: "agendamentos", label: "Agendamentos", icon: CalendarDays },
  { key: "clientes", label: "Clientes", icon: Users },
  { key: "servicos", label: "Servicos", icon: Scissors },
];

function toBackendDateTime(localValue: string): string {
  return `${localValue}:00`;
}

function toDateTimeLocalInput(value: string): string {
  const normalized = value.trim().replace(" ", "T");
  const [datePart, timePart = ""] = normalized.split("T");
  const hhmm = timePart.slice(0, 5);
  return `${datePart}T${hhmm}`;
}

export default function GestaoPage() {
  const authSession = useAuthSession();
  const isPremiumPlan = authSession?.plan === "premium";
  const [tab, setTab] = useState<Tab>("agendamentos");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modal states
  const [showClienteModal, setShowClienteModal] = useState(false);
  const [showServicoModal, setShowServicoModal] = useState(false);
  const [showAgendamentoModal, setShowAgendamentoModal] = useState(false);
  const [showBarbeiroModal, setShowBarbeiroModal] = useState(false);

  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [barbeiros, setBarbeiros] = useState<Barbeiro[]>([]);
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);

  const [novoCliente, setNovoCliente] = useState(initialCliente);
  const [editClienteId, setEditClienteId] = useState<number | null>(null);

  const [novoServico, setNovoServico] = useState(initialServico);
  const [editServicoId, setEditServicoId] = useState<number | null>(null);
  const [novoBarbeiro, setNovoBarbeiro] = useState(initialBarbeiro);
  const [editBarbeiroId, setEditBarbeiroId] = useState<number | null>(null);

  const [formAgendamento, setFormAgendamento] = useState({
    clienteId: "",
    barbeiroId: "",
    servicoId: "",
    dataHora: "",
    status: "confirmado" as "pendente" | "confirmado" | "cancelado",
  });
  const [editAgendamentoId, setEditAgendamentoId] = useState<number | null>(null);

  const limiteBarbeiros = isPremiumPlan ? MAX_BARBEIROS_PREMIUM : MAX_BARBEIROS_BASICO;
  const limiteBarbeirosAtingido = barbeiros.length >= limiteBarbeiros;

  async function carregarTudo() {
    setLoading(true);
    setError(null);
    try {
      const [cs, ss, bs, as] = await Promise.all([
        listClientes(),
        listServicos(),
        listBarbeiros(),
        listAgendamentos(),
      ]);
      setClientes(cs);
      setServicos(ss);
      setBarbeiros(bs);
      setAgendamentos(as);
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
    const t = setTimeout(() => setSuccess(null), 4000);
    return () => clearTimeout(t);
  }, [success]);

  const clientesById = useMemo(
    () => Object.fromEntries(clientes.map((c) => [c.id, c])),
    [clientes]
  );

  const limparMensagens = () => {
    setError(null);
    setSuccess(null);
  };

  // CLIENTE HANDLERS
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
    if (cliente) {
      setEditClienteId(cliente.id);
      setNovoCliente({ nome: cliente.nome, telefone: cliente.telefone });
    } else {
      setEditClienteId(null);
      setNovoCliente(initialCliente);
    }
    setShowClienteModal(true);
  }

  // SERVIÇO HANDLERS
  async function submitServico(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    try {
      if (editServicoId) {
        await updateServico(editServicoId, novoServico);
        setSuccess("Serviço atualizado com sucesso!");
      } else {
        await createServico(novoServico);
        setSuccess("Serviço criado com sucesso!");
      }
      setNovoServico(initialServico);
      setEditServicoId(null);
      setShowServicoModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar serviço.");
    }
  }

  function abrirModalServico(servico?: Servico) {
    if (servico) {
      setEditServicoId(servico.id);
      setNovoServico({
        nome: servico.nome,
        duracao_minutos: servico.duracao_minutos,
        preco: servico.preco,
      });
    } else {
      setEditServicoId(null);
      setNovoServico(initialServico);
    }
    setShowServicoModal(true);
  }

  // BARBEIRO HANDLERS
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

      setNovoBarbeiro(initialBarbeiro);
      setEditBarbeiroId(null);
      setShowBarbeiroModal(false);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar barbeiro.");
    }
  }

  function abrirModalBarbeiro(barbeiro?: Barbeiro) {
    if (barbeiro) {
      setEditBarbeiroId(barbeiro.id);
      setNovoBarbeiro({ nome: barbeiro.nome });
    } else {
      setEditBarbeiroId(null);
      setNovoBarbeiro(initialBarbeiro);
    }

    setShowBarbeiroModal(true);
  }

  // AGENDAMENTO HANDLERS
  async function submitAgendamento(e: FormEvent) {
    e.preventDefault();
    limparMensagens();

    const cliente = clientesById[Number(formAgendamento.clienteId)];
    if (!cliente) {
      setError("Selecione um cliente válido.");
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

  // DELETE HANDLERS
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
    if (!confirm("Tem certeza que deseja remover este serviço?")) return;
    try {
      limparMensagens();
      await deleteServico(id);
      setSuccess("Serviço removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover serviço.");
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
    if (!confirm("Tem certeza que deseja remover este barbeiro?")) return;

    try {
      limparMensagens();
      await deleteBarbeiro(id);
      setSuccess("Barbeiro removido com sucesso!");
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover barbeiro.");
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="py-8">
        <div className="app-container space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Gestão</h1>
              <p className="mt-1 text-gray-600">
                Administre clientes, serviços e agendamentos
              </p>
            </div>
            <Button
              onClick={carregarTudo}
              variant="secondary"
              size="md"
            >
              <RefreshCw size={18} />
              Atualizar Dados
            </Button>
          </div>

          {/* Alerts */}
          {error && (
            <Alert
              type="error"
              message={error}
              onClose={() => setError(null)}
            />
          )}
          {success && (
            <Alert
              type="success"
              message={success}
              onClose={() => setSuccess(null)}
            />
          )}

          {/* Tab Navigation */}
          <nav
            className="rounded-2xl border border-gray-200 bg-gradient-to-r from-slate-100 to-gray-100 p-3"
            aria-label="Abas da gestao"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
              {tabs.map((item) => {
                const isActive = tab === item.key;
                const Icon = item.icon;

                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setTab(item.key)}
                    aria-current={isActive ? "page" : undefined}
                    className={`inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-lg border px-3 text-sm font-semibold shadow-sm transition sm:h-14 sm:flex-1 sm:gap-2 sm:rounded-xl sm:px-6 sm:text-base focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                      isActive
                        ? "border-blue-700 bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md"
                        : "border-gray-300 bg-white text-gray-800 hover:-translate-y-0.5 hover:border-gray-400 hover:bg-gray-50"
                    }`}
                  >
                    <Icon size={16} />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </nav>

          {/* Content */}
          {loading ? (
            <Loading />
          ) : (
            <>
              {/* CLIENTES TAB */}
              {tab === "clientes" && (
                <div className="space-y-6">
                  <div>
                    <Button variant="primary" onClick={() => abrirModalCliente()}>
                      <Plus size={18} />
                      Novo Cliente
                    </Button>
                  </div>

                  <Card title="Lista de Clientes">
                    {clientes.length === 0 ? (
                      <div className="text-center py-8">
                        <p className="text-gray-600">Nenhum cliente cadastrado</p>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => abrirModalCliente()}
                          className="mt-4"
                        >
                          Criar Primeiro Cliente
                        </Button>
                      </div>
                    ) : (
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Nome</th>
                              <th>Telefone</th>
                              <th className="text-right">Ações</th>
                            </tr>
                          </thead>
                          <tbody>
                            {clientes.map((c) => (
                              <tr key={c.id}>
                                <td className="font-medium">{c.nome}</td>
                                <td>{c.telefone}</td>
                                <td className="text-right">
                                  <div className="flex gap-2 justify-end">
                                    <button
                                      type="button"
                                      onClick={() => abrirModalCliente(c)}
                                      className="btn btn-secondary btn-sm"
                                    >
                                      <Edit2 size={16} />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => deleteClienteHandler(c.id)}
                                      className="btn btn-danger btn-sm"
                                    >
                                      <Trash2 size={16} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              )}

              {/* SERVIÇOS TAB */}
              {tab === "servicos" && (
                <div className="space-y-6">
                  <div>
                    <Button variant="primary" onClick={() => abrirModalServico()}>
                      <Plus size={18} />
                      Novo Serviço
                    </Button>
                  </div>

                  <Card title="Lista de Serviços">
                    {servicos.length === 0 ? (
                      <div className="text-center py-8">
                        <p className="text-gray-600">Nenhum serviço cadastrado</p>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => abrirModalServico()}
                          className="mt-4"
                        >
                          Criar Primeiro Serviço
                        </Button>
                      </div>
                    ) : (
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Nome</th>
                              <th>Duração</th>
                              <th>Preço</th>
                              <th className="text-right">Ações</th>
                            </tr>
                          </thead>
                          <tbody>
                            {servicos.map((s) => (
                              <tr key={s.id}>
                                <td className="font-medium">{s.nome}</td>
                                <td>{s.duracao_minutos} min</td>
                                <td className="text-green-600 font-semibold">
                                  R$ {s.preco.toFixed(2)}
                                </td>
                                <td className="text-right">
                                  <div className="flex gap-2 justify-end">
                                    <button
                                      type="button"
                                      onClick={() => abrirModalServico(s)}
                                      className="btn btn-secondary btn-sm"
                                    >
                                      <Edit2 size={16} />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => deleteServicoHandler(s.id)}
                                      className="btn btn-danger btn-sm"
                                    >
                                      <Trash2 size={16} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              )}

              {/* AGENDAMENTOS TAB */}
              {tab === "agendamentos" && (
                <div className="space-y-6">
                  <Card
                    title="Gestao de Barbeiros"
                    subtitle="Crie, edite e exclua barbeiros ativos diretamente neste painel"
                  >
                    <div className="space-y-4">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-sm text-gray-600">
                          Ativos: <strong>{barbeiros.length}</strong> / {limiteBarbeiros}
                        </p>
                        <Button variant="primary" onClick={() => abrirModalBarbeiro()}>
                          <Plus size={18} />
                          Adicionar Barbeiro
                        </Button>
                      </div>

                      {!isPremiumPlan && limiteBarbeirosAtingido && (
                        <p className="text-sm text-amber-600">
                          Deseja adicionar mais barbeiros? Faca o upgrade para o plano premium.
                        </p>
                      )}

                      {isPremiumPlan && limiteBarbeirosAtingido && (
                        <p className="text-sm text-amber-600">
                          Limite de 3 barbeiros ativos atingido.
                        </p>
                      )}

                      {barbeiros.length === 0 ? (
                        <p className="text-sm text-gray-600">Nenhum barbeiro cadastrado.</p>
                      ) : (
                        <div className="table-wrapper">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Nome</th>
                                <th className="text-right">Acoes</th>
                              </tr>
                            </thead>
                            <tbody>
                              {barbeiros.map((barbeiro) => (
                                <tr key={barbeiro.id}>
                                  <td className="font-medium">{barbeiro.nome}</td>
                                  <td className="text-right">
                                    <div className="flex justify-end gap-2">
                                      <button
                                        type="button"
                                        onClick={() => abrirModalBarbeiro(barbeiro)}
                                        className="btn btn-secondary btn-sm"
                                      >
                                        <Edit2 size={16} />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => deleteBarbeiroHandler(barbeiro.id)}
                                        className="btn btn-danger btn-sm"
                                      >
                                        <Trash2 size={16} />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </Card>

                  <div>
                    <Button
                      variant="primary"
                      onClick={() => abrirModalAgendamento()}
                      disabled={clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0}
                    >
                      <Plus size={18} />
                      Novo Agendamento
                    </Button>
                    {(clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0) && (
                      <p className="mt-2 text-sm text-amber-600">
                        ⚠️ Você precisa cadastrar clientes, serviços e barbeiros antes de fazer agendamentos
                      </p>
                    )}
                  </div>

                  <Card title="Lista de Agendamentos">
                    {agendamentos.length === 0 ? (
                      <div className="text-center py-8">
                        <p className="text-gray-600">Nenhum agendamento cadastrado</p>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => abrirModalAgendamento()}
                          className="mt-4"
                          disabled={clientes.length === 0 || servicos.length === 0 || barbeiros.length === 0}
                        >
                          Criar Primeiro Agendamento
                        </Button>
                      </div>
                    ) : (
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Cliente</th>
                              <th>Serviço</th>
                              <th>Horário</th>
                              <th>Status</th>
                              <th className="text-right">Ações</th>
                            </tr>
                          </thead>
                          <tbody>
                            {agendamentos.map((a) => (
                              <tr key={a.id}>
                                <td className="font-medium">{a.cliente_nome}</td>
                                <td>{a.servico_nome}</td>
                                <td>
                                  {new Date(
                                    a.data_hora_inicio
                                  ).toLocaleString("pt-BR")}
                                </td>
                                <td>
                                  <Badge
                                    status={
                                      a.status as
                                        | "confirmado"
                                        | "pendente"
                                        | "cancelado"
                                    }
                                  />
                                </td>
                                <td className="text-right">
                                  <div className="flex gap-2 justify-end">
                                    <button
                                      type="button"
                                      onClick={() =>
                                        abrirModalAgendamento(a)
                                      }
                                      className="btn btn-secondary btn-sm"
                                    >
                                      <Edit2 size={16} />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        deleteAgendamentoHandler(a.id)
                                      }
                                      className="btn btn-danger btn-sm"
                                    >
                                      <Trash2 size={16} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* MODALS */}

      {/* Cliente Modal */}
      <Modal
        isOpen={showClienteModal}
        onClose={() => setShowClienteModal(false)}
        title={editClienteId ? "Editar Cliente" : "Novo Cliente"}
      >
        <form onSubmit={submitCliente} className="space-y-4">
          <FormInput
            label="Nome do Cliente"
            placeholder="Ex: João Silva"
            value={novoCliente.nome}
            onChange={(e) =>
              setNovoCliente((p) => ({ ...p, nome: e.target.value }))
            }
            required
          />
          <FormInput
            label="Telefone"
            placeholder="Ex: (11) 98765-4321"
            value={novoCliente.telefone}
            onChange={(e) =>
              setNovoCliente((p) => ({ ...p, telefone: e.target.value }))
            }
            required
          />
          <div className="flex gap-3 justify-end pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => setShowClienteModal(false)}
            >
              Cancelar
            </Button>
            <Button variant="primary" type="submit">
              {editClienteId ? "Atualizar" : "Criar"} Cliente
            </Button>
          </div>
        </form>
      </Modal>

      {/* Serviço Modal */}
      <Modal
        isOpen={showServicoModal}
        onClose={() => setShowServicoModal(false)}
        title={editServicoId ? "Editar Serviço" : "Novo Serviço"}
      >
        <form onSubmit={submitServico} className="space-y-4">
          <FormInput
            label="Nome do Serviço"
            placeholder="Ex: Corte Básico"
            value={novoServico.nome}
            onChange={(e) =>
              setNovoServico((p) => ({ ...p, nome: e.target.value }))
            }
            required
          />
          <FormInput
            label="Duração (minutos)"
            type="number"
            placeholder="Ex: 40"
            value={novoServico.duracao_minutos}
            onChange={(e) =>
              setNovoServico((p) => ({
                ...p,
                duracao_minutos: Number(e.target.value),
              }))
            }
            required
          />
          <FormInput
            label="Preço (R$)"
            type="number"
            step="0.01"
            placeholder="Ex: 40.00"
            value={novoServico.preco}
            onChange={(e) =>
              setNovoServico((p) => ({
                ...p,
                preco: Number(e.target.value),
              }))
            }
            required
          />
          <div className="flex gap-3 justify-end pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => setShowServicoModal(false)}
            >
              Cancelar
            </Button>
            <Button variant="primary" type="submit">
              {editServicoId ? "Atualizar" : "Criar"} Serviço
            </Button>
          </div>
        </form>
      </Modal>

      {/* Barbeiro Modal */}
      <Modal
        isOpen={showBarbeiroModal}
        onClose={() => setShowBarbeiroModal(false)}
        title={editBarbeiroId ? "Editar Barbeiro" : "Novo Barbeiro"}
      >
        <form onSubmit={submitBarbeiro} className="space-y-4">
          <FormInput
            label="Nome do Barbeiro"
            placeholder="Ex: Carlos"
            value={novoBarbeiro.nome}
            onChange={(e) =>
              setNovoBarbeiro((p) => ({ ...p, nome: e.target.value }))
            }
            required
          />

          <div className="flex gap-3 justify-end pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => setShowBarbeiroModal(false)}
            >
              Cancelar
            </Button>
            <Button variant="primary" type="submit">
              {editBarbeiroId ? "Atualizar" : "Criar"} Barbeiro
            </Button>
          </div>
        </form>
      </Modal>

      {/* Agendamento Modal */}
      <Modal
        isOpen={showAgendamentoModal}
        onClose={() => setShowAgendamentoModal(false)}
        title={editAgendamentoId ? "Editar Agendamento" : "Novo Agendamento"}
        size="lg"
      >
        <form onSubmit={submitAgendamento} className="space-y-4">
          <FormInput
            label="Cliente"
            as="select"
            value={formAgendamento.clienteId}
            onChange={(e) =>
              setFormAgendamento((p) => ({
                ...p,
                clienteId: e.target.value,
              }))
            }
            required
          >
            <option value="">Selecione um cliente</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome} ({c.telefone})
              </option>
            ))}
          </FormInput>

          <FormInput
            label="Barbeiro"
            as="select"
            value={formAgendamento.barbeiroId}
            onChange={(e) =>
              setFormAgendamento((p) => ({
                ...p,
                barbeiroId: e.target.value,
              }))
            }
            required
          >
            <option value="">Selecione um barbeiro</option>
            {barbeiros.map((b) => (
              <option key={b.id} value={b.id}>
                {b.nome}
              </option>
            ))}
          </FormInput>

          <FormInput
            label="Serviço"
            as="select"
            value={formAgendamento.servicoId}
            onChange={(e) =>
              setFormAgendamento((p) => ({
                ...p,
                servicoId: e.target.value,
              }))
            }
            required
          >
            <option value="">Selecione um serviço</option>
            {servicos.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nome} ({s.duracao_minutos} min - R$ {s.preco.toFixed(2)})
              </option>
            ))}
          </FormInput>

          <FormInput
            label="Data e Hora"
            type="datetime-local"
            value={formAgendamento.dataHora}
            onChange={(e) =>
              setFormAgendamento((p) => ({
                ...p,
                dataHora: e.target.value,
              }))
            }
            required
          />

          <FormInput
            label="Status"
            as="select"
            value={formAgendamento.status}
            onChange={(e) =>
              setFormAgendamento((p) => ({
                ...p,
                status: e.target.value as
                  | "pendente"
                  | "confirmado"
                  | "cancelado",
              }))
            }
          >
            <option value="confirmado">✓ Confirmado</option>
            <option value="pendente">⏳ Pendente</option>
            <option value="cancelado">✗ Cancelado</option>
          </FormInput>

          <div className="flex gap-3 justify-end pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => setShowAgendamentoModal(false)}
            >
              Cancelar
            </Button>
            <Button variant="primary" type="submit">
              {editAgendamentoId ? "Atualizar" : "Criar"} Agendamento
            </Button>
          </div>
        </form>
      </Modal>
    </main>
  );
}

