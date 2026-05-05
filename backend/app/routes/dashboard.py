# backend/app/routes/dashboard.py
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.pagamento import Pagamento
from app.models.servico import Servico
from app.routes.deps import verificar_plano_minimo_basico, verificar_plano_premium
from app.schemas.dashboard import (
    AnaliseResponse,
    ClientesAnalise,
    ClientesResponse,
    DiaSemana,
    FinanceiroResponse,
    HistoricoMes,
    HorarioCheio,
    ResumoBasicoResponse,
    ResumoMes,
    ServicoAnalise,
    ServicoMaisVendido,
    ServicosMaisVendidosResponse,
    TopCliente,
)

# Statuses que representam um atendimento realizado (conta no faturamento/analytics)
_ATENDIDO = ("confirmado", "compareceu")

router = APIRouter(prefix="/dashboard")


@router.get("/{barbearia_id}/resumo-basico", response_model=ResumoBasicoResponse)
def resumo_basico(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_minimo_basico),
    db: Session = Depends(get_db),
):
    """Dashboard simplificado acessível pelos planos Básico e Premium."""
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    try:
        return _resumo_basico(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _resumo_basico(db: Session, tenant_id: int) -> ResumoBasicoResponse:
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)
    inicio_hoje_dt = datetime.combine(hoje, datetime.min.time())
    fim_hoje_dt = inicio_hoje_dt + timedelta(days=1)

    total_mes = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar() or 0
    )

    confirmados_mes = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar() or 0
    )

    cancelados_mes = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "cancelado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar() or 0
    )

    faturamento = (
        db.query(func.coalesce(func.sum(Servico.preco), 0.0))
        .select_from(Agendamento)
        .join(Servico, Servico.id == Agendamento.servico_id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar() or 0.0
    )

    clientes_unicos = (
        db.query(func.count(func.distinct(Agendamento.cliente_telefone)))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar() or 0
    )

    agendamentos_hoje = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.data == hoje,
            Agendamento.status.in_(["confirmado", "pendente"]),
        )
        .scalar() or 0
    )

    valor_recebido_hoje = (
        db.query(func.coalesce(func.sum(Pagamento.amount), 0.0))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "approved",
            Pagamento.paid_at.is_not(None),
            Pagamento.paid_at >= inicio_hoje_dt,
            Pagamento.paid_at < fim_hoje_dt,
        )
        .scalar() or 0.0
    )

    pagamentos_pendentes = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "pending",
        )
        .scalar() or 0
    )

    pagamentos_expirados = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "expired",
            Pagamento.created_at >= datetime.combine(inicio_mes, datetime.min.time()),
        )
        .scalar() or 0
    )

    return ResumoBasicoResponse(
        total_agendamentos_mes=int(total_mes),
        agendamentos_confirmados_mes=int(confirmados_mes),
        agendamentos_cancelados_mes=int(cancelados_mes),
        faturamento_estimado_mes=float(faturamento),
        total_clientes_unicos_mes=int(clientes_unicos),
        agendamentos_hoje=int(agendamentos_hoje),
        valor_recebido_hoje=float(valor_recebido_hoje),
        pagamentos_pendentes=int(pagamentos_pendentes),
        pagamentos_expirados=int(pagamentos_expirados),
    )


