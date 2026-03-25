# Generalização e Correção de Lógica de Agendamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir a lógica de slots da agenda (intervalo fixo vs. duração do serviço) e generalizar o vocabulário do frontend para suportar qualquer tipo de estabelecimento.

**Architecture:** Cinco correções independentes mas encadeadas: (1) add campo `intervalo_minutos` no modelo Estabelecimento + migration no padrão `_run_best_effort`, (2) refatorar `build_day_slots` para separar `interval_minutes` de `duration_minutes` e ler o valor do estabelecimento, (3) merge de agendamentos fora da grade no endpoint `/agenda/dia`, (4) expor `intervalo_minutos` via endpoint de funcionamento + campo no gestão, (5) renomear textos "barbeiro/barbearia" para vocabulário neutro e corrigir referências de domínio hardcoded.

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL (backend), Next.js 16 App Router + TypeScript (frontend). Sem Alembic — migrações via `_run_best_effort` em `database.py`. Testes: pytest (backend), `npm run build` TypeScript check (frontend).

---

## Dependency Map

```
Task 1 (model) → Task 2 (build_day_slots) → Task 3 (booking_times)
Task 1 (model) → Task 4 (endpoint)         → Task 7 (gestão UI)
Task 5 (vocab) → Task 6 (text rename)       — independente
Task 8 (domains)                             — independente
```

Execute Tasks 1→2→3→4 em sequência. Tasks 5→6, Task 7, Task 8 podem correr em paralelo após Task 1.

---

## File Map

| Arquivo | O que muda |
|---|---|
| `backend/app/models/estabelecimento.py` | + coluna `intervalo_minutos: int` |
| `backend/app/database.py` | + `_ensure_intervalo_minutos_column()` chamado em `init_db()` |
| `backend/app/config.py` | default `INTERVALO_MINUTOS` de 40 → 30 (fallback) |
| `backend/app/services/barbershop_hours_service.py` | `build_day_slots` recebe `interval_minutes` separado de `duration_minutes` |
| `backend/app/routes/agenda.py` | lê `intervalo_minutos` do estabelecimento; merge de `booking_times` |
| `backend/app/services/agenda_service.py` | lê `intervalo_minutos` do estabelecimento |
| `backend/app/routes/barbearia_funcionamento.py` | aceita/retorna `intervalo_minutos` |
| `backend/app/schemas/barbearia.py` (ou funcionamento) | schema inclui `intervalo_minutos` |
| `frontend/lib/vocab.ts` | `defaultVocab` neutro |
| `frontend/app/agenda/page.tsx` | rename vars + textos visíveis |
| `frontend/app/components/AgendaGrid.tsx` | rename tipo `SelectedAgendamento` |
| `frontend/app/components/AgendaCell.tsx` | rename prop `barbeiroNome` |
| `frontend/app/agendar/[barbeariaId]/page.tsx` | labels visíveis usam vocab |
| `frontend/services/api.ts` | alias `AgendaProfissional` |
| `frontend/app/gestao/page.tsx` | campo `intervalo_minutos` na aba funcionamento |
| `backend/app/services/webhook_greeting_service.py` | URL via `BOOKING_PUBLIC_BASE_URL` |
| `backend/app/services/email_service.py` | remetente via `EMAIL_FROM_NAME` |
| `backend/.env.example` | criar com vars obrigatórias |
| `frontend/.env.example` | criar/atualizar |

---

## Task 1: Backend — Campo `intervalo_minutos` no modelo + migration

**Files:**
- Modify: `backend/app/models/estabelecimento.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_agenda.py` (verificar que ainda passa)

- [ ] **Step 1: Adicionar coluna ao modelo Estabelecimento**

Editar `backend/app/models/estabelecimento.py`, logo após `notif_horas_antes`:

```python
# antes de: profissionais = relationship(...)
intervalo_minutos = Column(Integer, nullable=False, server_default="30")
```

A linha de import já tem `Integer` no topo do arquivo — não duplicar.

- [ ] **Step 2: Adicionar migration `_ensure_intervalo_minutos_column` em `database.py`**

Adicionar função ao final da seção de helpers (antes de `_backfill_agendamentos_notification_defaults`):

