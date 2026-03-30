# Sistema de Notificações In-App — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar notificações in-app (sino + toasts) para o dono do estabelecimento, cobrindo novo agendamento, confirmação pelo cliente, e confirmação de presença (compareceu/no-show) com polling de 15s.

**Architecture:** Nova tabela `notificacoes` no banco. O backend gera registros nos eventos-chave via `BackgroundTasks` (nas rotas) e via APScheduler (para `pendente_confirmacao`). O frontend faz polling a cada 15s com o hook `useNotificacoes` e exibe toasts + sino.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite (tests), Next.js 14 App Router, React Context, TypeScript, CSS Modules, Lucide React.

---

## Mapa de Arquivos

### Backend — criar
- `backend/app/models/notificacao.py` — ORM model da tabela `notificacoes`
- `backend/app/schemas/notificacao.py` — Pydantic schemas de entrada/saída
- `backend/app/repositories/notificacao_repository.py` — queries de banco isoladas
- `backend/app/services/notificacao_inapp_service.py` — lógica de criação de notificações
- `backend/app/routes/notificacoes.py` — endpoints GET/PATCH
- `backend/tests/test_notificacoes.py` — testes TDD

### Backend — modificar
- `backend/app/models/agendamento.py` — adicionar `compareceu_em`
- `backend/app/schemas/agendamento.py` — adicionar `compareceu`/`no_show` ao `StatusAgendamento`
- `backend/app/services/agendamento_service.py` — adicionar `compareceu`/`no_show` a `STATUS_VALIDOS`
- `backend/app/routes/agendamentos.py` — adicionar `BackgroundTasks` para notificações + endpoint `confirmar-presenca`
- `backend/app/routes/public.py` — adicionar `BackgroundTasks` para notificação de novo agendamento
- `backend/app/services/scheduler.py` — chamar `processar_pendentes_confirmacao`
- `backend/app/models/__init__.py` — exportar `Notificacao`
- `backend/app/main.py` — registrar router de notificações
- `backend/tests/conftest.py` — incluir router de notificações no app de testes

### Frontend — criar
- `frontend/hooks/useNotificacoes.ts` — polling hook + state
- `frontend/app/components/NotificacoesProvider.tsx` — Context + renderiza toasts
- `frontend/app/components/ToastNotificacao.tsx` — componente de toast individual
- `frontend/app/components/NotificacoesSino.tsx` — sino com dropdown
- `frontend/app/components/ToastNotificacao.module.css` — estilos do toast
- `frontend/app/components/NotificacoesSino.module.css` — estilos do sino

### Frontend — modificar
- `frontend/services/api.ts` — tipos + funções de notificações
- `frontend/app/components/AppShell.tsx` — envolver com `NotificacoesProvider`
- `frontend/app/components/Header.tsx` — adicionar `<NotificacoesSino />`

---

## Task 1: Atualizar modelo e schema do Agendamento

**Files:**
- Modify: `backend/app/models/agendamento.py`
- Modify: `backend/app/schemas/agendamento.py`
- Modify: `backend/app/services/agendamento_service.py`

- [ ] **Step 1.1: Adicionar `compareceu_em` ao modelo ORM**

Em `backend/app/models/agendamento.py`, adicionar após `lembrete_2h_enviado`:

```python
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Time
# (imports existentes — não remover)
```

Adicionar campo ao modelo (antes dos synonyms):
```python
    compareceu_em = Column(DateTime, nullable=True)
```

O arquivo final terá a linha imediatamente após `lembrete_2h_enviado = Column(...)`:
```python
    lembrete_2h_enviado = Column(Boolean, nullable=False, default=False)
    compareceu_em = Column(DateTime, nullable=True)
```

- [ ] **Step 1.2: Adicionar novos status ao schema**

Em `backend/app/schemas/agendamento.py`, substituir a linha:

```python
StatusAgendamento = Literal["pendente", "confirmado", "cancelado", "reagendamento_solicitado"]
```

por:

```python
StatusAgendamento = Literal["pendente", "confirmado", "cancelado", "reagendamento_solicitado", "compareceu", "no_show"]
```

- [ ] **Step 1.3: Atualizar `STATUS_VALIDOS` no serviço**

Em `backend/app/services/agendamento_service.py`, substituir:

```python
STATUS_VALIDOS = {"pendente", "confirmado", "cancelado", "reagendamento_solicitado"}
```

por:

```python
STATUS_VALIDOS = {"pendente", "confirmado", "cancelado", "reagendamento_solicitado", "compareceu", "no_show"}
```

- [ ] **Step 1.4: Rodar os testes existentes para garantir nenhuma regressão**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -20
```

Esperado: todos os testes passam (sem falhas).

- [ ] **Step 1.5: Commit**

```bash
cd backend && git add app/models/agendamento.py app/schemas/agendamento.py app/services/agendamento_service.py
git commit -m "feat: add compareceu_em field and compareceu/no_show statuses to agendamento"
```

---

## Task 2: Criar modelo ORM `Notificacao`

**Files:**
- Create: `backend/app/models/notificacao.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 2.1: Criar o arquivo do modelo**

Criar `backend/app/models/notificacao.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.database import Base


class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        Index("ix_notificacoes_tenant_lida_criada", "estabelecimento_id", "lida", "criada_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    estabelecimento_id = Column(Integer, nullable=False, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id", ondelete="CASCADE"), nullable=True, index=True)
    tipo = Column(String(40), nullable=False)
    titulo = Column(String(255), nullable=False)
    corpo = Column(Text, nullable=True)
    lida = Column(Boolean, nullable=False, default=False)
    criada_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    lida_em = Column(DateTime, nullable=True)
```

- [ ] **Step 2.2: Registrar no `__init__.py`**

Em `backend/app/models/__init__.py`, adicionar:

```python
from app.models.notificacao import Notificacao
```

E adicionar `"Notificacao"` ao `__all__`:

```python
__all__ = [
    "Estabelecimento", "Profissional",
    "Agendamento", "Cliente", "Conversa", "Notificacao", "ReminderJob",
    "Servico", "WebhookEvent", "TokenBlacklist",
]
```

- [ ] **Step 2.3: Verificar que o modelo cria a tabela sem erros**

```bash
cd backend && python -c "from app.models.notificacao import Notificacao; print('OK:', Notificacao.__tablename__)"
```

Esperado: `OK: notificacoes`

- [ ] **Step 2.4: Commit**

```bash
git add backend/app/models/notificacao.py backend/app/models/__init__.py
git commit -m "feat: add Notificacao ORM model"
```

---

## Task 3: Criar schemas Pydantic para notificações

**Files:**
- Create: `backend/app/schemas/notificacao.py`

- [ ] **Step 3.1: Criar o arquivo de schemas**

Criar `backend/app/schemas/notificacao.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


TipoNotificacao = Literal["novo_agendamento", "agendamento_confirmado", "pendente_confirmacao"]


class NotificacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agendamento_id: int | None
    tipo: TipoNotificacao
    titulo: str
    corpo: str | None
    lida: bool
    criada_em: datetime
    lida_em: datetime | None


class ConfirmarPresencaPayload(BaseModel):
    compareceu: bool
```

