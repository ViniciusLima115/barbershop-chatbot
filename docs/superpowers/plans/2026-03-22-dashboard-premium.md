# Dashboard Premium Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma seção `/dashboard` premium ao painel Virtual Barber com analytics financeiros, ranking de serviços e análise de clientes, protegidos por verificação de plano no backend.

**Architecture:** Backend FastAPI com 3 endpoints analíticos protegidos por nova dependency `verificar_plano_premium`; frontend Next.js com página `/dashboard` usando recharts para gráficos, com gating de plano (mostra tela de upgrade para plano "basico"). O campo `barbearia.plano` já existe na tabela com valores `"basico"` e `"premium"`.

**Tech Stack:** FastAPI, SQLAlchemy (ORM queries), Pydantic v2, Next.js 16, React 19, CSS Modules, recharts, lucide-react

---

## File Map

### Backend (criar/modificar)
| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Criar | `backend/app/schemas/dashboard.py` | Pydantic response models para os 3 endpoints |
| Modificar | `backend/app/routes/deps.py` | Adicionar `verificar_plano_premium` dependency |
| Criar | `backend/app/routes/dashboard.py` | Router com 3 endpoints analíticos |
| Modificar | `backend/app/main.py` | Registrar `dashboard.router` |

### Frontend (criar/modificar)
| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Criar | `frontend/app/dashboard/page.tsx` | Página completa de dashboard |
| Criar | `frontend/app/dashboard/page.module.css` | Estilos da página |
| Modificar | `frontend/services/api.ts` | Adicionar tipos + funções para 3 endpoints |
| Modificar | `frontend/app/components/Header.tsx` | Adicionar item "Dashboard" condicional (premium) |

---

## Task 1: Backend — Schemas Pydantic do Dashboard

**Files:**
- Create: `backend/app/schemas/dashboard.py`

### Context
Pydantic models para tipagem dos responses. Seguir padrão dos outros schemas do projeto (`backend/app/schemas/agendamento.py`).

- [ ] **Step 1: Criar o arquivo de schemas**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/dashboard.py
git commit -m "feat: schemas pydantic para endpoints de dashboard premium"
```

---

## Task 2: Backend — Dependency `verificar_plano_premium`

**Files:**
- Modify: `backend/app/routes/deps.py`

### Context
Adicionar nova função ao arquivo de dependências. Padrão existente: `tenant_id_from_header` já valida JWT e extrai tenant. A nova dependency recebe o `tenant_id` já validado e adiciona a verificação de plano. Retorna `int` (tenant_id) para seguir mesmo padrão de `tenant_id_from_header`.

- [ ] **Step 1: Ler o arquivo deps.py atual**

```bash
cat backend/app/routes/deps.py
```

- [ ] **Step 2: Adicionar `verificar_plano_premium` ao deps.py**

Adicionar **ao final** do arquivo `backend/app/routes/deps.py`:

```python
def verificar_plano_premium(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> int:
    barbearia = db.query(Barbearia.plano).filter(Barbearia.id == tenant_id).first()
    if not barbearia or barbearia.plano != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponivel apenas para o plano Premium.",
        )
    return tenant_id
```

- [ ] **Step 3: Verificar que os imports existentes cobrem as necessidades**

O arquivo já importa `Barbearia`, `Session`, `Depends`, `HTTPException`, `status` — nenhum import adicional necessário.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/deps.py
git commit -m "feat: dependency verificar_plano_premium para rotas restritas"
```

---

## Task 3: Backend — Endpoints de Dashboard

**Files:**
- Create: `backend/app/routes/dashboard.py`
- Modify: `backend/app/main.py`

### Context
3 endpoints GET em `/dashboard/{barbearia_id}/`. Usam `verificar_plano_premium` como dependency (que por sua vez usa `tenant_id_from_header`).

**Segurança:** o `barbearia_id` do path deve ser validado contra o `tenant_id` vindo da dependency, para evitar que um usuário chame `/dashboard/999/financeiro` com header de outro tenant. Adicionar verificação explícita no início de cada endpoint.

Modelo `Agendamento` tem: `data` (Date), `status` (str), `barbearia_id`, `servico_id`, `cliente_telefone`, `cliente_nome`.
Modelo `Servico` tem: `id`, `nome`, `preco` (float).