```python
def _ensure_intervalo_minutos_column():
    """Adiciona coluna intervalo_minutos em estabelecimentos (default 30 min)."""
    _run_best_effort([
        "ALTER TABLE estabelecimentos ADD COLUMN intervalo_minutos INTEGER NOT NULL DEFAULT 30",
    ])
```

No corpo de `init_db()`, adicionar chamada após `_ensure_configuracoes_columns()`:

```python
_ensure_intervalo_minutos_column()
```

- [ ] **Step 3: Alterar default de `INTERVALO_MINUTOS` em `config.py`**

```python
# Antes:
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "40"))

# Depois:
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "30"))
```

Isso é apenas o **fallback** global — o valor real virá do estabelecimento a partir da Task 2.

- [ ] **Step 4: Rodar testes de backend para garantir que não quebrou nada**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/test_agenda.py tests/test_barbearia_funcionamento.py -v 2>&1 | tail -30
```

Expected: todos PASSED (os testes usam um DB SQLite em memória que cria as tabelas do zero via `Base.metadata.create_all`, então o novo campo aparece automaticamente).

- [ ] **Step 5: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add backend/app/models/estabelecimento.py backend/app/database.py backend/app/config.py
git commit -m "feat: adicionar campo intervalo_minutos ao modelo Estabelecimento"
```

---

## Task 2: Backend — Refatorar `build_day_slots` (interval ≠ duration)

**Files:**
- Modify: `backend/app/services/barbershop_hours_service.py`
- Modify: `backend/app/routes/agenda.py`
- Modify: `backend/app/services/agenda_service.py`
- Test: `backend/tests/test_agenda.py`

### Contexto crítico

O bug atual:
```python
# barbershop_hours_service.py — situação atual
def build_day_slots(barbearia, target_date, duration_minutes, barbeiro=None):
    while current + timedelta(minutes=duration_minutes) <= finish:
        slots.append(current)
        current += timedelta(minutes=INTERVALO_MINUTOS)  # ← passo global hardcoded
```

```python
# agenda.py — call site com BUG DUPLO
build_day_slots(barbearia, data.date(), INTERVALO_MINUTOS, barbeiro=barbeiro)
# ↑ passa INTERVALO_MINUTOS como duration_minutes (errado!) E usa global como passo
```

```python
# agenda_service.py — call site correto para duration, mas ainda usa global para passo
build_day_slots(barbearia, data.date(), duracao, barbeiro=barbeiro)
```

- [ ] **Step 1: Refatorar `build_day_slots` em `barbershop_hours_service.py`**

```python
def build_day_slots(
    barbearia,
    target_date: date,
    duration_minutes: int,
    barbeiro=None,
    interval_minutes: int | None = None,
) -> list[datetime]:
    """
    Gera lista de slots disponíveis no dia.

    Args:
        duration_minutes: duração do serviço — usado para checar se o slot cabe antes do fim.
        interval_minutes: passo entre slots. Se None, usa barbearia.intervalo_minutos,
                          com fallback para INTERVALO_MINUTOS global.
    """
    window = get_working_window(barbearia, target_date, barbeiro=barbeiro)
    if not window:
        return []

    if interval_minutes is None:
        interval_minutes = getattr(barbearia, "intervalo_minutos", None) or INTERVALO_MINUTOS

    start, end = window
    current = datetime.combine(target_date, start)
    finish = datetime.combine(target_date, end)
    slots: list[datetime] = []

    while current + timedelta(minutes=duration_minutes) <= finish:
        slots.append(current)
        current += timedelta(minutes=interval_minutes)

    return slots
```

Manter o import de `INTERVALO_MINUTOS` no topo (já está lá) — passa a ser fallback.

- [ ] **Step 2: Corrigir call site em `agenda.py`**

Ler o arquivo `backend/app/routes/agenda.py` para confirmar o contexto, então editar:

**Trecho atual (linha ~43–56):**
```python
barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
barbeiros = (...)

horarios_por_barbeiro = {
    barbeiro.id: [
        slot.strftime("%H:%M")
        for slot in build_day_slots(barbearia, data.date(), INTERVALO_MINUTOS, barbeiro=barbeiro)
    ]
    for barbeiro in barbeiros
}
```