- [ ] **Step 3.2: Verificar importação**

```bash
cd backend && python -c "from app.schemas.notificacao import NotificacaoResponse, ConfirmarPresencaPayload; print('OK')"
```

Esperado: `OK`

- [ ] **Step 3.3: Commit**

```bash
git add backend/app/schemas/notificacao.py
git commit -m "feat: add Notificacao pydantic schemas"
```

---

## Task 4: Criar repositório de notificações

**Files:**
- Create: `backend/app/repositories/notificacao_repository.py`

- [ ] **Step 4.1: Criar o arquivo do repositório**

Criar `backend/app/repositories/notificacao_repository.py`:

```python
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.notificacao import Notificacao


def criar(
    db: Session,
    *,
    estabelecimento_id: int,
    tipo: str,
    titulo: str,
    corpo: str | None = None,
    agendamento_id: int | None = None,
) -> Notificacao:
    notif = Notificacao(
        estabelecimento_id=estabelecimento_id,
        agendamento_id=agendamento_id,
        tipo=tipo,
        titulo=titulo,
        corpo=corpo,
    )
    db.add(notif)
    db.flush()  # obtém o id sem commit
    return notif


def listar(
    db: Session,
    *,
    estabelecimento_id: int,
    apenas_nao_lidas: bool = False,
    limite: int = 30,
) -> list[Notificacao]:
    q = db.query(Notificacao).filter(Notificacao.estabelecimento_id == estabelecimento_id)
    if apenas_nao_lidas:
        q = q.filter(Notificacao.lida.is_(False))
    return q.order_by(Notificacao.criada_em.desc()).limit(limite).all()


def marcar_lida(db: Session, *, notificacao_id: int, estabelecimento_id: int) -> Notificacao | None:
    notif = (
        db.query(Notificacao)
        .filter(Notificacao.id == notificacao_id, Notificacao.estabelecimento_id == estabelecimento_id)
        .first()
    )
    if notif and not notif.lida:
        notif.lida = True
        notif.lida_em = datetime.utcnow()
        db.flush()
    return notif


def marcar_todas_lidas(db: Session, *, estabelecimento_id: int) -> int:
    count = (
        db.query(Notificacao)
        .filter(Notificacao.estabelecimento_id == estabelecimento_id, Notificacao.lida.is_(False))
        .update({"lida": True, "lida_em": datetime.utcnow()}, synchronize_session=False)
    )
    db.flush()
    return count


def existe_pendente_confirmacao(db: Session, *, agendamento_id: int) -> bool:
    """Verifica se já existe notificação pendente_confirmacao para este agendamento (idempotência)."""
    return (
        db.query(Notificacao.id)
        .filter(
            Notificacao.agendamento_id == agendamento_id,
            Notificacao.tipo == "pendente_confirmacao",
        )
        .first()
    ) is not None


def marcar_lida_por_agendamento_e_tipo(
    db: Session, *, agendamento_id: int, tipo: str
) -> None:
    """Marca como lida a notificação de um agendamento específico (ex: após confirmar presença)."""
    db.query(Notificacao).filter(
        Notificacao.agendamento_id == agendamento_id,
        Notificacao.tipo == tipo,
        Notificacao.lida.is_(False),
    ).update({"lida": True, "lida_em": datetime.utcnow()}, synchronize_session=False)
    db.flush()
```

- [ ] **Step 4.2: Verificar importação**

```bash
cd backend && python -c "from app.repositories.notificacao_repository import criar, listar; print('OK')"
```

Esperado: `OK`

- [ ] **Step 4.3: Commit**

```bash
git add backend/app/repositories/notificacao_repository.py
git commit -m "feat: add notificacao_repository with CRUD and idempotency check"
```

---

## Task 5: Criar serviço `notificacao_inapp_service`

**Files:**
- Create: `backend/app/services/notificacao_inapp_service.py`

- [ ] **Step 5.1: Criar o arquivo do serviço**

Criar `backend/app/services/notificacao_inapp_service.py`:

```python
import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.agendamento import Agendamento
from app.repositories import notificacao_repository as repo

logger = logging.getLogger(__name__)


def _corpo_agendamento(agendamento: Agendamento) -> str:
    cliente = agendamento.cliente_nome or "Cliente"
    servico = agendamento.servico.nome if agendamento.servico else "Serviço"
    data_str = agendamento.data_hora_inicio.strftime("%d/%m %H:%M") if agendamento.data_hora_inicio else ""
    return f"{cliente} · {servico} · {data_str}"


def criar_notificacao_novo_agendamento(db: Session, agendamento: Agendamento) -> None:
    """Chamado com db próprio ao criar um agendamento (via wrapper de background task)."""
    try:
        repo.criar(
            db,
            estabelecimento_id=agendamento.estabelecimento_id,
            agendamento_id=agendamento.id,
            tipo="novo_agendamento",
            titulo="Novo agendamento",
            corpo=_corpo_agendamento(agendamento),
        )
        db.commit()
    except Exception:
        logger.exception("Erro ao criar notificacao novo_agendamento para agendamento %s", agendamento.id)
        db.rollback()


def criar_notificacao_confirmado(db: Session, agendamento: Agendamento) -> None:
    """Chamado com db próprio quando o cliente confirma pelo link de email."""
    try:
        repo.criar(
            db,
            estabelecimento_id=agendamento.estabelecimento_id,
            agendamento_id=agendamento.id,
            tipo="agendamento_confirmado",
            titulo="Agendamento confirmado",
            corpo=_corpo_agendamento(agendamento),
        )
        db.commit()
    except Exception:
        logger.exception("Erro ao criar notificacao agendamento_confirmado para agendamento %s", agendamento.id)
        db.rollback()


# ── Wrappers para BackgroundTasks ────────────────────────────────────────────
# Criam sua própria sessão para não depender da sessão da requisição HTTP.

def task_notificacao_novo_agendamento(agendamento_id: int) -> None:
    """Versão para BackgroundTasks — cria sessão própria."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ag = (
            db.query(Agendamento)
            .options(joinedload(Agendamento.servico))
            .filter(Agendamento.id == agendamento_id)
            .first()
        )
        if ag:
            criar_notificacao_novo_agendamento(db, ag)
    finally:
        db.close()


def task_notificacao_confirmado(agendamento_id: int) -> None:
    """Versão para BackgroundTasks — cria sessão própria."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ag = (
            db.query(Agendamento)
            .options(joinedload(Agendamento.servico))
            .filter(Agendamento.id == agendamento_id)
            .first()
        )
        if ag:
            criar_notificacao_confirmado(db, ag)
    finally:
        db.close()


def processar_pendentes_confirmacao(db: Session) -> int:
    """
    Chamado pelo APScheduler a cada minuto.
    Cria notificações pendente_confirmacao para agendamentos cujo horário já passou
    e que ainda não têm marcação de presença. Idempotente.
    """
    agora = datetime.utcnow()
    try:
        agendamentos = (
            db.query(Agendamento)
            .filter(
                Agendamento.data_hora_fim < agora,
                Agendamento.status.in_(["pendente", "confirmado"]),
            )
            .all()
        )

        criados = 0
        for ag in agendamentos:
            if repo.existe_pendente_confirmacao(db, agendamento_id=ag.id):
                continue

            cliente = ag.cliente_nome or "Cliente"
            servico = ag.servico.nome if ag.servico else "Serviço"
            data_str = ag.data_hora_inicio.strftime("%d/%m %H:%M") if ag.data_hora_inicio else ""
            repo.criar(
                db,
                estabelecimento_id=ag.estabelecimento_id,
                agendamento_id=ag.id,
                tipo="pendente_confirmacao",
                titulo="Confirmar presença",
                corpo=f"{cliente} · {servico} · {data_str}",
            )
            criados += 1

        if criados:
            db.commit()
            logger.info("Criadas %s notificações pendente_confirmacao.", criados)

        return criados
    except Exception:
        logger.exception("Erro ao processar pendentes de confirmacao.")
        db.rollback()
        return 0
```

