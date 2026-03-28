# Spec: Dados Reais na Aba "Análise" do Dashboard

**Data:** 2026-03-28

## Objetivo

Substituir os dados mockados de `AnaliseTab.tsx` por dados reais vindos de um novo endpoint consolidado `GET /dashboard/{barbearia_id}/analise`.

---

## Decisões de design

- **Endpoint único:** um endpoint retorna tudo que a aba Análise precisa — uma chamada só, componente autocontido.
- **Período:** mês calendário atual para todos os blocos (`date.today().replace(day=1)` até `date.today()`).
- **No-show:** agendamentos com `status="pendente"` cuja `data_hora_inicio < datetime.now()` — não altera o modelo.
- **Premium gate:** mesma dependência `verificar_plano_premium` dos outros endpoints de dashboard.
- **Isolamento de tenant:** filtra por `estabelecimento_id` (alias `barbearia_id`), verifica `barbearia_id == tenant_id`, retorna 403 se diferente.
- **Resultado vazio:** mês sem agendamentos retorna zeros e arrays vazios, nunca erro.

---

## Arquivos

| Arquivo | Ação |
|---|---|
| `backend/app/schemas/dashboard.py` | Adicionar 6 novos schemas |
| `backend/app/routes/dashboard.py` | Adicionar endpoint `GET /{barbearia_id}/analise` |
| `backend/tests/test_analise_dashboard.py` | Criar — testes do novo endpoint |
| `frontend/services/api.ts` | Adicionar tipos + `getDashboardAnalise()` |
| `frontend/app/dashboard/AnaliseTab.tsx` | Substituir mocks por chamada real |

---

## Schemas novos em `app/schemas/dashboard.py`

```python
class ResumoMes(BaseModel):
    agendamentos: int
    faturamento: float
    ticket_medio: float
    ocupacao: int           # 0–100 (percentual inteiro)

class DiaSemana(BaseModel):
    dia: str                # "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"
    clientes: int

class HorarioCheio(BaseModel):
    hora: str               # "18:00"
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
    semana: list[DiaSemana]         # Seg–Dom ordenados (apenas dias com agendamentos)
    horarios: list[HorarioCheio]    # top 5 DESC
    servicos: list[ServicoAnalise]  # top 5 DESC
    clientes: ClientesAnalise
```

---

## Endpoint `GET /dashboard/{barbearia_id}/analise`

```python
@router.get("/{barbearia_id}/analise", response_model=AnaliseResponse)
def analise(
    barbearia_id: int,
    tenant_id: int = Depends(verificar_plano_premium),
    db: Session = Depends(get_db),
):
    if barbearia_id != tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    try:
        return _analise(db, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc
```

### Lógica de `_analise(db, tenant_id)`

Período base:
```python
hoje = date.today()
inicio_mes = hoje.replace(day=1)
agora = datetime.now()
```

**resumo.agendamentos + faturamento + ticket_medio:**
```python
row = db.query(
    func.count(Agendamento.id).label("total"),
    func.coalesce(func.sum(Servico.preco), 0.0).label("fat"),
    func.coalesce(func.avg(Servico.preco), 0.0).label("ticket"),
).select_from(Agendamento)
 .join(Servico, Servico.id == Agendamento.servico_id)
 .filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "confirmado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
 ).first()
agendamentos = int(row.total)
faturamento  = float(row.fat)
ticket_medio = float(row.ticket)
```

**resumo.ocupacao:**
```python
# confirmados já calculados acima
cancelados = db.query(func.count(Agendamento.id)).filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "cancelado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
).scalar() or 0

no_show = db.query(func.count(Agendamento.id)).filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "pendente",
    Agendamento.data_hora_inicio < agora,
    Agendamento.data >= inicio_mes,
).scalar() or 0

total_demanda = agendamentos + cancelados + no_show
ocupacao = round(agendamentos / total_demanda * 100) if total_demanda > 0 else 0
```