**Substituir por:**
```python
barbearia = db.query(Barbearia).filter(Barbearia.id == tenant_id).first()
barbeiros = (...)

# interval_minutes = None → build_day_slots lê do estabelecimento
# duration_minutes = 1 → qualquer slot que inicia cabe (grade é independente de duração de serviço)
horarios_por_barbeiro = {
    barbeiro.id: [
        slot.strftime("%H:%M")
        for slot in build_day_slots(barbearia, data.date(), duration_minutes=1, barbeiro=barbeiro)
    ]
    for barbeiro in barbeiros
}
```

**Justificativa do `duration_minutes=1`:** A grade `/agenda/dia` mostra todos os slots de tempo, não filtra por duração de serviço. Usar `1` minuto garante que todos os slots aparecem (qualquer slot de 1 min cabe antes do fim). A verificação real de disponibilidade acontece em `agenda_service.py`.

Remover também o import de `INTERVALO_MINUTOS` em `agenda.py` se não for mais usado (verificar após a edição).

- [ ] **Step 3: Atualizar call site em `agenda_service.py`**

O call site atual em `agenda_service.py` já passa `duracao` corretamente. Apenas remover o import de `INTERVALO_MINUTOS` se existir:

```python
# agenda_service.py — confirmar que a linha está assim (não precisa mudar):
horarios = build_day_slots(barbearia, data.date(), duracao, barbeiro=barbeiro)
# ↑ build_day_slots agora lê interval_minutes do próprio barbearia object — correto
```

Verificar se `from app.config import INTERVALO_MINUTOS` existe em `agenda_service.py`; se sim, remover.

- [ ] **Step 4: Rodar testes**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/test_agenda.py -v 2>&1 | tail -40
```

Expected: todos PASSED. Se algum falhar com "08:00 not in horarios", o slot gerado depende do `intervalo_minutos` default (30 min) — 08:00 ainda deve estar presente pois é o início do expediente.

- [ ] **Step 5: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add backend/app/services/barbershop_hours_service.py \
        backend/app/routes/agenda.py \
        backend/app/services/agenda_service.py
git commit -m "fix: build_day_slots separa interval_minutes de duration_minutes, lê do estabelecimento"
```

---

## Task 3: Backend — Agendamentos fora da grade aparecem na agenda

**Files:**
- Modify: `backend/app/routes/agenda.py` (linhas ~58–60)
- Test: `backend/tests/test_agenda.py`

- [ ] **Step 1: Escrever teste de regressão em `test_agenda.py`**

Adicionar ao final de `backend/tests/test_agenda.py`:

```python
def test_agenda_dia_inclui_horario_fora_da_grade(client, dados_base, tenant_headers, db_session):
    """Agendamento criado em horário não alinhado com a grade deve aparecer na agenda visual."""
    data = _proxima_segunda(dados_base["amanha"]).replace(hour=0, minute=0, second=0, microsecond=0)

    # Criar agendamento às 09:15 — fora de grades típicas de 30 ou 40 min a partir das 08:00
    inicio = data.replace(hour=9, minute=15)
    _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        "5582977777777",
        "Cliente Fora Grade",
        inicio.isoformat(),
    )

    resp = client.get("/agenda/dia", params={"data": data.isoformat()}, headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.json()

    # "09:15" deve aparecer na lista global de horários
    assert "09:15" in body["horarios"], f"09:15 deveria estar em horarios, got: {body['horarios']}"

    # E no agendamentos do barbeiro correto
    ags = body["barbeiros"][0]["agendamentos"]
    assert any(item["hora"] == "09:15" for item in ags)
```

- [ ] **Step 2: Rodar para confirmar que falha (red)**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/test_agenda.py::test_agenda_dia_inclui_horario_fora_da_grade -v
```

Expected: FAIL — `09:15` não está em `body["horarios"]`.

- [ ] **Step 3: Implementar o merge de `booking_times` em `agenda.py`**

Localizar a linha atual:
```python
horarios = sorted({hora for itens in horarios_por_barbeiro.values() for hora in itens})
```

Substituir por (após o bloco que popula `por_barbeiro` com os agendamentos):
```python
# Horários da grade
_grade_times = {hora for itens in horarios_por_barbeiro.values() for hora in itens}

# Horários reais dos agendamentos (incluindo fora da grade)
_booking_times = {ag.data_hora_inicio.strftime("%H:%M") for ag in agendamentos}