- [ ] **Step 5.2: Verificar importação**

```bash
cd backend && python -c "from app.services.notificacao_inapp_service import processar_pendentes_confirmacao; print('OK')"
```

Esperado: `OK`

- [ ] **Step 5.3: Commit**

```bash
git add backend/app/services/notificacao_inapp_service.py
git commit -m "feat: add notificacao_inapp_service with event helpers and scheduler job"
```

---

## Task 6: Criar rota `/notificacoes` + endpoint `confirmar-presenca`

**Files:**
- Create: `backend/app/routes/notificacoes.py`
- Modify: `backend/app/routes/agendamentos.py`

- [ ] **Step 6.1: Criar `backend/app/routes/notificacoes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import notificacao_repository as repo
from app.routes.deps import tenant_id_from_header
from app.schemas.notificacao import NotificacaoResponse

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


@router.get("/", response_model=list[NotificacaoResponse])
def listar_notificacoes(
    apenas_nao_lidas: bool = False,
    limite: int = 30,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    return repo.listar(db, estabelecimento_id=tenant_id, apenas_nao_lidas=apenas_nao_lidas, limite=limite)


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_lida(
    notificacao_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    notif = repo.marcar_lida(db, notificacao_id=notificacao_id, estabelecimento_id=tenant_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/marcar-todas-lidas")
def marcar_todas_lidas(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    count = repo.marcar_todas_lidas(db, estabelecimento_id=tenant_id)
    db.commit()
    return {"marcadas": count}
```

- [ ] **Step 6.2: Adicionar endpoint `confirmar-presenca` em `backend/app/routes/agendamentos.py`**

Adicionar imports no topo do arquivo (após os existentes):

```python
from datetime import datetime as _datetime

from app.repositories import notificacao_repository as notif_repo
from app.schemas.notificacao import ConfirmarPresencaPayload
```

Adicionar o endpoint ao final do arquivo (antes do último `@router.delete`):

```python
@router.post("/{agendamento_id}/confirmar-presenca", response_model=AgendamentoResponse)
def confirmar_presenca(
    agendamento_id: int,
    dados: ConfirmarPresencaPayload,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    agendamento = (
        db.query(AgendamentoModel)
        .filter(AgendamentoModel.id == agendamento_id, AgendamentoModel.estabelecimento_id == tenant_id)
        .first()
    )
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    agendamento.status = "compareceu" if dados.compareceu else "no_show"
    agendamento.compareceu_em = _datetime.utcnow()

    notif_repo.marcar_lida_por_agendamento_e_tipo(
        db, agendamento_id=agendamento_id, tipo="pendente_confirmacao"
    )

    db.commit()
    db.refresh(agendamento)
    from app.services.agendamento_service import _serializar_agendamento
    return _serializar_agendamento(agendamento)
```

- [ ] **Step 6.3: Verificar importações**

```bash
cd backend && python -c "from app.routes.notificacoes import router; print('OK')"
cd backend && python -c "from app.routes.agendamentos import router; print('OK')"
```

Esperado: `OK` em ambos.

- [ ] **Step 6.4: Commit**

```bash
git add backend/app/routes/notificacoes.py backend/app/routes/agendamentos.py
git commit -m "feat: add /notificacoes routes and confirmar-presenca endpoint"
```

---

## Task 7: Injetar criação de notificações nas rotas existentes

**Files:**
- Modify: `backend/app/routes/agendamentos.py`
- Modify: `backend/app/routes/public.py`

- [ ] **Step 7.1: Notificar ao criar agendamento admin**

Em `backend/app/routes/agendamentos.py`, adicionar import no topo (após os imports existentes):

```python
from app.services.notificacao_inapp_service import (
    task_notificacao_novo_agendamento,
    task_notificacao_confirmado,
)
```

No handler `criar`, substituir o bloco `try` completo por:

```python
    try:
        agendamento = criar_agendamento(db, dados, tenant_id=tenant_id)
        payload = obter_payload_email_confirmacao(db, agendamento_id=agendamento["id"])
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        background_tasks.add_task(task_notificacao_novo_agendamento, agendamento["id"])
        return agendamento
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 7.2: Notificar quando cliente confirma pelo token**

Em `backend/app/routes/agendamentos.py`, no handler `confirmar_por_token`, substituir o bloco `try` completo por:

```python
    try:
        dados = atualizar_status_agendamento_por_token(db, token, "confirmado")
        payload = obter_payload_email_status(db, token=token, tipo="confirmado")
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        # obtém o id do agendamento para a task
        ag = db.query(AgendamentoModel).filter(AgendamentoModel.confirmation_token == token).first()
        if ag:
            background_tasks.add_task(task_notificacao_confirmado, ag.id)
        return dados
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "inválido" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc
```

- [ ] **Step 7.3: Notificar ao criar agendamento público**

Em `backend/app/routes/public.py`, adicionar import no topo:

```python
from app.services.notificacao_inapp_service import task_notificacao_novo_agendamento
```

No handler `criar_agendamento_public`, substituir o bloco `try` completo por:

```python
    try:
        agendamento = criar_agendamento_publico(
            db,
            slug=dados.slug,
            barbearia_id=dados.barbearia_id,
            cliente_nome=dados.cliente_nome,
            cliente_telefone=dados.cliente_telefone,
            cliente_email=dados.cliente_email,
            barbeiro_id=dados.barbeiro_id,
            servico_id=dados.servico_id,
            data=dados.data,
            hora_inicio=dados.hora_inicio,
        )
        payload = obter_payload_email_confirmacao(db, agendamento_id=agendamento["id"])
        if payload:
            background_tasks.add_task(send_email_payload, payload)
        background_tasks.add_task(task_notificacao_novo_agendamento, agendamento["id"])
        return agendamento
    except ValueError as exc:
        mensagem = str(exc)
        status_code = 404 if "nao encontrada" in mensagem.lower() else 400
        raise HTTPException(status_code=status_code, detail=mensagem) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro interno ao criar agendamento.") from exc