**semana** — agendamentos confirmados agrupados por dia da semana:
```python
# Python weekday(): 0=Seg, 1=Ter, ..., 5=Sáb, 6=Dom
DIA_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

rows = db.query(
    func.extract("dow", Agendamento.data).label("dow"),  # 0=Dom,1=Seg,...,6=Sáb (PostgreSQL)
    func.count(Agendamento.id).label("total"),
).filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "confirmado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
).group_by("dow").all()

# PostgreSQL extract("dow"): 0=Dom, 1=Seg, ..., 6=Sáb
# Mapear para ordem Seg–Dom: índice Python = (dow - 1) % 7
contagem = {int(r.dow): int(r.total) for r in rows}
semana = [
    DiaSemana(dia=DIA_LABELS[(dow - 1) % 7], clientes=contagem.get(dow, 0))
    for dow in [1, 2, 3, 4, 5, 6, 0]  # Seg=1 ... Sáb=6, Dom=0
    if contagem.get(dow, 0) > 0        # omitir dias sem agendamentos
]
```

**horarios** — top 5 horários mais cheios:
```python
rows = db.query(
    func.extract("hour", Agendamento.hora_inicio).label("hora"),
    func.count(Agendamento.id).label("total"),
).filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "confirmado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
).group_by("hora").order_by(func.count(Agendamento.id).desc()).limit(5).all()

horarios = [
    HorarioCheio(hora=f"{int(r.hora):02d}:00", atendimentos=int(r.total))
    for r in rows
]
```

**servicos** — top 5 serviços mais vendidos no mês:
```python
rows = db.query(
    Servico.nome,
    func.count(Agendamento.id).label("total"),
).join(Agendamento, Agendamento.servico_id == Servico.id)
 .filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "confirmado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
 ).group_by(Servico.id, Servico.nome)
  .order_by(func.count(Agendamento.id).desc())
  .limit(5).all()

servicos = [ServicoAnalise(nome=r.nome, total=int(r.total)) for r in rows]
```

**clientes** — novos, recorrentes, cancelamentos, no_show:
```python
# Novos e recorrentes: telefones únicos com agendamentos confirmados no mês
freq_rows = db.query(
    Agendamento.cliente_telefone,
    func.count(Agendamento.id).label("visitas"),
).filter(
    Agendamento.barbearia_id == tenant_id,
    Agendamento.status == "confirmado",
    Agendamento.data >= inicio_mes,
    Agendamento.data <= hoje,
).group_by(Agendamento.cliente_telefone).all()

novos        = sum(1 for r in freq_rows if r.visitas == 1)
recorrentes  = sum(1 for r in freq_rows if r.visitas > 1)
# cancelamentos e no_show: já calculados acima
```

---

## Testes em `backend/tests/test_analise_dashboard.py`

### Setup

Fixture própria `dados_analise` que cria:
- 1 `Estabelecimento` com `plano="premium"` (`tenant_a`)
- 1 `Estabelecimento` com `plano="premium"` (`tenant_b`) — para teste de isolamento
- 1 `Servico` "Corte" (R$40) vinculado ao `tenant_a`
- 1 `Servico` "Barba" (R$30) vinculado ao `tenant_a`
- Agendamentos no mês atual para `tenant_a`:
  - 3x confirmado "Corte" — diferentes dias da semana e horas
  - 1x confirmado "Barba" — mesma hora que um dos acima
  - 1x cancelado
  - 1x pendente com `data_hora_inicio` no passado (no-show)
  - 1x pendente com `data_hora_inicio` no futuro (não conta como no-show)
- 1x confirmado "Corte" para `tenant_b` — não deve aparecer nos resultados de `tenant_a`

### Casos de teste

