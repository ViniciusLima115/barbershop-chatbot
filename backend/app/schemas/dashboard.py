# backend/app/schemas/dashboard.py
from pydantic import BaseModel


class HistoricoMes(BaseModel):
    mes: str        # "2026-01"
    faturamento: float
    total_agendamentos: int


class FinanceiroResponse(BaseModel):
    faturamento_mes_atual: float
    faturamento_mes_anterior: float
    variacao_percentual: float | None   # None se mês anterior = 0
    ticket_medio: float
    total_agendamentos: int
    historico_12_meses: list[HistoricoMes]


class ServicoMaisVendido(BaseModel):
    nome: str
    preco: float
    total_vendas: int
    receita_total: float


class ServicosMaisVendidosResponse(BaseModel):
    servicos: list[ServicoMaisVendido]


class TopCliente(BaseModel):
    nome: str
    telefone: str
    total_visitas: int
    valor_total_gasto: float
    ultima_visita: str      # ISO date "2026-03-21"


class ClientesResponse(BaseModel):
    total_clientes: int
    clientes_novos: int         # só 1 visita no período
    clientes_recorrentes: int   # mais de 1 visita
    taxa_cancelamento: float    # 0.0 a 100.0 (percentual)
    top_5_clientes: list[TopCliente]


class ResumoMes(BaseModel):
    agendamentos: int
    faturamento: float
    ticket_medio: float
    ocupacao: int           # 0–100 (percentual inteiro)


class DiaSemana(BaseModel):
    dia: str                # "Seg", "Ter", ..., "Dom"
    clientes: int


class HorarioCheio(BaseModel):
    hora: str               # "09:00", "18:00", etc.
    atendimentos: int


class ServicoAnalise(BaseModel):
    nome: str
    total: int


class ClientesAnalise(BaseModel):
    novos: int
    recorrentes: int
    cancelamentos: int
    no_show: int


class AnaliseResponse(BaseModel):
    resumo: ResumoMes
    semana: list[DiaSemana]
    horarios: list[HorarioCheio]
    servicos: list[ServicoAnalise]
    clientes: ClientesAnalise


# ── Dashboard Básico (plano Básico) ──────────────────────────────────────────
class ResumoBasicoResponse(BaseModel):
    total_agendamentos_mes: int
    agendamentos_confirmados_mes: int
    agendamentos_cancelados_mes: int
    faturamento_estimado_mes: float
    total_clientes_unicos_mes: int
    agendamentos_hoje: int
