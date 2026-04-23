from pydantic import BaseModel


class HistoricoMes(BaseModel):
    mes: str
    faturamento: float
    total_agendamentos: int


class FinanceiroResponse(BaseModel):
    faturamento_mes_atual: float
    faturamento_mes_anterior: float
    variacao_percentual: float | None
    ticket_medio: float
    total_agendamentos: int
    historico_12_meses: list[HistoricoMes]
    valor_recebido_hoje: float = 0
    agendamentos_pagos: int = 0
    taxa_conversao_pagamento: float | None = None
    pagamentos_pendentes: int = 0
    pagamentos_expirados: int = 0


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
    ultima_visita: str


class ClientesResponse(BaseModel):
    total_clientes: int
    clientes_novos: int
    clientes_recorrentes: int
    taxa_cancelamento: float
    top_5_clientes: list[TopCliente]


class ResumoMes(BaseModel):
    agendamentos: int
    faturamento: float
    ticket_medio: float
    ocupacao: int


class DiaSemana(BaseModel):
    dia: str
    clientes: int


class HorarioCheio(BaseModel):
    hora: str
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


class ResumoBasicoResponse(BaseModel):
    total_agendamentos_mes: int
    agendamentos_confirmados_mes: int
    agendamentos_cancelados_mes: int
    faturamento_estimado_mes: float
    total_clientes_unicos_mes: int
    agendamentos_hoje: int
    valor_recebido_hoje: float = 0
    pagamentos_pendentes: int = 0
    pagamentos_expirados: int = 0