```
test_resumo_agendamentos       → resumo.agendamentos == 4 (3 corte + 1 barba confirmados)
test_resumo_faturamento        → resumo.faturamento == 3*40 + 1*30 == 150.0
test_resumo_ticket_medio       → resumo.ticket_medio == 150.0 / 4 == 37.5
test_resumo_ocupacao           → ocupacao == round(4 / (4+1+1) * 100) == 67
test_semana_retorna_dias       → semana contém apenas dias com agendamentos, labels corretos
test_horarios_ordenados        → horarios[0].atendimentos >= horarios[1].atendimentos
test_horarios_limite_5         → len(horarios) <= 5
test_servicos_ordenados        → servicos[0].nome == "Corte", servicos[1].nome == "Barba"
test_servicos_total            → servicos[0].total == 3, servicos[1].total == 1
test_clientes_novos            → clientes.novos == contagem correta
test_clientes_cancelamentos    → clientes.cancelamentos == 1
test_clientes_no_show          → clientes.no_show == 1 (pendente passado, não futuro)
test_mes_vazio                 → zeros e arrays vazios quando não há agendamentos
test_tenant_isolamento         → resultados de tenant_a não incluem dados de tenant_b
test_403_tenant_errado         → retorna 403 se barbearia_id != tenant autenticado
test_401_sem_token             → retorna 401 se sem Authorization header
```

---

## Frontend — `frontend/services/api.ts`

### Tipos novos

```typescript
export type ResumoMes = {
  agendamentos: number;
  faturamento: number;
  ticket_medio: number;
  ocupacao: number;
};

export type DiaSemana = {
  dia: string;
  clientes: number;
};

export type HorarioCheio = {
  hora: string;
  atendimentos: number;
};

export type ServicoAnalise = {
  nome: string;
  total: number;
};

export type ClientesAnalise = {
  novos: number;
  recorrentes: number;
  cancelamentos: number;
  no_show: number;
};

export type AnaliseResponse = {
  resumo: ResumoMes;
  semana: DiaSemana[];
  horarios: HorarioCheio[];
  servicos: ServicoAnalise[];
  clientes: ClientesAnalise;
};
```

### Função nova

```typescript
export async function getDashboardAnalise(barbeariaId: string): Promise<AnaliseResponse> {
  const res = await apiFetch(`/dashboard/${barbeariaId}/analise`);
  return parseOrThrow(res, "Falha ao carregar dados de análise do dashboard.");
}
```

---

## Frontend — `frontend/app/dashboard/AnaliseTab.tsx`

### Estado

```tsx
const session = useAuthSession();
const tenantId = session?.tenantId ?? "";

const [data, setData] = useState<AnaliseResponse | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  if (!tenantId) return;
  getDashboardAnalise(tenantId)
    .then(setData)
    .catch(() => setError("Erro ao carregar análise."))
    .finally(() => setLoading(false));
}, [tenantId]);
```

### Renderização condicional

```tsx
if (loading) return <div className={styles.loadingState}>…</div>;
if (error || !data) return <div className={styles.loadingState}><p style={{ color: "var(--danger)" }}>{error}</p></div>;
```

Após os guards, substitui os 5 blocos trocando cada referência a `MOCK_*` pelo campo correspondente em `data`:
- `MOCK_RESUMO` → `data.resumo`
- `MOCK_SEMANA` → `data.semana`
- `MOCK_HORARIOS` → `data.horarios`
- `MOCK_SERVICOS` → `data.servicos`
- `MOCK_CLIENTES` → `data.clientes`

Remove todos os `MOCK_*` e `maxSemana`/`maxServico` calculados a partir deles — recalcula inline:
```tsx
const maxSemana = Math.max(...data.semana.map(d => d.clientes), 1);
const maxServico = data.servicos[0]?.total ?? 1;
```

### Imports adicionados

```tsx
import { useEffect, useState } from "react";
import { useAuthSession } from "@/services/auth";
import { getDashboardAnalise, type AnaliseResponse } from "@/services/api";
```

Remove import das constantes mock (nenhum import novo de ícones — os 4 já existem).

---

## Fora de escopo

- Filtros de período (semana/mês/trimestre)
- Exportação de dados
- Alteração no modelo de `Agendamento` (no-show via pendente passado, sem novo status)