Padrão das queries: usar `db.query(...)` com JOIN explícito, filtrar por `barbearia_id` + `status == "confirmado"` + range de datas.

- [ ] **Step 1: Criar `backend/app/routes/dashboard.py`**

```python
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
```

- [ ] **Step 2: Registrar o router em `main.py`**

Em `backend/app/main.py`:

1. Adicionar import no bloco de imports das rotas:
```python
from app.routes import (
    agenda,
    agendamentos,
    auth,
    barbearia_funcionamento,
    barbearias,
    barbeiros,
    chatbot,
    clientes,
    dashboard,       # ← adicionar esta linha
    internal,
    public,
    servicos,
    webhook,
    webhooks,
    whatsapp,
)
```

2. Adicionar `app.include_router(dashboard.router)` após a linha `app.include_router(agenda.router)`:
```python
app.include_router(agenda.router)
app.include_router(dashboard.router)   # ← adicionar esta linha
```

- [ ] **Step 3: Testar manualmente os endpoints**

```bash
# Subir o backend localmente
cd backend
uvicorn app.main:app --reload

# Testar autenticação (obter token)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "SEU_EMAIL", "senha": "SUA_SENHA"}'

# Testar endpoint financeiro (substituir TOKEN e BARBEARIA_ID)
curl http://localhost:8000/dashboard/BARBEARIA_ID/financeiro \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Barbearia-Id: BARBEARIA_ID"

# Esperado: JSON com faturamento_mes_atual, historico_12_meses, etc.
# Se plano != premium → 403 "Recurso disponivel apenas para o plano Premium."
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/dashboard.py backend/app/main.py
git commit -m "feat: endpoints de analytics /dashboard/{id}/financeiro|servicos-mais-vendidos|clientes"
```

---

## Task 4: Frontend — Instalar recharts + Funções de API

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Modify: `frontend/services/api.ts`

### Context
Instalar recharts para gráficos. Adicionar tipos TypeScript e funções `apiFetch` para os 3 endpoints. Padrão existente no `api.ts`: `apiFetch(path)` envia `Authorization` + `X-Barbearia-Id` headers automaticamente.

- [ ] **Step 1: Instalar recharts**

```bash
cd frontend
npm install recharts
```

Verificar que apareceu em `package.json` em `dependencies`.

- [ ] **Step 2: Ler o final de `frontend/services/api.ts`**

```bash
tail -50 frontend/services/api.ts
```

Para entender o padrão de `apiFetch` e o bloco de funções existentes.

- [ ] **Step 3: Adicionar tipos e funções de dashboard ao `api.ts`**

Adicionar **ao final** de `frontend/services/api.ts`:

```typescript
// ─── DASHBOARD PREMIUM ───────────────────────────────────────────────────────

export type HistoricoMes = {
  mes: string;
  faturamento: number;
  total_agendamentos: number;
};

export type FinanceiroResponse = {
  faturamento_mes_atual: number;
  faturamento_mes_anterior: number;
  variacao_percentual: number | null;
  ticket_medio: number;
  total_agendamentos: number;
  historico_12_meses: HistoricoMes[];
};

export type ServicoMaisVendido = {
  nome: string;
  preco: number;
  total_vendas: number;
  receita_total: number;
};

export type ServicosMaisVendidosResponse = {
  servicos: ServicoMaisVendido[];
};

export type TopCliente = {
  nome: string;
  telefone: string;
  total_visitas: number;
  valor_total_gasto: number;
  ultima_visita: string;
};

export type ClientesResponse = {
  total_clientes: number;
  clientes_novos: number;
  clientes_recorrentes: number;
  taxa_cancelamento: number;
  top_5_clientes: TopCliente[];
};

export async function getDashboardFinanceiro(barbeariaId: string): Promise<FinanceiroResponse> {
  return apiFetch(`/dashboard/${barbeariaId}/financeiro`);
}

export async function getDashboardServicos(barbeariaId: string): Promise<ServicosMaisVendidosResponse> {
  return apiFetch(`/dashboard/${barbeariaId}/servicos-mais-vendidos`);
}

export async function getDashboardClientes(barbeariaId: string): Promise<ClientesResponse> {
  return apiFetch(`/dashboard/${barbeariaId}/clientes`);
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/services/api.ts
git commit -m "feat: tipos e funções de API para endpoints de dashboard premium"
```