horarios = sorted(_grade_times | _booking_times)
```

**Atenção:** este trecho deve ficar APÓS o bloco que popula `agendamentos` (linha ~70–82 do arquivo atual), senão `agendamentos` ainda estará vazio `[]`.

- [ ] **Step 4: Rodar testes (green)**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/test_agenda.py -v 2>&1 | tail -20
```

Expected: todos PASSED, incluindo o novo.

- [ ] **Step 5: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add backend/app/routes/agenda.py backend/tests/test_agenda.py
git commit -m "fix: agendamentos fora da grade aparecem na agenda visual (merge booking_times)"
```

---

## Task 4: Backend — Expor `intervalo_minutos` no endpoint de funcionamento

**Files:**
- Read first: `backend/app/routes/barbearia_funcionamento.py`
- Read first: `backend/app/schemas/barbearia.py` (ou funcionamento)
- Modify: rota GET e PATCH de funcionamento + schema correspondente

**Contexto:** O projeto já tem um endpoint de funcionamento (`/barbearia/funcionamento` ou similar). Precisamos que ele leia e salve `intervalo_minutos` do modelo `Estabelecimento`. A Task 7 (frontend gestão) consome este endpoint.

- [ ] **Step 1: Ler os arquivos relevantes**

```bash
cat -n /Users/viniciusttm/dev/barbearia-chatbot/backend/app/routes/barbearia_funcionamento.py
```

Identificar:
1. O path do GET endpoint (ex.: `GET /barbearia/funcionamento`)
2. O path do PATCH endpoint
3. O schema Pydantic usado no PATCH body

- [ ] **Step 2: Adicionar `intervalo_minutos` ao schema de update**

No schema Pydantic do body do PATCH (procurar em `backend/app/schemas/barbearia.py` ou criar campo inline), adicionar:

```python
intervalo_minutos: int | None = None  # 5–120, step 5
```

- [ ] **Step 3: Adicionar `intervalo_minutos` à resposta do GET**

Na função do GET endpoint, incluir `intervalo_minutos` na resposta:

```python
return {
    "horarios_funcionamento": ...,   # campo já existente
    "intervalo_minutos": barbearia.intervalo_minutos or 30,
}
```

- [ ] **Step 4: Salvar `intervalo_minutos` no PATCH**

Na função do PATCH endpoint, após salvar `horarios_funcionamento`, adicionar:

```python
if body.intervalo_minutos is not None:
    valor = max(5, min(120, body.intervalo_minutos))  # clamp 5–120
    barbearia.intervalo_minutos = valor
```

- [ ] **Step 5: Verificar com curl ou teste**

```bash
# No conftest, o tenant já tem um estabelecimento criado — rodar suite de funcionamento:
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/test_barbearia_funcionamento.py -v 2>&1 | tail -20
```

Expected: PASSED. Se o schema mudar e o teste enviar um body sem `intervalo_minutos`, o campo `None = None` garante compatibilidade retroativa.

- [ ] **Step 6: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add backend/app/routes/barbearia_funcionamento.py backend/app/schemas/
git commit -m "feat: endpoint de funcionamento expõe e salva intervalo_minutos"
```

---

## Task 5: Frontend — `vocab.ts` default neutro

**Files:**
- Modify: `frontend/lib/vocab.ts`

- [ ] **Step 1: Alterar `defaultVocab` para vocabulário neutro**

Substituir:
```typescript
const defaultVocab: VocabEntry = vocabMap["barbearia"];
```

Por:
```typescript
const defaultVocab: VocabEntry = {
  profissional: "Profissional",
  estabelecimento: "Estabelecimento",
  profissionalPlural: "Profissionais",
};
```

Manter os mapeamentos específicos (`barbearia`, `salao_beleza`, `estetica_automotiva`) intocados.

- [ ] **Step 2: Verificar build TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend
npm run build 2>&1 | tail -20
```

Expected: sem erros de TypeScript.

- [ ] **Step 3: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add frontend/lib/vocab.ts
git commit -m "feat: vocab.ts default neutro (Profissional/Estabelecimento)"
```

---

## Task 6: Frontend — Renomear variáveis e textos barbeiro→profissional

**Files:**
- Modify: `frontend/app/agenda/page.tsx`
- Modify: `frontend/app/components/AgendaGrid.tsx`
- Modify: `frontend/app/components/AgendaCell.tsx`
- Modify: `frontend/services/api.ts` (alias de tipo)
- Modify (textos apenas): `frontend/app/agendar/[barbeariaId]/page.tsx`

