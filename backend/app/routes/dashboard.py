# backend/app/routes/dashboard.py
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.servico import Servico
from app.routes.deps import verificar_plano_premium
from app.schemas.dashboard import (
    ClientesResponse,
    FinanceiroResponse,
    HistoricoMes,
    ServicoMaisVendido,
    ServicosMaisVendidosResponse,
    TopCliente,
)

router = APIRouter(prefix="/dashboard")


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
                Agendamento.status == "confirmado",
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
    mes_col = func.date_format(Agendamento.data, "%Y-%m").label("mes")
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
            Agendamento.status == "confirmado",
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

    return FinanceiroResponse(
        faturamento_mes_atual=fat_atual,
        faturamento_mes_anterior=fat_anterior,
        variacao_percentual=variacao,
        ticket_medio=ticket_atual,
        total_agendamentos=total_atual,
        historico_12_meses=historico,
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
            Agendamento.status == "confirmado",
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
            Agendamento.status == "confirmado",
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
            Agendamento.status == "confirmado",
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