---

## Task 5: Frontend — Página `/dashboard`

**Files:**
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/app/dashboard/page.module.css`

### Context
Página "use client". Busca sessão com `useAuthSession()`. Se `session.plan !== "premium"`, renderiza tela de upgrade. Caso contrário, faz 3 chamadas paralelas com `Promise.all` e renderiza os cards/gráficos.

Padrões do projeto:
- Classe `app-container` (wrapper de max-width do globals.css)
- CSS Modules com variáveis `--canvas`, `--surface`, `--ink`, `--accent`, etc.
- `"use client"` no topo, `useState` + `useEffect` para data fetching
- lucide-react para ícones
- Formatação: `new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(valor)`

O gráfico de linha será: `<LineChart>` do recharts com `historico_12_meses` — eixo X = mês, eixo Y = faturamento.

- [ ] **Step 1: Criar `frontend/app/dashboard/page.module.css`**

```css
/* frontend/app/dashboard/page.module.css */
.page {
  min-height: 100vh;
  background: var(--canvas);
  color: var(--ink);
}

.shell {
  padding: 32px 0 80px;
}

/* ── Tela de upgrade ──────────────────────────────────────── */
.upgradePage {
  display: grid;
  place-items: center;
  min-height: 60vh;
  padding: 40px 20px;
}

.upgradeCard {
  max-width: 520px;
  width: 100%;
  padding: 48px 40px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-md);
  text-align: center;
  display: grid;
  gap: 20px;
}

.upgradeIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  margin: 0 auto;
}

.upgradeTitle {
  margin: 0;
  font-size: 1.8rem;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.upgradeText {
  margin: 0;
  color: var(--ink-muted);
  line-height: 1.65;
}

/* ── Hero ─────────────────────────────────────────────────── */
.hero {
  padding: 28px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-dark);
}

.heroTitle {
  margin: 0 0 6px;
  font-size: clamp(2rem, 4vw, 3.2rem);
  line-height: 0.96;
  letter-spacing: -0.04em;
}

.heroSubtitle {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.95rem;
  line-height: 1.6;
}

/* ── Stats grid ───────────────────────────────────────────── */
.statsGrid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.statCard {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 20px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.statIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  color: var(--accent-dark);
  background: var(--accent-soft);
}

.statContent {
  display: grid;
  gap: 3px;
}