```

- [ ] **Step 7.4: Rodar testes existentes para verificar nenhuma regressão**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -20
```

Esperado: todos os testes passam.

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/routes/agendamentos.py backend/app/routes/public.py
git commit -m "feat: wire in-app notification creation in agendamento and public routes"
```

---

## Task 8: Conectar scheduler ao `processar_pendentes_confirmacao`

**Files:**
- Modify: `backend/app/services/scheduler.py`

- [ ] **Step 8.1: Adicionar job no scheduler**

Em `backend/app/services/scheduler.py`, na função `start_scheduler`, adicionar o segundo job após o existente:

```python
        scheduler.add_job(
            processar_lembretes_email_pendentes,
            "interval",
            minutes=1,
            id="email-reminders",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        # --- novo job ---
        scheduler.add_job(
            _processar_notificacoes_pendentes,
            "interval",
            minutes=1,
            id="inapp-notifications",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
        )
        # -----------------
```

Adicionar a função wrapper no topo do arquivo (após os imports):

```python
def _processar_notificacoes_pendentes():
    from app.services.notificacao_inapp_service import processar_pendentes_confirmacao
    db = SessionLocal()
    try:
        processar_pendentes_confirmacao(db)
    finally:
        db.close()
```

- [ ] **Step 8.2: Verificar importação**

```bash
cd backend && python -c "from app.services.scheduler import start_scheduler; print('OK')"
```

Esperado: `OK`

- [ ] **Step 8.3: Commit**

```bash
git add backend/app/services/scheduler.py
git commit -m "feat: add scheduler job for pendente_confirmacao notifications"
```

---

## Task 9: Registrar router + atualizar `conftest.py`

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 9.1: Registrar router em `main.py`**

Em `backend/app/main.py`, adicionar no bloco de imports de routes:

```python
from app.routes import (
    agenda,
    agendamentos,
    auth,
    chatbot,
    clientes,
    configuracoes,
    dashboard,
    estabelecimento_funcionamento,
    estabelecimentos,
    internal,
    notificacoes,          # <-- adicionar
    profissionais,
    public,
    servicos,
    webhook,
    webhooks,
    whatsapp,
)
```

E adicionar no bloco `include_router`:

```python
app.include_router(notificacoes.router)
```

- [ ] **Step 9.2: Adicionar router no `conftest.py` de testes**

Em `backend/tests/conftest.py`, adicionar no import:

```python
from app.routes import agenda, agendamentos, chatbot, barbeiros, barbearia_funcionamento, clientes, servicos, whatsapp, barbearias, auth, webhooks, public, internal, webhook, estabelecimentos, profissionais, estabelecimento_funcionamento, configuracoes, dashboard, notificacoes
```

E dentro da fixture `app`, adicionar:

```python
    test_app.include_router(notificacoes.router)
```

Também adicionar o import do modelo para garantir que a tabela seja criada:

```python
from app.models.notificacao import Notificacao  # garante criação da tabela no SQLite
```

- [ ] **Step 9.3: Verificar que a app sobe sem erros**

```bash
cd backend && python -c "from app.main import app; print('rotas:', [r.path for r in app.routes if hasattr(r, 'path')])" 2>&1 | grep notif
```

Esperado: `/notificacoes/` e `/notificacoes/{notificacao_id}/lida` aparecendo na lista.

- [ ] **Step 9.4: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py
git commit -m "feat: register notificacoes router in main and test conftest"
```

---

## Task 10: Escrever testes de backend

**Files:**
- Create: `backend/tests/test_notificacoes.py`

- [ ] **Step 10.1: Escrever os testes**

Criar `backend/tests/test_notificacoes.py`:

```python
from datetime import datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.notificacao import Notificacao
from app.repositories import notificacao_repository as repo
from app.services.notificacao_inapp_service import (
    criar_notificacao_confirmado,
    criar_notificacao_novo_agendamento,
    processar_pendentes_confirmacao,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _criar_agendamento(db_session, dados_base, *, hora_inicio=None, status="pendente"):
    barbearia = dados_base["barbearia"]
    barbeiro = dados_base["barbeiro"]
    servico = dados_base["servico"]
    inicio = hora_inicio or dados_base["amanha"]
    fim = inicio + timedelta(minutes=servico.duracao_minutos)

    from app.models.cliente import Cliente
    cliente = Cliente(telefone="11999999999", nome="Teste", barbearia_id=barbearia.id)
    db_session.add(cliente)
    db_session.flush()

    ag = Agendamento(
        cliente_id=cliente.id,
        profissional_id=barbeiro.id,
        servico_id=servico.id,
        estabelecimento_id=barbearia.id,
        cliente_nome="Teste",
        cliente_telefone="11999999999",
        data=inicio.date(),
        hora_inicio=inicio.time(),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        status=status,
    )
    db_session.add(ag)
    db_session.commit()
    db_session.refresh(ag)
    return ag


# ── testes do repositório ─────────────────────────────────────────────────────

def test_criar_notificacao_basica(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    notif = repo.criar(
        db_session,
        estabelecimento_id=barbearia.id,
        tipo="novo_agendamento",
        titulo="Novo agendamento",
        corpo="Teste · Corte · 01/01 10:00",
    )
    db_session.commit()
    assert notif.id is not None
    assert notif.lida is False
    assert notif.estabelecimento_id == barbearia.id


def test_listar_apenas_nao_lidas(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="A")
    notif_lida = repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="B")
    notif_lida.lida = True
    db_session.commit()

    todas = repo.listar(db_session, estabelecimento_id=barbearia.id)
    nao_lidas = repo.listar(db_session, estabelecimento_id=barbearia.id, apenas_nao_lidas=True)
    assert len(todas) == 2
    assert len(nao_lidas) == 1
    assert nao_lidas[0].titulo == "A"


def test_isolamento_tenant(db_session, dados_base):
    from app.models.estabelecimento import Estabelecimento as Est
    outro = Est(nome="Outro", endereco="Rua 2")
    db_session.add(outro)
    db_session.commit()

    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="Minha")
    repo.criar(db_session, estabelecimento_id=outro.id, tipo="novo_agendamento", titulo="Outra")
    db_session.commit()

    minhas = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(minhas) == 1
    assert minhas[0].titulo == "Minha"


def test_existe_pendente_confirmacao_idempotente(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base)
    assert repo.existe_pendente_confirmacao(db_session, agendamento_id=ag.id) is False
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, agendamento_id=ag.id, tipo="pendente_confirmacao", titulo="Confirmar")
    db_session.commit()
    assert repo.existe_pendente_confirmacao(db_session, agendamento_id=ag.id) is True


def test_marcar_todas_lidas(db_session, dados_base):
    barbearia = dados_base["barbearia"]
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="A")
    repo.criar(db_session, estabelecimento_id=barbearia.id, tipo="novo_agendamento", titulo="B")
    db_session.commit()

    count = repo.marcar_todas_lidas(db_session, estabelecimento_id=barbearia.id)
    db_session.commit()
    assert count == 2
    nao_lidas = repo.listar(db_session, estabelecimento_id=barbearia.id, apenas_nao_lidas=True)
    assert len(nao_lidas) == 0


# ── testes do serviço ─────────────────────────────────────────────────────────

def test_criar_notificacao_novo_agendamento(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base)
    criar_notificacao_novo_agendamento(db_session, ag)

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(notifs) == 1
    assert notifs[0].tipo == "novo_agendamento"
    assert notifs[0].agendamento_id == ag.id


def test_criar_notificacao_confirmado(db_session, dados_base):
    ag = _criar_agendamento(db_session, dados_base, status="confirmado")
    criar_notificacao_confirmado(db_session, ag)

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    assert len(notifs) == 1
    assert notifs[0].tipo == "agendamento_confirmado"


def test_processar_pendentes_apenas_horario_passado(db_session, dados_base):
    futuro = _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() + timedelta(hours=2))
    passado = _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2))

    count = processar_pendentes_confirmacao(db_session)
    assert count == 1

    notifs = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id)
    tipos = [n.tipo for n in notifs]
    assert "pendente_confirmacao" in tipos
    assert all(n.agendamento_id == passado.id for n in notifs if n.tipo == "pendente_confirmacao")


def test_processar_pendentes_idempotente(db_session, dados_base):
    _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2))

    count1 = processar_pendentes_confirmacao(db_session)
    count2 = processar_pendentes_confirmacao(db_session)
    assert count1 == 1
    assert count2 == 0  # segunda execução não duplica


def test_processar_pendentes_ignora_status_invalido(db_session, dados_base):
    _criar_agendamento(db_session, dados_base, hora_inicio=datetime.now() - timedelta(hours=2), status="cancelado")
    count = processar_pendentes_confirmacao(db_session)
    assert count == 0


# ── testes de endpoint via HTTP ───────────────────────────────────────────────

def test_get_notificacoes_vazio(client, tenant_headers):
    res = client.get("/notificacoes/", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_get_notificacoes_retorna_do_tenant(client, db_session, dados_base, tenant_headers):
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="Minha notif")
    db_session.commit()

    res = client.get("/notificacoes/", headers=tenant_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "Minha notif"
    assert data[0]["lida"] is False


def test_marcar_lida_endpoint(client, db_session, dados_base, tenant_headers):
    notif = repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="X")
    db_session.commit()

    res = client.patch(f"/notificacoes/{notif.id}/lida", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json()["lida"] is True


def test_marcar_todas_lidas_endpoint(client, db_session, dados_base, tenant_headers):
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="A")
    repo.criar(db_session, estabelecimento_id=dados_base["barbearia"].id, tipo="novo_agendamento", titulo="B")
    db_session.commit()

    res = client.post("/notificacoes/marcar-todas-lidas", headers=tenant_headers)
    assert res.status_code == 200
    assert res.json()["marcadas"] == 2


def test_confirmar_presenca_compareceu(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)

    res = client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": True},
        headers=tenant_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "compareceu"

    db_session.refresh(ag)
    assert ag.status == "compareceu"
    assert ag.compareceu_em is not None


def test_confirmar_presenca_no_show(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)

    res = client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": False},
        headers=tenant_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "no_show"


def test_confirmar_presenca_marca_notificacao_lida(client, db_session, dados_base, tenant_headers):
    ag = _criar_agendamento(db_session, dados_base)
    repo.criar(
        db_session,
        estabelecimento_id=dados_base["barbearia"].id,
        agendamento_id=ag.id,
        tipo="pendente_confirmacao",
        titulo="Confirmar presença",
    )
    db_session.commit()

    client.post(
        f"/agendamentos/{ag.id}/confirmar-presenca",
        json={"compareceu": True},
        headers=tenant_headers,
    )

    nao_lidas = repo.listar(db_session, estabelecimento_id=dados_base["barbearia"].id, apenas_nao_lidas=True)
    assert len(nao_lidas) == 0
```

- [ ] **Step 10.2: Rodar os testes novos para confirmar que passam**

```bash
cd backend && python -m pytest tests/test_notificacoes.py -v 2>&1 | tail -40
```

Esperado: todos os testes passam (`PASSED`).

- [ ] **Step 10.3: Rodar a suite completa para garantir nenhuma regressão**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -20
```

Esperado: todos os testes passam.

- [ ] **Step 10.4: Commit**

```bash
git add backend/tests/test_notificacoes.py
git commit -m "test: add comprehensive tests for in-app notification system"
```

---

## Task 11: Frontend — tipos TypeScript + funções de API

**Files:**
- Modify: `frontend/services/api.ts`

- [ ] **Step 11.1: Adicionar tipo `Notificacao` e atualizar `Agendamento`**

Em `frontend/services/api.ts`, substituir o tipo `Agendamento`:

```typescript
export type Agendamento = {
  id: number;
  cliente_nome: string;
  telefone: string;
  cliente_email?: string | null;
  barbeiro_nome: string;
  servico_nome: string;
  data_hora_inicio: string;
  data_hora_fim: string;
  status: "pendente" | "confirmado" | "cancelado" | "reagendamento_solicitado" | "compareceu" | "no_show";
};
```

Adicionar após o tipo `Agendamento`:

```typescript
export type TipoNotificacao = "novo_agendamento" | "agendamento_confirmado" | "pendente_confirmacao";

export type Notificacao = {
  id: number;
  agendamento_id: number | null;
  tipo: TipoNotificacao;
  titulo: string;
  corpo: string | null;
  lida: boolean;
  criada_em: string;
  lida_em: string | null;
};
```

- [ ] **Step 11.2: Adicionar funções de notificação**

Adicionar ao final de `frontend/services/api.ts` (antes do último export se houver, ou no final):

```typescript
export async function listNotificacoes(params?: {
  apenas_nao_lidas?: boolean;
  limite?: number;
}): Promise<Notificacao[]> {
  const qs = new URLSearchParams();
  if (params?.apenas_nao_lidas) qs.set("apenas_nao_lidas", "true");
  if (params?.limite) qs.set("limite", String(params.limite));
  const res = await apiFetch(`/notificacoes/?${qs}`, { cache: "no-store" });
  return parseOrThrow(res, "Falha ao carregar notificações.");
}

export async function marcarNotificacaoLida(id: number): Promise<Notificacao> {
  const res = await apiFetch(`/notificacoes/${id}/lida`, { method: "PATCH" });
  return parseOrThrow(res, "Falha ao marcar notificação como lida.");
}

export async function marcarTodasNotificacoesLidas(): Promise<{ marcadas: number }> {
  const res = await apiFetch("/notificacoes/marcar-todas-lidas", { method: "POST" });
  return parseOrThrow(res, "Falha ao marcar todas as notificações como lidas.");
}

export async function confirmarPresenca(
  agendamentoId: number,
  compareceu: boolean
): Promise<Agendamento> {
  const res = await apiFetch(`/agendamentos/${agendamentoId}/confirmar-presenca`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ compareceu }),
  });
  return parseOrThrow(res, "Falha ao confirmar presença.");
}
```

- [ ] **Step 11.3: Verificar compilação TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 11.4: Commit**

```bash
git add frontend/services/api.ts
git commit -m "feat: add Notificacao types and API functions to frontend"
```

---

## Task 12: Frontend — hook `useNotificacoes`

**Files:**
- Create: `frontend/hooks/useNotificacoes.ts`

- [ ] **Step 12.1: Criar o hook**

Criar `frontend/hooks/useNotificacoes.ts`:

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type Notificacao,
  confirmarPresenca,
  listNotificacoes,
  marcarNotificacaoLida,
  marcarTodasNotificacoesLidas,
} from "@/services/api";

const POLL_INTERVAL_MS = 15_000;

export type UseNotificacoesReturn = {
  notificacoes: Notificacao[];
  naoLidas: number;
  novasIds: number[];           // ids das notificações que chegaram no último poll (para disparar toasts)
  confirmarNovaVista: () => void; // limpa novasIds após exibir os toasts
  marcarLida: (id: number) => Promise<void>;
  marcarTodasLidas: () => Promise<void>;
  confirmarPresencaAgendamento: (agendamentoId: number, compareceu: boolean) => Promise<void>;
};

export function useNotificacoes(): UseNotificacoesReturn {
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [novasIds, setNovasIds] = useState<number[]>([]);
  const knownIdsRef = useRef<Set<number>>(new Set());

  const fetchNotificacoes = useCallback(async () => {
    try {
      const data = await listNotificacoes({ limite: 30 });
      setNotificacoes(data);

      const fetchedIds = data.map((n) => n.id);
      const recemChegadas = fetchedIds.filter((id) => !knownIdsRef.current.has(id));

      if (recemChegadas.length > 0 && knownIdsRef.current.size > 0) {
        // só dispara toasts se não for o primeiro load (evita toasts ao abrir a página)
        setNovasIds(recemChegadas);
      }

      knownIdsRef.current = new Set(fetchedIds);
    } catch {
      // silently fail — polling retenta no próximo ciclo
    }
  }, []);

  useEffect(() => {
    fetchNotificacoes();
    const interval = setInterval(fetchNotificacoes, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchNotificacoes]);

  const confirmarNovaVista = useCallback(() => setNovasIds([]), []);

  const marcarLida = useCallback(
    async (id: number) => {
      await marcarNotificacaoLida(id);
      setNotificacoes((prev) =>
        prev.map((n) => (n.id === id ? { ...n, lida: true } : n))
      );
    },
    []
  );

  const marcarTodasLidas = useCallback(async () => {
    await marcarTodasNotificacoesLidas();
    setNotificacoes((prev) => prev.map((n) => ({ ...n, lida: true })));
  }, []);

  const confirmarPresencaAgendamento = useCallback(
    async (agendamentoId: number, compareceu: boolean) => {
      await confirmarPresenca(agendamentoId, compareceu);
      // Atualiza local: remove a notificação pendente_confirmacao do agendamento
      setNotificacoes((prev) =>
        prev.map((n) =>
          n.agendamento_id === agendamentoId && n.tipo === "pendente_confirmacao"
            ? { ...n, lida: true }
            : n
        )
      );
    },
    []
  );

  const naoLidas = notificacoes.filter((n) => !n.lida).length;

  return {
    notificacoes,
    naoLidas,
    novasIds,
    confirmarNovaVista,
    marcarLida,
    marcarTodasLidas,
    confirmarPresencaAgendamento,
  };
}
```