**Regra fundamental:** Campos internos da API (JSON) como `barbeiros`, `barbearia_id`, `barbeiro_id` NÃO mudam — são keys de banco/API. Apenas variáveis TypeScript locais e textos visíveis ao usuário mudam.

- [ ] **Step 1: Ler `frontend/app/components/AgendaCell.tsx` (confirmar props)**

Confirmar que a prop se chama `barbeiroNome` (já lido — sim). A prop é puramente interna ao componente; o `aria-label` usa `barbeiroNome` mas não é visível ao usuário final como texto.

- [ ] **Step 2: Renomear prop em `AgendaCell.tsx`**

```typescript
// Antes:
type AgendaCellProps = {
  hora: string;
  barbeiroNome: string;
  ...
}
export default function AgendaCell({
  hora,
  barbeiroNome,
  ...
}: AgendaCellProps) {
  ...
  aria-label={`${barbeiroNome} as ${hora}`}
```

```typescript
// Depois:
type AgendaCellProps = {
  hora: string;
  profissionalNome: string;
  ...
}
export default function AgendaCell({
  hora,
  profissionalNome,
  ...
}: AgendaCellProps) {
  ...
  aria-label={`${profissionalNome} as ${hora}`}
```

- [ ] **Step 3: Atualizar `SelectedAgendamento` e call site em `AgendaGrid.tsx`**

```typescript
// Antes:
export type SelectedAgendamento = {
  hora: string;
  barbeiroId: number;
  barbeiroNome: string;
  agendamento?: AgendaSlot;
};
// E no onSelect:
onSelect({
  hora,
  barbeiroId: barbeiro.id,
  barbeiroNome: barbeiro.nome,
  agendamento,
});
// E no AgendaCell:
<AgendaCell
  barbeiroNome={barbeiro.nome}
  ...
```

```typescript
// Depois:
export type SelectedAgendamento = {
  hora: string;
  profissionalId: number;
  profissionalNome: string;
  agendamento?: AgendaSlot;
};
// E no onSelect:
onSelect({
  hora,
  profissionalId: barbeiro.id,
  profissionalNome: barbeiro.nome,
  agendamento,
});
// E no AgendaCell:
<AgendaCell
  profissionalNome={barbeiro.nome}
  ...
```

- [ ] **Step 4: Atualizar `agenda/page.tsx` — variáveis e textos**

Renomeações de variáveis:
```typescript
// Antes:
const [selectedBarbeiroId, setSelectedBarbeiroId] = useState("all");
// ...
selectedBarbeiroId !== "all" && !data.barbeiros.some(b => String(b.id) === selectedBarbeiroId)
// ...
const barbeirosVisiveis = data?.barbeiros.filter(b => selectedBarbeiroId === "all" || ...)
// ...
const selectedKey = selected ? `${selected.barbeiroId}-${selected.hora}` : undefined;
```

```typescript
// Depois:
const [selectedProfissionalId, setSelectedProfissionalId] = useState("all");
// ...
selectedProfissionalId !== "all" && !data.barbeiros.some(b => String(b.id) === selectedProfissionalId)
// ...
const barbeirosVisiveis = data?.barbeiros.filter(b => selectedProfissionalId === "all" || ...)
// ...
const selectedKey = selected ? `${selected.profissionalId}-${selected.hora}` : undefined;
```

Textos visíveis ao usuário:
```typescript
// agenda/page.tsx — textos a substituir:

// "Veja a disponibilidade por barbeiro..." → "Veja a disponibilidade por profissional..."
// <label htmlFor="barbeiro-filter">Barbeiro</label> → Profissional
// id="barbeiro-filter" → id="profissional-filter" (e o htmlFor correspondente)
// <option value="all">Todos os barbeiros</option> → "Todos os profissionais"
// "Fora do expediente do barbeiro" → "Fora do expediente do profissional"
// selected.barbeiroNome → selected.profissionalNome  (2 ocorrências no JSX de detalhes)
// setSelectedBarbeiroId → setSelectedProfissionalId (nos onChange)
```

- [ ] **Step 5: Adicionar alias em `services/api.ts`**

Localizar o tipo `AgendaBarbeiro` (ou equivalente) e adicionar ao final da seção de tipos:

```typescript
// Alias genérico — mantém compatibilidade com código que importar AgendaBarbeiro
export type AgendaProfissional = AgendaBarbeiro;
```

- [ ] **Step 6: Textos em `agendar/[barbeariaId]/page.tsx`**

Ler o arquivo. Localizar labels visíveis como "Escolha o barbeiro", "Barbeiro" em selects/headings e substituir por vocab dinâmico. Exemplo padrão:

```typescript
// Se o arquivo já importa getVocab ou similar:
import { getVocab } from "@/lib/vocab";
const vocab = getVocab(estabelecimento?.tipo_servico);
// ...
<label>Escolha o {vocab.profissional}</label>
```

Se o arquivo não tem acesso ao `tipo_servico`, usar o texto neutro literal: `"Profissional"`.

- [ ] **Step 7: Build TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend
npm run build 2>&1 | grep -E "error|Error|✓" | head -20
```

Expected: `✓ Compiled successfully` sem erros de tipo.

- [ ] **Step 8: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add frontend/app/agenda/page.tsx \
        frontend/app/components/AgendaGrid.tsx \
        frontend/app/components/AgendaCell.tsx \
        frontend/services/api.ts \
        frontend/app/agendar/
git commit -m "feat: renomear barbeiro→profissional em variáveis e textos do frontend"
```

---

## Task 7: Frontend — Campo `intervalo_minutos` no painel de gestão

**Files:**
- Read first: `frontend/app/gestao/page.tsx` (inteiro — é grande)
- Modify: `frontend/app/gestao/page.tsx`
- Read first: `frontend/services/api.ts` (funções `getBarbershopWorkingHours` / `updateBarbershopWorkingHours`)

**Contexto:** A aba "funcionamento" do gestão já salva `horarios_funcionamento`. Precisamos adicionar o campo `intervalo_minutos` ao mesmo fluxo.

- [ ] **Step 1: Ler `api.ts` — tipos e funções de funcionamento**

```bash
grep -n "WorkingHours\|funcionamento\|intervalo" /Users/viniciusttm/dev/barbearia-chatbot/frontend/services/api.ts | head -30
```

Identificar o tipo `BarbershopWorkingHours` e se ele já inclui (ou pode incluir) `intervalo_minutos`.

- [ ] **Step 2: Adicionar `intervalo_minutos` ao tipo/interface em `api.ts`**

```typescript
// Localizar BarbershopWorkingHours ou o tipo de update de funcionamento:
export type BarbershopWorkingHours = {
  // campos existentes...
  intervalo_minutos?: number;  // ← adicionar
};
```

- [ ] **Step 3: Ler gestao/page.tsx — aba funcionamento**

Localizar a seção onde `updateBarbershopWorkingHours` é chamado e onde o estado de funcionamento é inicializado.

- [ ] **Step 4: Adicionar estado `intervaloMinutos` no gestão**

```typescript
const [intervaloMinutos, setIntervaloMinutos] = useState<number>(30);
```

No `useEffect` que carrega os dados de funcionamento:
```typescript
const dados = await getBarbershopWorkingHours();
// ...
setIntervaloMinutos(dados.intervalo_minutos ?? 30);
```

No submit do funcionamento:
```typescript
await updateBarbershopWorkingHours({
  horarios_funcionamento: horariosEditados,
  intervalo_minutos: intervaloMinutos,
});
```

- [ ] **Step 5: Adicionar campo de formulário na aba funcionamento**

Inserir antes ou após o bloco de horários por dia, na seção de configurações do estabelecimento:

```tsx
<div className={styles.formGroup}>
  <label className={styles.formLabel}>
    Intervalo entre horários (minutos)
  </label>
  <input
    type="number"
    min={5}
    max={120}
    step={5}
    value={intervaloMinutos}
    onChange={(e) => setIntervaloMinutos(Number(e.target.value))}
    className={styles.formInput}
  />
  <span className={styles.formHint}>
    Define o espaçamento entre os slots disponíveis na agenda. Ex: 30 min gera horários
    como 09:00, 09:30, 10:00...
  </span>
</div>
```

Use as classes CSS já existentes no `page.module.css` — não criar novas.

