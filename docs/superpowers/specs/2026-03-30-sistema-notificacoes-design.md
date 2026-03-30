# Sistema de Notificações In-App

**Data:** 2026-03-30
**Status:** Aprovado

---

## Visão Geral

Implementar um sistema de notificações in-app para donos de barbearia, cobrindo três eventos:
- Novo agendamento criado
- Agendamento confirmado pelo cliente (via link de email)
- Agendamento com horário passado aguardando confirmação de presença (compareceu / no-show)

O dono pode confirmar presença diretamente na notificação, atualizando o status do agendamento e as métricas do dashboard.

---

## Arquitetura

### Abordagem escolhida: Tabela dedicada + polling

Nova tabela `notificacoes` no banco. O backend gera registros nos eventos-chave. O frontend faz polling a cada 15 segundos. Segue o padrão já existente no projeto (`reminder_jobs`, `BackgroundTasks`, APScheduler).

---

## Modelo de Dados

### Nova tabela: `notificacoes`

```sql
id                 SERIAL PRIMARY KEY
estabelecimento_id INT NOT NULL REFERENCES estabelecimentos(id)
agendamento_id     INT REFERENCES agendamentos(id) ON DELETE CASCADE
tipo               VARCHAR(40) NOT NULL
titulo             VARCHAR(255) NOT NULL
corpo              TEXT
lida               BOOLEAN DEFAULT FALSE
criada_em          TIMESTAMP NOT NULL DEFAULT NOW()
lida_em            TIMESTAMP
```

**Índice:** `(estabelecimento_id, lida, criada_em DESC)` — otimiza o polling.

### Tipos de notificação (`tipo`)

| Valor | Quando é criada |
|---|---|
| `novo_agendamento` | Cliente faz agendamento via público ou chatbot |
| `agendamento_confirmado` | Cliente clica no link de confirmação do email |
| `pendente_confirmacao` | Horário do agendamento passou sem marcação de presença |

### Novos status em `agendamentos`

Adicionar `compareceu` e `no_show` ao `StatusAgendamento`:

```python
StatusAgendamento = Literal[
    "pendente", "confirmado", "cancelado",
    "reagendamento_solicitado", "compareceu", "no_show"
]
```

Campo adicional na tabela `agendamentos`:
```sql
compareceu_em TIMESTAMP  -- nullable, preenchido ao confirmar presença
```

---

## Backend

### Novos endpoints

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/notificacoes/` | Tenant | Lista notificações do estabelecimento. Params: `apenas_nao_lidas: bool = false`, `limite: int = 30` |
| `PATCH` | `/notificacoes/{id}/lida` | Tenant | Marca notificação como lida |
| `POST` | `/notificacoes/marcar-todas-lidas` | Tenant | Marca todas como lidas |
| `POST` | `/agendamentos/{id}/confirmar-presenca` | Tenant | Registra compareceu/no-show no agendamento |

### Payload de `confirmar-presenca`

```json
{ "compareceu": true }
```

Ao chamar este endpoint:
1. Atualiza `agendamentos.status` para `compareceu` ou `no_show`
2. Preenche `agendamentos.compareceu_em` com o timestamp atual
3. Marca a notificação `pendente_confirmacao` correspondente como lida

### Onde as notificações são criadas

**`novo_agendamento`**
- Inline via `BackgroundTasks` nas rotas:
  - `POST /agendamentos/` (admin)
  - `POST /public/agendar` (público)
  - Fluxo do chatbot (quando cria agendamento)

**`agendamento_confirmado`**
- Inline via `BackgroundTasks` na rota:
  - `POST /agendamentos/{token}/confirmar`

**`pendente_confirmacao`**
- Criada pelo job do APScheduler (já roda a cada 1 min)
- Consulta agendamentos onde:
  - `data_hora_fim < now()`
  - `status IN ('pendente', 'confirmado')` (sem marcação de presença)
  - Não existe notificação `pendente_confirmacao` para esse `agendamento_id`
- Cria uma notificação por agendamento elegível
- Garante idempotência: nunca cria duplicata

### Serviço de notificações

Novo arquivo `backend/app/services/notificacao_inapp_service.py`:

```python
def criar_notificacao(db, estabelecimento_id, agendamento_id, tipo, titulo, corpo) -> Notificacao
def criar_notificacao_novo_agendamento(db, agendamento) -> Notificacao
def criar_notificacao_confirmado(db, agendamento) -> Notificacao
def processar_pendentes_confirmacao(db) -> int  # retorna qtd criadas
```

---

## Frontend

### Componentes

#### `NotificacoesProvider` (Context)
- Envolve o layout autenticado
- Instancia `useNotificacoes()` e expõe o estado via Context
- Renderiza `<ToastContainer />` globalmente

#### `useNotificacoes()` (hook)
- Chama `GET /notificacoes/?apenas_nao_lidas=false&limite=30` a cada **15 segundos**
- Compara resultado com estado anterior — se chegou notificação nova, despacha toast
- Expõe:
  - `notificacoes: Notificacao[]`
  - `naoLidas: number`
  - `marcarLida(id: number): Promise<void>`
  - `marcarTodasLidas(): Promise<void>`
  - `confirmarPresenca(agendamentoId: number, compareceu: boolean): Promise<void>`

#### `NotificacoesSino`
- Ícone de sino no canto **direito** do header, junto ao avatar
- Badge vermelho com contagem de não-lidas (some quando `naoLidas === 0`)
- Clique abre dropdown com até 30 notificações
- Notificações lidas aparecem com opacidade reduzida
- Notificações `pendente_confirmacao` exibem botões **Compareceu / Faltou** inline
- Botão "Marcar todas como lidas" no topo do dropdown
- Rodapé "Ver todas as notificações →" — fora de escopo desta feature; link desabilitado ou oculto por ora
- Fecha ao clicar fora (click-outside handler)

#### `ToastNotificacao`
- Aparece no **canto inferior direito** da tela
- Máximo de 3 toasts simultâneos (os mais antigos saem primeiro)
- **Toast informativo** (`novo_agendamento`, `agendamento_confirmado`): fecha automaticamente em **5 segundos**
- **Toast de presença** (`pendente_confirmacao`): fica aberto até o dono agir (Compareceu / Faltou) ou fechar manualmente com ✕

**Cores por tipo:**
| Tipo | Borda | Cor do label |
|---|---|---|
| `novo_agendamento` | `#3b82f6` (azul) | `#60a5fa` |
| `agendamento_confirmado` | `#22c55e` (verde) | `#4ade80` |
| `pendente_confirmacao` | `#f59e0b` (âmbar) | `#fbbf24` |