@router.get("/{barbearia_id}/financeiro", response_model=FinanceiroResponse)
def financeiro(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    try:
        return _financeiro(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _financeiro(db: Session, tenant_id: int) -> FinanceiroResponse:
    hoje = date.today()
    inicio_atual = hoje.replace(day=1)
    inicio_atual_dt = datetime.combine(inicio_atual, datetime.min.time())
    inicio_hoje_dt = datetime.combine(hoje, datetime.min.time())
    fim_hoje_dt = inicio_hoje_dt + timedelta(days=1)
    # Primeiro dia do mês anterior
    ultimo_dia_anterior = inicio_atual - timedelta(days=1)
    inicio_anterior = ultimo_dia_anterior.replace(day=1)

    def _agg(inicio: date, fim: date):
        """Retorna (faturamento, total_agendamentos, ticket_medio) para o período."""
        row = (
            db.query(
                func.coalesce(func.sum(Servico.preco), 0.0).label("fat"),
                func.count(Agendamento.id).label("total"),
                func.coalesce(func.avg(Servico.preco), 0.0).label("ticket"),
            )
            .select_from(Agendamento)
            .join(Servico, Servico.id == Agendamento.servico_id)
            .filter(
                Agendamento.barbearia_id == tenant_id,
                Agendamento.status.in_(_ATENDIDO),
                Agendamento.data >= inicio,
                Agendamento.data <= fim,
            )
            .first()
        )
        return float(row.fat), int(row.total), float(row.ticket)

    fat_atual, total_atual, ticket_atual = _agg(inicio_atual, hoje)
    fat_anterior, _, _ = _agg(inicio_anterior, ultimo_dia_anterior)

    if fat_anterior > 0:
        variacao = ((fat_atual - fat_anterior) / fat_anterior) * 100.0
    else:
        variacao = None

    # Histórico dos últimos 12 meses (agrupado por mês)
    data_12m = hoje - timedelta(days=365)
    mes_col = func.to_char(Agendamento.data, "YYYY-MM").label("mes")
    historico_rows = (
        db.query(
            mes_col,
            func.coalesce(func.sum(Servico.preco), 0.0).label("faturamento"),
            func.count(Agendamento.id).label("total_agendamentos"),
        )
        .select_from(Agendamento)
        .join(Servico, Servico.id == Agendamento.servico_id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= data_12m,
        )
        .group_by(mes_col)
        .order_by(mes_col)
        .all()
    )

    historico = [
        HistoricoMes(
            mes=row.mes,
            faturamento=float(row.faturamento),
            total_agendamentos=int(row.total_agendamentos),
        )
        for row in historico_rows
    ]

    valor_recebido_hoje = (
        db.query(func.coalesce(func.sum(Pagamento.amount), 0.0))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "approved",
            Pagamento.paid_at.is_not(None),
            Pagamento.paid_at >= inicio_hoje_dt,
            Pagamento.paid_at < fim_hoje_dt,
        )
        .scalar() or 0.0
    )

    agendamentos_pagos = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "approved",
            Pagamento.created_at >= inicio_atual_dt,
        )
        .scalar() or 0
    )

    total_pagamentos_iniciados = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.created_at >= inicio_atual_dt,
        )
        .scalar() or 0
    )

    pagamentos_pendentes = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "pending",
        )
        .scalar() or 0
    )

    pagamentos_expirados = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == tenant_id,
            Pagamento.status == "expired",
            Pagamento.created_at >= inicio_atual_dt,
        )
        .scalar() or 0
    )

    taxa_conversao_pagamento = (
        (agendamentos_pagos / total_pagamentos_iniciados) * 100.0
        if total_pagamentos_iniciados > 0
        else None
    )

    return FinanceiroResponse(
        faturamento_mes_atual=fat_atual,
        faturamento_mes_anterior=fat_anterior,
        variacao_percentual=variacao,
        ticket_medio=ticket_atual,
        total_agendamentos=total_atual,
        historico_12_meses=historico,
        valor_recebido_hoje=float(valor_recebido_hoje),
        agendamentos_pagos=int(agendamentos_pagos),
        taxa_conversao_pagamento=taxa_conversao_pagamento,
        pagamentos_pendentes=int(pagamentos_pendentes),
        pagamentos_expirados=int(pagamentos_expirados),
    )


@router.get("/{barbearia_id}/servicos-mais-vendidos", response_model=ServicosMaisVendidosResponse)
def servicos_mais_vendidos(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    try:
        return _servicos_mais_vendidos(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _servicos_mais_vendidos(db: Session, tenant_id: int) -> ServicosMaisVendidosResponse:
    data_30d = date.today() - timedelta(days=30)

    rows = (
        db.query(
            Servico.nome,
            Servico.preco,
            func.count(Agendamento.id).label("total_vendas"),
            func.coalesce(func.sum(Servico.preco), 0.0).label("receita_total"),
        )
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= data_30d,
        )
        .group_by(Servico.id, Servico.nome, Servico.preco)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )

    return ServicosMaisVendidosResponse(
        servicos=[
            ServicoMaisVendido(
                nome=row.nome,
                preco=float(row.preco),
                total_vendas=int(row.total_vendas),
                receita_total=float(row.receita_total),
            )
            for row in rows
        ]
    )


@router.get("/{barbearia_id}/clientes", response_model=ClientesResponse)
def clientes(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    try:
        return _clientes(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _clientes(db: Session, tenant_id: int) -> ClientesResponse:
    hoje = date.today()
    data_30d = hoje - timedelta(days=30)

    # Frequência de clientes nos últimos 30 dias (confirmados)
    freq_rows = (
        db.query(
            Agendamento.cliente_telefone,
            func.count(Agendamento.id).label("visitas"),
        )
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= data_30d,
        )
        .group_by(Agendamento.cliente_telefone)
        .all()
    )

    total_clientes = len(freq_rows)
    clientes_novos = sum(1 for r in freq_rows if r.visitas == 1)
    clientes_recorrentes = sum(1 for r in freq_rows if r.visitas > 1)

    # Taxa de cancelamento nos últimos 30 dias
    total_periodo = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.data >= data_30d,
        )
        .scalar()
        or 0
    )
    total_cancelados = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "cancelado",
            Agendamento.data >= data_30d,
        )
        .scalar()
        or 0
    )
    taxa_cancelamento = (total_cancelados / total_periodo * 100.0) if total_periodo > 0 else 0.0

    # Top 5 clientes mais frequentes (all-time)
    top_rows = (
        db.query(
            Agendamento.cliente_nome,
            Agendamento.cliente_telefone,
            func.count(Agendamento.id).label("total_visitas"),
            func.coalesce(func.sum(Servico.preco), 0.0).label("valor_total"),
            func.max(Agendamento.data).label("ultima_visita"),
        )
        .join(Servico, Servico.id == Agendamento.servico_id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
        )
        .group_by(Agendamento.cliente_telefone, Agendamento.cliente_nome)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )

    return ClientesResponse(
        total_clientes=total_clientes,
        clientes_novos=clientes_novos,
        clientes_recorrentes=clientes_recorrentes,
        taxa_cancelamento=round(taxa_cancelamento, 1),
        top_5_clientes=[
            TopCliente(
                nome=row.cliente_nome or "—",
                telefone=row.cliente_telefone or "—",
                total_visitas=int(row.total_visitas),
                valor_total_gasto=float(row.valor_total),
                ultima_visita=row.ultima_visita.isoformat() if row.ultima_visita else "—",
            )
            for row in top_rows
        ],
    )