- [ ] **Step 6: Build TypeScript**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/frontend
npm run build 2>&1 | grep -E "error|Error|✓" | head -20
```

Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add frontend/app/gestao/page.tsx frontend/services/api.ts
git commit -m "feat: campo intervalo_minutos na aba de funcionamento do gestão"
```

---

## Task 8: Global — Referências de domínio hardcoded

**Files:**
- Modify: `backend/app/services/webhook_greeting_service.py` (linha 29)
- Modify: `backend/app/services/email_service.py` (linha 158 — "Virtual Barber")
- Create: `backend/.env.example`
- Create: `frontend/.env.example`

**Escopo preciso:** Apenas 2 arquivos backend têm referências que DEVEM mudar. As demais (`public_booking_service.py`, `email_service.py` EMAIL_FROM/URL) já usam variáveis de ambiente com fallbacks — os fallbacks são aceitáveis.

- [ ] **Step 1: Corrigir `webhook_greeting_service.py`**

Ler o arquivo para confirmar o contexto da linha 29. A linha atual:
```python
f"https://app.virtualbarber.shop/agendar/{barbearia_id}"
```

Substituir por:
```python
import os
# (adicionar import no topo se não existir)
_BOOKING_BASE = os.getenv("BOOKING_PUBLIC_BASE_URL", "https://app.virtualbarber.shop")
# ...
f"{_BOOKING_BASE.rstrip('/')}/agendar/{barbearia_id}"
```

- [ ] **Step 2: Corrigir `email_service.py` — remetente "Virtual Barber"**

Ler a linha 158 para confirmar contexto. Localizar onde "Virtual Barber" aparece como nome do remetente (provavelmente em um header `From: Virtual Barber <noreply@...>`).

```python
# Adicionar near topo (após EMAIL_FROM):
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Virtual Barber")

# Substituir uso hardcoded:
# Antes: "Virtual Barber"
# Depois: EMAIL_FROM_NAME
```

- [ ] **Step 3: Criar `backend/.env.example`**

```bash
cat > /Users/viniciusttm/dev/barbearia-chatbot/backend/.env.example << 'EOF'
# Banco de dados
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/dbname

# JWT
SECRET_KEY=sua-chave-secreta-aqui

# Agendamento
HORARIO_ABERTURA=8
HORARIO_FECHAMENTO=19
INTERVALO_MINUTOS=30

# Email
EMAIL_FROM=noreply@seudominio.com
EMAIL_FROM_NAME=Nome do Sistema
SMTP_HOST=smtp.seudominio.com
SMTP_PORT=587
SMTP_USER=usuario
SMTP_PASSWORD=senha

# URLs públicas
BOOKING_PUBLIC_BASE_URL=https://app.seudominio.com

# CORS
CORS_ALLOWED_ORIGINS=https://app.seudominio.com,https://seudominio.com

# Ambiente
APP_ENV=production
EOF
```

- [ ] **Step 4: Criar `frontend/.env.example`**

```bash
cat > /Users/viniciusttm/dev/barbearia-chatbot/frontend/.env.example << 'EOF'
# URL da API backend
NEXT_PUBLIC_API_URL=https://api.seudominio.com
EOF
```

- [ ] **Step 5: Rodar testes de backend**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot/backend
python -m pytest tests/ -x -q 2>&1 | tail -20
```

Expected: sem novas falhas.

- [ ] **Step 6: Commit**

```bash
cd /Users/viniciusttm/dev/barbearia-chatbot
git add backend/app/services/webhook_greeting_service.py \
        backend/app/services/email_service.py \
        backend/.env.example \
        frontend/.env.example
git commit -m "fix: substituir referências de domínio hardcoded por variáveis de ambiente"
```

---

## Verificação Final

Após todas as tasks:

- [ ] `python -m pytest backend/tests/ -q` — todos PASSED
- [ ] `npm run build` no frontend — sem erros TypeScript
- [ ] Agendamento criado às 17:00 numa grade 08:00→16:00 (intervalo 40) aparece em `horarios`
- [ ] Alterar `intervalo_minutos` de 40 → 30 no gestão muda a grade no próximo carregamento
- [ ] Página pública `/agendar/[id]` continua mostrando horários disponíveis
- [ ] Nenhum texto visível diz "barbeiro/barbearia" nos contextos neutros
- [ ] Email de notificação usa `EMAIL_FROM_NAME` do env