- [ ] **Step 12.2: Verificar compilação TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 12.3: Commit**

```bash
git add frontend/hooks/useNotificacoes.ts
git commit -m "feat: add useNotificacoes polling hook"
```

---

## Task 13: Frontend — componente `ToastNotificacao`

**Files:**
- Create: `frontend/app/components/ToastNotificacao.tsx`
- Create: `frontend/app/components/ToastNotificacao.module.css`

- [ ] **Step 13.1: Criar CSS do toast**

Criar `frontend/app/components/ToastNotificacao.module.css`:

```css
.container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.toast {
  pointer-events: all;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border-left: 4px solid var(--accent);
  box-shadow: var(--shadow-lg);
  padding: 12px 14px;
  width: 280px;
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from { transform: translateX(20px); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}

.toast.novo_agendamento { border-left-color: #3b82f6; }
.toast.agendamento_confirmado { border-left-color: #22c55e; }
.toast.pendente_confirmacao { border-left-color: #f59e0b; }

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 4px;
}

.tipo {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.tipo.novo_agendamento { color: #3b82f6; }
.tipo.agendamento_confirmado { color: #22c55e; }
.tipo.pendente_confirmacao { color: #f59e0b; }

.close {
  background: none;
  border: none;
  color: var(--ink-subtle);
  cursor: pointer;
  padding: 0;
  line-height: 1;
  font-size: 14px;
}

.titulo {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 2px;
}

.corpo {
  font-size: 11px;
  color: var(--ink-subtle);
  margin-bottom: 0;
}

.acoes {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.btnCompareceu {
  flex: 1;
  background: #22c55e;
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-body);
}

.btnFaltou {
  flex: 1;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-body);
}

@media (max-width: 480px) {
  .container {
    bottom: 16px;
    right: 12px;
    left: 12px;
  }
  .toast {
    width: 100%;
  }
}
```

