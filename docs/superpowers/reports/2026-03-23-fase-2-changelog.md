# Changelog — Fase 2: Generalização

**Data:** 2026-03-24
**Branch:** claude/priceless-faraday
**Status:** Concluído

## Resumo Executivo

A Fase 2 generalizou o sistema para suportar qualquer tipo de estabelecimento de serviços (barbearias, salões de beleza, estéticas automotivas, etc.), sem quebrar o código existente. O objetivo central foi substituir a nomenclatura específica de barbearia (`barbearias`, `barbeiros`) por termos neutros (`estabelecimentos`, `profissionais`) tanto no banco de dados quanto nas camadas de model, schema, rota e frontend.

A estratégia adotada priorizou compatibilidade retroativa: as tabelas e colunas físicas foram renomeadas via migrações idempotentes executadas no startup (`_ensure_*`), enquanto os arquivos `barbearia.py` e `barbeiro.py` foram convertidos em shims que re-exportam os novos modelos. Os modelos SQLAlchemy expõem synonyms (`barbearia_id`, `barbeiro_id`, `tenant_id`) e relacionamentos duplos (`profissional`/`barbeiro`, `estabelecimento`/`barbearia`) para que código legado continue funcionando sem alterações. Um campo `tipo_servico` foi adicionado ao estabelecimento para controlar o vocabulário exibido ao usuário final.

## Tabelas/Colunas renomeadas no BD

| De | Para |
|---|---|
| `barbearias` | `estabelecimentos` |
| `barbeiros` | `profissionais` |
| `barbearia_id` (agendamentos, clientes, servicos) | `estabelecimento_id` |
| `barbeiro_id` (agendamentos) | `profissional_id` |
| `barbershop_id` (profissionais) | `estabelecimento_id` |
| `tenant_id` (conversas, reminder_jobs) | `estabelecimento_id` |

## Coluna nova

- `estabelecimentos.tipo_servico VARCHAR(50) DEFAULT 'barbearia'`

## Arquivos criados

| Arquivo | Descrição |
|---|---|
| `backend/app/models/estabelecimento.py` | Model `Estabelecimento` com `__tablename__ = "estabelecimentos"` e campo `tipo_servico` |
| `backend/app/models/profissional.py` | Model `Profissional` com `__tablename__ = "profissionais"`, FK para `estabelecimentos.id` e synonyms de compatibilidade |
| `backend/app/routes/estabelecimentos.py` | Router CRUD `/estabelecimentos/` (substitui `/barbearias/`) |
| `backend/app/routes/profissionais.py` | Router CRUD `/profissionais/` (substitui `/barbeiros/`) |
| `backend/app/routes/estabelecimento_funcionamento.py` | Router GET/PUT `/estabelecimentos/me/funcionamento` (substitui `/barbearias/me/funcionamento`) |
| `backend/app/services/estabelecimento_hours_service.py` | Serviço de normalização/herança de horários de funcionamento por estabelecimento |
| `frontend/lib/vocab.ts` | Mapeamento `tipo_servico` → labels (Barbeiro/Atendente/Detailer, etc.) |
| `frontend/services/estabelecimentos-admin.ts` | Substitui `barbershops-admin.ts`; exporta aliases backward-compat (`BarbeariaAdmin`, etc.) |

## Arquivos modificados

| Arquivo | Alteração |
|---|---|
| `backend/app/database.py` | Adicionados `_ensure_rename_para_estabelecimentos()` e `_ensure_tipo_servico_column()`, ambos chamados em `init_db()` |
| `backend/app/main.py` | Inclui routers `/estabelecimentos`, `/profissionais` e `/estabelecimentos/me/funcionamento`; removidos routers legados na limpeza final |
| `backend/app/models/__init__.py` | Expõe `Estabelecimento` e `Profissional`; aliases `Barbearia`/`Barbeiro` removidos na limpeza final |
| `backend/app/models/barbearia.py` | Convertido em shim: `Barbearia = Estabelecimento` |
| `backend/app/models/barbeiro.py` | Convertido em shim: `Barbeiro = Profissional` |
| `backend/app/models/agendamento.py` | Colunas físicas renomeadas para `estabelecimento_id`/`profissional_id`; synonyms `barbearia_id`, `barbeiro_id`, `tenant_id` e relacionamentos duplos adicionados |
| `backend/app/models/cliente.py` | Coluna renomeada para `estabelecimento_id` com synonym `barbearia_id` |
| `backend/app/models/servico.py` | Coluna renomeada para `estabelecimento_id` com synonym `barbearia_id` |
| `backend/app/routes/auth.py` | Adicionado endpoint `GET /auth/me` retornando `MeResponse` com `tipo_servico` |
| `backend/app/routes/deps.py` | Adicionada dependência `get_current_estabelecimento`; alias `get_current_barbearia` mantido |
| `backend/app/schemas/auth.py` | Adicionado schema `MeResponse` com campos `id`, `nome`, `plano`, `is_admin`, `tipo_servico` |
| `backend/app/schemas/barbearia.py` | Adicionados aliases de schema: `EstabelecimentoAdminCreate/Update/Response/Funcionamento` |
| `backend/tests/conftest.py` | Atualizado para usar `Estabelecimento`/`Profissional`; routers legados mantidos no test app |
| `backend/tests/test_auth_barbearias.py` | Adicionados testes para `GET /auth/me` |
| `frontend/services/auth.ts` | Adicionados tipo `MeResponse` e função `fetchMe()` |
| `frontend/services/api.ts` | Funções `listBarbeiros`/`createBarbeiro`/`updateBarbeiro`/`deleteBarbeiro` apontam para `/profissionais/`; `getBarbershopWorkingHours`/`updateBarbershopWorkingHours` apontam para `/estabelecimentos/me/funcionamento` |