.statLabel {
  color: var(--ink-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.statValue {
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.1;
}

.statHelper {
  font-size: 0.82rem;
  color: var(--ink-muted);
}

.variacaoPositiva {
  color: var(--success);
}

.variacaoNegativa {
  color: var(--danger);
}

/* ── Content grid ─────────────────────────────────────────── */
.contentGrid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
  margin-top: 20px;
  align-items: start;
}

/* ── Panels ───────────────────────────────────────────────── */
.panel {
  padding: 24px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.panelTitle {
  margin: 0 0 20px;
  font-size: 1.3rem;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

/* ── Gráfico ──────────────────────────────────────────────── */
.chartWrap {
  width: 100%;
  height: 260px;
}

/* ── Serviços ─────────────────────────────────────────────── */
.servicosList {
  display: grid;
  gap: 12px;
}

.servicoItem {
  display: grid;
  gap: 6px;
}

.servicoHeader {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.servicoNome {
  font-size: 0.9rem;
  font-weight: 600;
}

.servicoVendas {
  font-size: 0.82rem;
  color: var(--ink-muted);
  white-space: nowrap;
}

.progressTrack {
  height: 6px;
  border-radius: 999px;
  background: var(--surface-alt);
  overflow: hidden;
}

.progressBar {
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
  transition: width 0.6s ease;
}

/* ── Clientes ─────────────────────────────────────────────── */
.clienteStats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.clienteStatItem {
  padding: 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-alt);
  border: 1px solid var(--line);
  text-align: center;
}

.clienteStatValue {
  display: block;
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.clienteStatLabel {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ink-muted);
  margin-top: 4px;
}

/* ── Tabela top clientes ──────────────────────────────────── */
.topClientesTitle {
  margin: 0 0 12px;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--ink-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.topClientesList {
  display: grid;
  gap: 8px;
}

.topClienteRow {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-alt);
  border: 1px solid var(--line);
}

.topClienteRank {
  font-size: 0.78rem;
  font-weight: 800;
  color: var(--ink-subtle);
  min-width: 20px;
}

.topClienteInfo {
  flex: 1;
  min-width: 0;
}

.topClienteNome {
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topClienteTel {
  font-size: 0.78rem;
  color: var(--ink-muted);
}

.topClienteStats {
  text-align: right;
  white-space: nowrap;
}

.topClienteValor {
  font-size: 0.88rem;
  font-weight: 700;
}

.topClienteVisitas {
  font-size: 0.75rem;
  color: var(--ink-muted);
}

/* ── Loading ──────────────────────────────────────────────── */
.loadingState {
  display: grid;
  place-items: center;
  gap: 14px;
  min-height: 300px;
}

.loadingPulse {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  background: var(--accent-soft);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(0.92); opacity: 0.6; }
  50%       { transform: scale(1);    opacity: 1;   }
}

/* ── Responsividade ───────────────────────────────────────── */
@media (max-width: 1120px) {
  .statsGrid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .contentGrid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .statsGrid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .clienteStats {
    grid-template-columns: repeat(3, 1fr);
  }
  .upgradeCard {
    padding: 32px 24px;
  }
  .shell {
    padding: 16px 0 60px;
  }
  .hero,
  .panel,
  .statCard {
    padding: 18px;
    border-radius: var(--radius-lg);
  }
}

@media (max-width: 480px) {
  .statsGrid {
    grid-template-columns: 1fr;
  }
  .clienteStats {
    grid-template-columns: repeat(2, 1fr);
  }
  .heroTitle {
    font-size: 2rem;
  }
}
```

- [ ] **Step 2: Criar `frontend/app/dashboard/page.tsx`**

```tsx
// frontend/app/dashboard/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Lock, TrendingUp, Users, Scissors, DollarSign } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useAuthSession } from "@/services/auth";
import {
  getDashboardFinanceiro,
  getDashboardServicos,
  getDashboardClientes,
  type FinanceiroResponse,
  type ServicosMaisVendidosResponse,
  type ClientesResponse,
} from "@/services/api";
import styles from "./page.module.css";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const pct = (v: number | null) => {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
};

function UpgradeScreen() {
  return (
    <div className={styles.upgradePage}>
      <div className={styles.upgradeCard}>
        <div className={styles.upgradeIcon}>
          <Lock size={28} />
        </div>
        <h1 className={styles.upgradeTitle}>Dashboard Premium</h1>
        <p className={styles.upgradeText}>
          Acesse analytics financeiros, ranking de serviços e análise de clientes
          com o plano <strong>Premium</strong>. Fale com o suporte para fazer upgrade.
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const session = useAuthSession();
  const isPremium = session?.plan === "premium";
  const tenantId = session?.tenantId ?? "";

  const [financeiro, setFinanceiro] = useState<FinanceiroResponse | null>(null);
  const [servicos, setServicos] = useState<ServicosMaisVendidosResponse | null>(null);
  const [clientes, setClientes] = useState<ClientesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPremium || !tenantId) return;

    setLoading(true);
    Promise.all([
      getDashboardFinanceiro(tenantId),
      getDashboardServicos(tenantId),
      getDashboardClientes(tenantId),
    ])
      .then(([fin, srv, cli]) => {
        setFinanceiro(fin);
        setServicos(srv);
        setClientes(cli);
      })
      .catch(() => setError("Erro ao carregar dados. Tente novamente."))
      .finally(() => setLoading(false));
  }, [isPremium, tenantId]);

  if (!session) return null;
  if (!isPremium) return <UpgradeScreen />;

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.loadingPulse} />
        <p style={{ color: "var(--ink-muted)" }}>Carregando analytics…</p>
      </div>
    );
  }

  if (error || !financeiro || !servicos || !clientes) {
    return (
      <div className={styles.loadingState}>
        <p style={{ color: "var(--danger)" }}>{error ?? "Erro desconhecido."}</p>
      </div>
    );
  }

  const maxVendas = servicos.servicos[0]?.total_vendas ?? 1;

  const variacaoClass =
    financeiro.variacao_percentual === null
      ? ""
      : financeiro.variacao_percentual >= 0
      ? styles.variacaoPositiva
      : styles.variacaoNegativa;

  const mesLabel = (mes: string) => {
    const [year, month] = mes.split("-");
    return new Date(Number(year), Number(month) - 1).toLocaleDateString("pt-BR", {
      month: "short",
    });
  };

  return (
    <div className={styles.page}>
      <div className={`app-container ${styles.shell}`}>
        {/* Hero */}
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Analytics Premium</p>
          <h1 className={styles.heroTitle}>Dashboard</h1>
          <p className={styles.heroSubtitle}>
            Visão financeira e comportamento de clientes da sua barbearia.
          </p>
        </section>

        {/* Stat cards */}
        <div className={styles.statsGrid}>
          <article className={styles.statCard}>
            <div className={styles.statIcon}><DollarSign size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Faturamento do mês</span>
              <strong className={styles.statValue}>{brl(financeiro.faturamento_mes_atual)}</strong>
              <span className={`${styles.statHelper} ${variacaoClass}`}>
                {pct(financeiro.variacao_percentual)} vs mês anterior
              </span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><TrendingUp size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Ticket médio</span>
              <strong className={styles.statValue}>{brl(financeiro.ticket_medio)}</strong>
              <span className={styles.statHelper}>por agendamento confirmado</span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><Scissors size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Agendamentos</span>
              <strong className={styles.statValue}>{financeiro.total_agendamentos}</strong>
              <span className={styles.statHelper}>confirmados no mês atual</span>
            </div>
          </article>

          <article className={styles.statCard}>
            <div className={styles.statIcon}><Users size={22} /></div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Clientes únicos</span>
              <strong className={styles.statValue}>{clientes.total_clientes}</strong>
              <span className={styles.statHelper}>últimos 30 dias</span>
            </div>
          </article>
        </div>

        <div className={styles.contentGrid}>
          {/* Coluna principal */}
          <div style={{ display: "grid", gap: "20px" }}>
            {/* Gráfico faturamento */}
            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>Faturamento — últimos 12 meses</h2>
              <div className={styles.chartWrap}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={financeiro.historico_12_meses.map((h) => ({
                      mes: mesLabel(h.mes),
                      faturamento: h.faturamento,
                      agendamentos: h.total_agendamentos,
                    }))}
                    margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis
                      dataKey="mes"
                      tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
                      axisLine={false}
                      tickLine={false}
                      width={52}
                    />
                    <Tooltip
                      formatter={(value: number) => [brl(value), "Faturamento"]}
                      contentStyle={{
                        background: "var(--surface)",
                        border: "1px solid var(--line)",
                        borderRadius: "8px",
                        fontSize: "13px",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="faturamento"
                      stroke="var(--accent)"
                      strokeWidth={2.5}
                      dot={false}
                      activeDot={{ r: 5, fill: "var(--accent)" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Clientes */}
            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>Clientes — últimos 30 dias</h2>
              <div className={styles.clienteStats}>
                <div className={styles.clienteStatItem}>
                  <strong className={styles.clienteStatValue}>{clientes.total_clientes}</strong>
                  <span className={styles.clienteStatLabel}>Únicos</span>
                </div>
                <div className={styles.clienteStatItem}>
                  <strong className={styles.clienteStatValue}>{clientes.clientes_novos}</strong>
                  <span className={styles.clienteStatLabel}>Novos</span>
                </div>
                <div className={styles.clienteStatItem}>
                  <strong className={styles.clienteStatValue}>{clientes.clientes_recorrentes}</strong>
                  <span className={styles.clienteStatLabel}>Recorrentes</span>
                </div>
              </div>
              {clientes.taxa_cancelamento > 0 && (
                <p style={{ margin: "0 0 16px", fontSize: "0.84rem", color: "var(--danger)" }}>
                  Taxa de cancelamento: <strong>{clientes.taxa_cancelamento}%</strong>
                </p>
              )}

              <p className={styles.topClientesTitle}>Top 5 clientes</p>
              <div className={styles.topClientesList}>
                {clientes.top_5_clientes.map((c, i) => (
                  <div key={c.telefone} className={styles.topClienteRow}>
                    <span className={styles.topClienteRank}>#{i + 1}</span>
                    <div className={styles.topClienteInfo}>
                      <div className={styles.topClienteNome}>{c.nome}</div>
                      <div className={styles.topClienteTel}>{c.telefone}</div>
                    </div>
                    <div className={styles.topClienteStats}>
                      <div className={styles.topClienteValor}>{brl(c.valor_total_gasto)}</div>
                      <div className={styles.topClienteVisitas}>{c.total_visitas} visita{c.total_visitas !== 1 ? "s" : ""}</div>
                    </div>
                  </div>
                ))}
                {clientes.top_5_clientes.length === 0 && (
                  <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem" }}>
                    Nenhum dado disponível.
                  </p>
                )}
              </div>
            </section>
          </div>

          {/* Sidebar — Serviços */}
          <section className={styles.panel}>
            <h2 className={styles.panelTitle}>Serviços mais vendidos</h2>
            <p style={{ margin: "0 0 16px", fontSize: "0.82rem", color: "var(--ink-muted)" }}>
              Últimos 30 dias
            </p>
            <div className={styles.servicosList}>
              {servicos.servicos.map((s) => (
                <div key={s.nome} className={styles.servicoItem}>
                  <div className={styles.servicoHeader}>
                    <span className={styles.servicoNome}>{s.nome}</span>
                    <span className={styles.servicoVendas}>{s.total_vendas}× · {brl(s.receita_total)}</span>
                  </div>
                  <div className={styles.progressTrack}>
                    <div
                      className={styles.progressBar}
                      style={{ width: `${(s.total_vendas / maxVendas) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
              {servicos.servicos.length === 0 && (
                <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem" }}>
                  Nenhum serviço no período.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/dashboard/page.tsx frontend/app/dashboard/page.module.css
git commit -m "feat: página /dashboard com analytics premium (gráfico, serviços, clientes)"
```

---

## Task 6: Frontend — Adicionar item "Dashboard" no Header

**Files:**
- Modify: `frontend/app/components/Header.tsx`

### Context
O Header usa `useAuthSession()` para obter `session`. A constante `navItems` monta os links do menu. Já tem `isAdmin` para controle condicional. Precisamos adicionar o item "Dashboard" só quando `session.plan === "premium"` e o usuário não for admin.

O ícone `LayoutDashboard` já está importado do lucide-react na linha 4 do arquivo. Basta adicionar um novo item com ícone `BarChart2` (importar junto) ou usar `TrendingUp`.

- [ ] **Step 1: Ler o arquivo Header.tsx atual**

Ver o bloco de `navItems` (linhas 21–26 do arquivo atual).

- [ ] **Step 2: Editar `Header.tsx` para incluir o item Dashboard**

Na linha do import de lucide-react (linha 4), adicionar `BarChart2` à lista:
```tsx
import { BarChart2, CalendarDays, LayoutDashboard, Scissors, Settings2, Shield, LogOut } from "lucide-react";
```

No bloco `navItems` (após o item "Gestao", antes do spread do admin):
```tsx
const navItems = [
  { href: "/", label: "Painel", icon: LayoutDashboard },
  { href: "/agenda", label: "Agenda", icon: CalendarDays },
  { href: "/gestao", label: "Gestao", icon: Settings2 },
  ...(!isAdmin && session?.plan === "premium" ? [{ href: "/dashboard", label: "Dashboard", icon: BarChart2 }] : []),
  ...(isAdmin && !inAdminPage ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
];
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/components/Header.tsx
git commit -m "feat: item Dashboard no menu (visível apenas para plano premium)"
```

---

## Verificação Final

- [ ] **Backend funciona localmente:**
  - `GET /dashboard/{id}/financeiro` → 200 para premium, 403 para basico
  - `GET /dashboard/{id}/servicos-mais-vendidos` → resposta correta
  - `GET /dashboard/{id}/clientes` → resposta correta

- [ ] **Frontend funciona localmente:**
  ```bash
  cd frontend && npm run dev
  ```
  - Acessar `/dashboard` com conta premium → ver gráfico + cards
  - Acessar `/dashboard` com conta basico → ver tela de upgrade
  - Item "Dashboard" aparece no header só para premium

- [ ] **Deploy:** Fazer push para `main` para triggerar deploy automático
  ```bash
  git push origin main
  ```