- [ ] **Step 13.2: Criar componente do toast**

Criar `frontend/app/components/ToastNotificacao.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { type Notificacao } from "@/services/api";
import styles from "./ToastNotificacao.module.css";

const LABELS: Record<string, string> = {
  novo_agendamento: "📅 Novo agendamento",
  agendamento_confirmado: "✅ Confirmado pelo cliente",
  pendente_confirmacao: "⏳ Confirmar presença",
};

type ToastProps = {
  notificacao: Notificacao;
  onClose: (id: number) => void;
  onCompareceu?: (agendamentoId: number, compareceu: boolean) => void;
};

function Toast({ notificacao, onClose, onCompareceu }: ToastProps) {
  const isPendente = notificacao.tipo === "pendente_confirmacao";

  useEffect(() => {
    if (isPendente) return; // toasts de presença não fecham sozinhos
    const t = setTimeout(() => onClose(notificacao.id), 5000);
    return () => clearTimeout(t);
  }, [isPendente, notificacao.id, onClose]);

  return (
    <div className={`${styles.toast} ${styles[notificacao.tipo]}`} role="alert">
      <div className={styles.header}>
        <span className={`${styles.tipo} ${styles[notificacao.tipo]}`}>
          {LABELS[notificacao.tipo] ?? notificacao.tipo}
        </span>
        <button className={styles.close} onClick={() => onClose(notificacao.id)} aria-label="Fechar">
          ✕
        </button>
      </div>
      <div className={styles.titulo}>{notificacao.titulo}</div>
      {notificacao.corpo && <div className={styles.corpo}>{notificacao.corpo}</div>}
      {isPendente && notificacao.agendamento_id && onCompareceu && (
        <div className={styles.acoes}>
          <button
            className={styles.btnCompareceu}
            onClick={() => {
              onCompareceu(notificacao.agendamento_id!, true);
              onClose(notificacao.id);
            }}
          >
            ✓ Compareceu
          </button>
          <button
            className={styles.btnFaltou}
            onClick={() => {
              onCompareceu(notificacao.agendamento_id!, false);
              onClose(notificacao.id);
            }}
          >
            ✕ Faltou
          </button>
        </div>
      )}
    </div>
  );
}

type ToastContainerProps = {
  toasts: Notificacao[];
  onClose: (id: number) => void;
  onCompareceu: (agendamentoId: number, compareceu: boolean) => void;
};

export function ToastContainer({ toasts, onClose, onCompareceu }: ToastContainerProps) {
  if (toasts.length === 0) return null;
  return (
    <div className={styles.container}>
      {toasts.slice(0, 3).map((n) => (
        <Toast key={n.id} notificacao={n} onClose={onClose} onCompareceu={onCompareceu} />
      ))}
    </div>
  );
}
```