### Onde o sino aparece

Presente em todas as páginas autenticadas: **Gestão**, **Agenda**, **Dashboard**, **Configurações**.

Ausente em páginas públicas: agendar, confirmar, cancelar, reagendar.

### Tipos TypeScript

```typescript
interface Notificacao {
  id: number
  agendamento_id: number | null
  tipo: 'novo_agendamento' | 'agendamento_confirmado' | 'pendente_confirmacao'
  titulo: string
  corpo: string | null
  lida: boolean
  criada_em: string
  lida_em: string | null
}
```

---

## Impacto nas Métricas do Dashboard

Os status `compareceu` e `no_show` alimentam as métricas existentes:
- Taxa de no-show (clientes que agendaram mas não compareceram)
- Faturamento estimado: a lógica do dashboard permanece inalterada por ora — continua contando agendamentos `confirmados`. Revisar cálculo em feature futura dedicada.

---

## Testes

### Backend

- Criar agendamento → notificação `novo_agendamento` gerada
- Confirmar via token → notificação `agendamento_confirmado` gerada
- Job do scheduler → cria `pendente_confirmacao` apenas para agendamentos com horário passado e sem marcação
- Job idempotente → segunda execução não duplica notificação
- `GET /notificacoes/` → retorna apenas notificações do tenant correto
- `POST /confirmar-presenca` com `compareceu: true` → status `compareceu`, `compareceu_em` preenchido, notificação marcada como lida
- `POST /confirmar-presenca` com `compareceu: false` → status `no_show`

### Frontend

- `useNotificacoes` detecta nova notificação no poll e despacha toast
- Toast informativo fecha automaticamente em 5s
- Toast de presença não fecha sozinho
- Contador do sino exibe apenas não-lidas
- Após confirmar presença, notificação `pendente_confirmacao` é removida da lista de pendentes
- Marcar todas como lidas → badge some

---

## Arquivos a Criar / Modificar

### Backend (novos)
- `backend/app/models/notificacao.py`
- `backend/app/schemas/notificacao.py`
- `backend/app/repositories/notificacao_repository.py`
- `backend/app/services/notificacao_inapp_service.py`
- `backend/app/routes/notificacoes.py`
- `backend/tests/test_notificacoes.py`

### Backend (modificar)
- `backend/app/models/agendamento.py` — adicionar `compareceu_em`, novos status
- `backend/app/schemas/agendamento.py` — adicionar `compareceu` e `no_show` ao `StatusAgendamento`
- `backend/app/routes/agendamentos.py` — BackgroundTasks para criar notificações + endpoint `confirmar-presenca`
- `backend/app/routes/public.py` — BackgroundTasks para criar notificação ao agendar publicamente
- `backend/app/services/scheduler.py` — chamar `processar_pendentes_confirmacao`
- `backend/app/main.py` — registrar router de notificações

### Frontend (novos)
- `frontend/app/components/NotificacoesProvider.tsx`
- `frontend/app/components/NotificacoesSino.tsx`
- `frontend/app/components/ToastNotificacao.tsx`
- `frontend/hooks/useNotificacoes.ts`
- `frontend/services/api.ts` — adicionar funções de notificações

### Frontend (modificar)
- `frontend/app/layout.tsx` ou layout autenticado — envolver com `NotificacoesProvider`
- `frontend/app/components/Header.tsx` — adicionar `<NotificacoesSino />`