# Mapeamento: índice = Python weekday() (0=Seg, ..., 6=Dom)
_DIA_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@router.get("/{barbearia_id}/analise", response_model=AnaliseResponse)
def analise(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
    try:
        return _analise(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


def _analise(db: Session, tenant_id: int) -> AnaliseResponse:
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)
    agora = datetime.now()

    # ── Resumo: confirmados no mês atual ──────────────────────────────────────
    row = (
        db.query(
            func.count(Agendamento.id).label("total"),
            func.coalesce(func.sum(Servico.preco), 0.0).label("fat"),
            func.coalesce(func.avg(Servico.preco), 0.0).label("ticket"),
        )
        .select_from(Agendamento)
        .join(Servico, Servico.id == Agendamento.servico_id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .first()
    )
    total_confirmados = int(row.total)
    faturamento = float(row.fat)
    ticket_medio = float(row.ticket)

    total_cancelados = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "cancelado",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar()
        or 0
    )

    # Conta no_show explícitos + pendentes passados (heurística)
    total_no_show = (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "no_show",
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .scalar()
        or 0
    )
    total_no_show += (
        db.query(func.count(Agendamento.id))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status == "pendente",
            Agendamento.data_hora_inicio < agora,
            Agendamento.data >= inicio_mes,
        )
        .scalar()
        or 0
    )

    total_demanda = total_confirmados + total_cancelados + total_no_show
    ocupacao = round(total_confirmados / total_demanda * 100) if total_demanda > 0 else 0

    resumo = ResumoMes(
        agendamentos=total_confirmados,
        faturamento=faturamento,
        ticket_medio=ticket_medio,
        ocupacao=ocupacao,
    )

    # ── Semana: confirmados agrupados por dia da semana ───────────────────────
    # extract("dow"): 0=Dom, 1=Seg, ..., 6=Sáb (PostgreSQL e SQLite via SQLAlchemy)
    dow_col = func.extract("dow", Agendamento.data).label("dow")
    semana_rows = (
        db.query(dow_col, func.count(Agendamento.id).label("total"))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(dow_col)
        .all()
    )
    contagem_semana = {int(r.dow): int(r.total) for r in semana_rows}
    # Ordem Seg→Dom; (dow-1)%7 converte SQL dow para índice de _DIA_LABELS
    semana = [
        DiaSemana(dia=_DIA_LABELS[(dow - 1) % 7], clientes=contagem_semana[dow])
        for dow in [1, 2, 3, 4, 5, 6, 0]
        if dow in contagem_semana
    ]

    # ── Horários mais cheios: top 5 ───────────────────────────────────────────
    hora_col = func.extract("hour", Agendamento.hora_inicio).label("hora")
    horario_rows = (
        db.query(hora_col, func.count(Agendamento.id).label("total"))
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(hora_col)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )
    horarios = [
        HorarioCheio(hora=f"{int(r.hora):02d}:00", atendimentos=int(r.total))
        for r in horario_rows
    ]

    # ── Serviços mais vendidos: top 5 ─────────────────────────────────────────
    servico_rows = (
        db.query(Servico.nome, func.count(Agendamento.id).label("total"))
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(Servico.id, Servico.nome)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
        .all()
    )
    servicos = [ServicoAnalise(nome=r.nome, total=int(r.total)) for r in servico_rows]

    # ── Clientes ──────────────────────────────────────────────────────────────
    freq_rows = (
        db.query(
            Agendamento.cliente_telefone,
            func.count(Agendamento.id).label("visitas"),
        )
        .filter(
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(_ATENDIDO),
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(Agendamento.cliente_telefone)
        .all()
    )
    novos = sum(1 for r in freq_rows if r.visitas == 1)
    recorrentes = sum(1 for r in freq_rows if r.visitas > 1)

    clientes = ClientesAnalise(
        novos=novos,
        recorrentes=recorrentes,
        cancelamentos=total_cancelados,
        no_show=total_no_show,
    )

    return AnaliseResponse(
        resumo=resumo,
        semana=semana,
        horarios=horarios,
        servicos=servicos,
        clientes=clientes,
    )