- [ ] **Step 13.3: Verificar compilação TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 13.4: Commit**

```bash
git add frontend/app/components/ToastNotificacao.tsx frontend/app/components/ToastNotificacao.module.css
git commit -m "feat: add ToastNotificacao component with auto-close and presence actions"
```

---

## Task 14: Frontend — componente `NotificacoesSino`

**Files:**
- Create: `frontend/app/components/NotificacoesSino.tsx`
- Create: `frontend/app/components/NotificacoesSino.module.css`

- [ ] **Step 14.1: Criar CSS do sino**

Criar `frontend/app/components/NotificacoesSino.module.css`:

```css
.wrapper {
  position: relative;
}

.btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink-muted);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.btn:hover {
  border-color: var(--ink-subtle);
  color: var(--ink);
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ef4444;
  color: white;
  font-size: 9px;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  padding: 0 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  width: 320px;
  box-shadow: var(--shadow-lg);
  z-index: 500;
  overflow: hidden;
}

.dropdownHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
}

.dropdownTitle {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}

.marcarTodas {
  background: none;
  border: none;
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
  font-family: var(--font-body);
}

.lista {
  max-height: 400px;
  overflow-y: auto;
}

.item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--line);
  border-left: 3px solid transparent;
  transition: background 0.1s ease;
}

.item:last-child {
  border-bottom: none;
}

.item.novo_agendamento { border-left-color: #3b82f6; }
.item.agendamento_confirmado { border-left-color: #22c55e; }
.item.pendente_confirmacao { border-left-color: #f59e0b; }

.item.lida {
  opacity: 0.45;
}

.itemHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.itemTipo {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.itemTipo.novo_agendamento { color: #3b82f6; }
.itemTipo.agendamento_confirmado { color: #22c55e; }
.itemTipo.pendente_confirmacao { color: #f59e0b; }

.itemData {
  font-size: 10px;
  color: var(--ink-subtle);
}

.itemTitulo {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 2px;
}

.itemCorpo {
  font-size: 11px;
  color: var(--ink-subtle);
  margin-bottom: 0;
}

.itemAcoes {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.btnCompareceu {
  flex: 1;
  background: #22c55e;
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-body);
}

.btnFaltou {
  flex: 1;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-body);
}

.vazio {
  padding: 20px 16px;
  text-align: center;
  color: var(--ink-subtle);
  font-size: 12px;
}
```

- [ ] **Step 14.2: Criar componente do sino**

Criar `frontend/app/components/NotificacoesSino.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { type Notificacao } from "@/services/api";
import styles from "./NotificacoesSino.module.css";

const LABELS: Record<string, string> = {
  novo_agendamento: "📅 Novo agendamento",
  agendamento_confirmado: "✅ Confirmado",
  pendente_confirmacao: "⏳ Confirmar presença",
};

function formatarData(iso: string): string {
  const d = new Date(iso);
  const agora = new Date();
  const diffMs = agora.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin}min atrás`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h atrás`;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

type Props = {
  notificacoes: Notificacao[];
  naoLidas: number;
  onMarcarLida: (id: number) => void;
  onMarcarTodasLidas: () => void;
  onConfirmarPresenca: (agendamentoId: number, compareceu: boolean) => void;
};

export default function NotificacoesSino({
  notificacoes,
  naoLidas,
  onMarcarLida,
  onMarcarTodasLidas,
  onConfirmarPresenca,
}: Props) {
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickFora(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setAberto(false);
      }
    }
    document.addEventListener("mousedown", handleClickFora);
    return () => document.removeEventListener("mousedown", handleClickFora);
  }, []);

  return (
    <div className={styles.wrapper} ref={ref}>
      <button
        className={styles.btn}
        onClick={() => setAberto((v) => !v)}
        aria-label={`Notificações${naoLidas > 0 ? ` (${naoLidas} não lidas)` : ""}`}
      >
        <Bell size={16} />
        {naoLidas > 0 && (
          <span className={styles.badge}>{naoLidas > 99 ? "99+" : naoLidas}</span>
        )}
      </button>

      {aberto && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>
            <span className={styles.dropdownTitle}>Notificações</span>
            {naoLidas > 0 && (
              <button className={styles.marcarTodas} onClick={onMarcarTodasLidas}>
                Marcar todas como lidas
              </button>
            )}
          </div>

          <div className={styles.lista}>
            {notificacoes.length === 0 ? (
              <div className={styles.vazio}>Nenhuma notificação</div>
            ) : (
              notificacoes.map((n) => (
                <div
                  key={n.id}
                  className={`${styles.item} ${styles[n.tipo]} ${n.lida ? styles.lida : ""}`}
                  onClick={() => !n.lida && onMarcarLida(n.id)}
                >
                  <div className={styles.itemHeader}>
                    <span className={`${styles.itemTipo} ${styles[n.tipo]}`}>
                      {LABELS[n.tipo] ?? n.tipo}
                    </span>
                    <span className={styles.itemData}>{formatarData(n.criada_em)}</span>
                  </div>
                  <div className={styles.itemTitulo}>{n.titulo}</div>
                  {n.corpo && <div className={styles.itemCorpo}>{n.corpo}</div>}
                  {n.tipo === "pendente_confirmacao" && !n.lida && n.agendamento_id && (
                    <div className={styles.itemAcoes} onClick={(e) => e.stopPropagation()}>
                      <button
                        className={styles.btnCompareceu}
                        onClick={() => onConfirmarPresenca(n.agendamento_id!, true)}
                      >
                        ✓ Compareceu
                      </button>
                      <button
                        className={styles.btnFaltou}
                        onClick={() => onConfirmarPresenca(n.agendamento_id!, false)}
                      >
                        ✕ Faltou
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 14.3: Verificar compilação TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 14.4: Commit**

```bash
git add frontend/app/components/NotificacoesSino.tsx frontend/app/components/NotificacoesSino.module.css
git commit -m "feat: add NotificacoesSino dropdown component"
```

---

## Task 15: Frontend — `NotificacoesProvider` + integração no `AppShell` e `Header`

**Files:**
- Create: `frontend/app/components/NotificacoesProvider.tsx`
- Modify: `frontend/app/components/AppShell.tsx`
- Modify: `frontend/app/components/Header.tsx`

- [ ] **Step 15.1: Criar `NotificacoesProvider`**

Criar `frontend/app/components/NotificacoesProvider.tsx`:

```tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { type Notificacao } from "@/services/api";
import { useNotificacoes, type UseNotificacoesReturn } from "@/hooks/useNotificacoes";
import { ToastContainer } from "./ToastNotificacao";