## Endpoints novos

- `GET /auth/me` — retorna dados do estabelecimento logado + `tipo_servico` (ou admin sem tenant)
- `GET /estabelecimentos/` — lista estabelecimentos (admin); substitui `GET /barbearias/`
- `POST /estabelecimentos/` — cria estabelecimento (admin); substitui `POST /barbearias/`
- `PUT /estabelecimentos/{id}` — atualiza estabelecimento (admin); substitui `PUT /barbearias/{id}`
- `DELETE /estabelecimentos/{id}` — remove estabelecimento (admin); substitui `DELETE /barbearias/{id}`
- `GET /profissionais/` — lista profissionais do tenant; substitui `GET /barbeiros/`
- `POST /profissionais/` — cria profissional; substitui `POST /barbeiros/`
- `PUT /profissionais/{id}` — atualiza profissional; substitui `PUT /barbeiros/{id}`
- `DELETE /profissionais/{id}` — remove profissional; substitui `DELETE /barbeiros/{id}`
- `GET /estabelecimentos/me/funcionamento` — retorna horários do estabelecimento; substitui `GET /barbearias/me/funcionamento`
- `PUT /estabelecimentos/me/funcionamento` — atualiza horários; substitui `PUT /barbearias/me/funcionamento`

## Endpoints removidos (em produção)

- `GET/POST/PUT/DELETE /barbearias/`
- `GET/POST/PUT/DELETE /barbeiros/`
- `GET/PUT /barbearias/me/funcionamento`

> Nota: os routers legados foram mantidos registrados no app de testes (`conftest.py`) para que a suíte existente continue cobrindo as rotas antigas até eventual remoção completa.

## Frontend

- `frontend/lib/vocab.ts` — mapeamento `tipo_servico` → labels; tipos suportados: `barbearia` (Barbeiro), `salao_beleza` (Atendente), `estetica_automotiva` (Detailer); fallback para `barbearia`
- `frontend/services/estabelecimentos-admin.ts` — substitui `barbershops-admin.ts`; exporta aliases `BarbeariaAdmin`, `PlanoBarbearia`, `StatusManualBarbearia`, `StatusAssinaturaBarbearia` para compatibilidade
- `frontend/services/auth.ts` — adicionado tipo `MeResponse` e função `fetchMe(accessToken)` que chama `GET /auth/me`
- `frontend/services/api.ts` — funções de barbeiros (`listBarbeiros`, `createBarbeiro`, etc.) atualizadas para usar `/profissionais/`; funções de horários atualizadas para `/estabelecimentos/me/funcionamento`

## Variáveis de ambiente novas

Nenhuma.

## Roteiro de Deploy

1. `git pull` no VPS
2. Reiniciar serviço backend — `init_db()` executa `_ensure_rename_para_estabelecimentos()` e `_ensure_tipo_servico_column()` automaticamente
3. Verificar logs de startup (os `_ensure_*` usam `_run_best_effort`, que suprime erros silenciosamente caso a renomeação já tenha ocorrido)
4. Deploy do frontend atualizado
5. Verificar que os novos endpoints respondem corretamente: `GET /estabelecimentos/`, `GET /profissionais/`, `GET /auth/me`

## Notas Técnicas

### Abordagem de compatibilidade retroativa (shims)

Os arquivos `backend/app/models/barbearia.py` e `backend/app/models/barbeiro.py` foram mantidos como shims simples que re-exportam `Estabelecimento as Barbearia` e `Profissional as Barbeiro`, respectivamente. Qualquer import legado do tipo `from app.models.barbearia import Barbearia` continua funcionando sem alterações.

### Synonyms SQLAlchemy

Os models `Agendamento`, `Profissional`, `Cliente` e `Servico` expõem synonyms SQLAlchemy (`barbearia_id`, `barbeiro_id`, `tenant_id`) mapeados para as colunas físicas renomeadas. Isso garante que queries legadas que filtram por esses nomes continuem funcionando sem modificação.

### Relacionamentos duplos em Agendamento

`Agendamento` declara dois pares de relacionamentos apontando para a mesma FK, com o parâmetro `overlaps` para silenciar o aviso do SQLAlchemy: `profissional`/`barbeiro` (ambos via `profissional_id`) e `estabelecimento`/`barbearia` (ambos via `estabelecimento_id`). Código legado que acessa `.barbeiro` ou `.barbearia` continua funcional.

### Aliases de schema (Pydantic)

`backend/app/schemas/barbearia.py` define aliases `EstabelecimentoAdminCreate/Update/Response/Funcionamento` apontando para os schemas existentes. O router `/estabelecimentos/` reutiliza os schemas `BarbeariaAdmin*` diretamente, evitando duplicação.

### Aliases de dep (FastAPI)

`get_current_barbearia` em `deps.py` é mantido como alias para `get_current_estabelecimento`, garantindo que endpoints existentes que usam essa dependência não precisem ser alterados.

### Frontend backward-compat

`estabelecimentos-admin.ts` reexporta todos os tipos antigos (`BarbeariaAdmin`, `PlanoBarbearia`, etc.) como aliases dos novos tipos, preservando compatibilidade com componentes do painel que ainda não foram migrados.