const NotificacoesContext = createContext<UseNotificacoesReturn | null>(null);

export function useNotificacoesContext(): UseNotificacoesReturn {
  const ctx = useContext(NotificacoesContext);
  if (!ctx) throw new Error("useNotificacoesContext deve ser usado dentro de NotificacoesProvider");
  return ctx;
}

export function NotificacoesProvider({ children }: { children: React.ReactNode }) {
  const notif = useNotificacoes();
  const [toastsVisiveis, setToastsVisiveis] = useState<Notificacao[]>([]);

  // Quando chegam novas notificações, adiciona ao stack de toasts
  useEffect(() => {
    if (notif.novasIds.length === 0) return;
    const novas = notif.notificacoes.filter((n) => notif.novasIds.includes(n.id));
    setToastsVisiveis((prev) => [...novas, ...prev].slice(0, 3));
    notif.confirmarNovaVista();
  }, [notif.novasIds]); // eslint-disable-line react-hooks/exhaustive-deps

  const fecharToast = useCallback((id: number) => {
    setToastsVisiveis((prev) => prev.filter((n) => n.id !== id));
    notif.marcarLida(id);
  }, [notif.marcarLida]);

  const confirmarPresencaToast = useCallback(
    async (agendamentoId: number, compareceu: boolean) => {
      await notif.confirmarPresencaAgendamento(agendamentoId, compareceu);
      setToastsVisiveis((prev) =>
        prev.filter((n) => n.agendamento_id !== agendamentoId)
      );
    },
    [notif.confirmarPresencaAgendamento]
  );

  return (
    <NotificacoesContext.Provider value={notif}>
      {children}
      <ToastContainer
        toasts={toastsVisiveis}
        onClose={fecharToast}
        onCompareceu={confirmarPresencaToast}
      />
    </NotificacoesContext.Provider>
  );
}
```

- [ ] **Step 15.2: Envolver `AppShell` com o provider**

Em `frontend/app/components/AppShell.tsx`, substituir o conteúdo completo por:

```tsx
"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Header from "./Header";
import ThemeToggle from "./ThemeToggle";
import { useTenantTheme } from "@/hooks/useTenantTheme";
import { NotificacoesProvider } from "./NotificacoesProvider";

type AppShellProps = {
  children: ReactNode;
};

const TOKEN_ACTION_PREFIXES = ["/confirmar/", "/cancelar/", "/reagendar/"];

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  useTenantTheme();
  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isTokenActionPage = TOKEN_ACTION_PREFIXES.some((p) => pathname.startsWith(p));
  const isPublicBookingPath =
    !isPublicBookingById &&
    !isTokenActionPage &&
    /^\/[^/]+$/.test(pathname) &&
    !["/login", "/admin", "/agenda", "/gestao"].includes(pathname);

  const hideHeader = inLogin || isPublicBookingPath || isPublicBookingById || isTokenActionPage;
  const isAuthenticated = !hideHeader;

  const content = (
    <>
      {!hideHeader && <Header />}
      {(isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />}
      {children}
    </>
  );

  // Só inicializa o provider (polling) em páginas autenticadas
  if (isAuthenticated) {
    return <NotificacoesProvider>{content}</NotificacoesProvider>;
  }

  return <>{content}</>;
}
```

- [ ] **Step 15.3: Adicionar `NotificacoesSino` ao `Header`**

Em `frontend/app/components/Header.tsx`, adicionar o import:

```typescript
import { useNotificacoesContext } from "./NotificacoesProvider";
import NotificacoesSino from "./NotificacoesSino";
```

Dentro da função `Header`, adicionar após `const session = useAuthSession()`:

```typescript
  const {
    notificacoes,
    naoLidas,
    marcarLida,
    marcarTodasLidas,
    confirmarPresencaAgendamento,
  } = useNotificacoesContext();
```

No JSX, dentro de `<div className={styles.actions}>`, adicionar `<NotificacoesSino />` entre `<ThemeToggle />` e o botão de logout:

```tsx
        <div className={styles.actions}>
          {!inAdminPage ? (
            <nav className={styles.nav} aria-label="Navegacao principal">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cx(styles.navLink, isActive && styles.navLinkActive)}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          ) : null}

          <ThemeToggle />

          {!isAdmin && !inAdminPage && (
            <NotificacoesSino
              notificacoes={notificacoes}
              naoLidas={naoLidas}
              onMarcarLida={marcarLida}
              onMarcarTodasLidas={marcarTodasLidas}
              onConfirmarPresenca={confirmarPresencaAgendamento}
            />
          )}

          <button type="button" className={styles.logoutButton} onClick={handleLogout}>
            <LogOut size={16} />
            <span>Sair</span>
          </button>
        </div>
```

- [ ] **Step 15.4: Verificar compilação TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem erros.

- [ ] **Step 15.5: Rodar o servidor de desenvolvimento e verificar visualmente**

```bash
cd frontend && npm run dev
```

Abrir `http://localhost:3000`, fazer login e verificar:
1. Sino aparece na direita do header, junto ao botão de logout
2. Clicar no sino abre o dropdown
3. Criar um agendamento via gestão → toast de "Novo agendamento" aparece em 15s
4. Agendamentos com horário passado → toast "Confirmar presença" aparece após o job rodar

- [ ] **Step 15.6: Commit**

```bash
git add frontend/app/components/NotificacoesProvider.tsx frontend/app/components/AppShell.tsx frontend/app/components/Header.tsx
git commit -m "feat: wire NotificacoesProvider, sino and toasts into app shell"
```

---

## Verificação Final

- [ ] **Rodar suite de testes backend completa**

```bash
cd backend && python -m pytest tests/ -q 2>&1 | tail -10
```

Esperado: todos os testes passam.

- [ ] **Verificar build de produção do frontend**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Esperado: build sem erros.
