# Rebrand Barbershop → Hagendei — Design Spec

**Data:** 2026-07-20
**Status:** Aprovado

---

## Visão Geral

O sistema deixou de ser específico para barbearias e passou a ser uma plataforma
multi-tenant genérica de agendamento (negócios e profissionais em geral). Um novo
domínio, `hagendei.com`, foi comprado para refletir essa mudança. Parte do rebrand
de marca já começou informalmente (README já usa "Hagendei", chaves de
`localStorage` no frontend já usam o prefixo `hagendei`), e o backend já tem uma
migração de domínio interna em andamento (`barbearia` → `estabelecimento`, com um
shim de compatibilidade marcado no próprio código para remoção em uma "Tarefa 17").

Este trabalho termina essas duas frentes e adiciona o que falta: nome de marca
visível na UI, nome do repositório GitHub, e um checklist de configuração manual
de DNS/ambiente de produção.

---

## Escopo

### Fase 1 — Nomenclatura interna (código)

Finalizar a migração já sinalizada no código de `barbearia`/`barbershop` (inglês,
usado em identificadores) para `estabelecimento`:

- Remover o shim `backend/app/models/barbearia.py` (hoje reexporta
  `Estabelecimento as Barbearia`) e atualizar todos os imports que dependem dele
  (ex.: `notificacao_service.py`, `public_booking_service.py`).
- Confirmar, usando o grafo de dependências, que `backend/app/routes/barbearias.py`
  e `backend/app/routes/barbearia_funcionamento.py` não estão registrados em
  `main.py` (já confirmado: não estão) e removê-los, a menos que algum teste
  dependa exclusivamente deles — nesse caso, migrar o teste primeiro.
- Unificar `backend/app/services/barbershop_hours_service.py` com
  `backend/app/services/estabelecimento_hours_service.py` (parecem cobrir a mesma
  responsabilidade duplicada — confirmar diffs antes de decidir qual fica).
- Frontend: renomear identificadores que ainda usam "Barbershop" em inglês —
  `BarbershopWorkingHours`, `lookupPublicBarbershopById`,
  `defaultBarbershopWorkingHours`, `getBarbershopWorkingHours`,
  `updateBarbershopWorkingHours`, `lookupPublicBarbershop` (em `services/api.ts`),
  arquivo `frontend/services/barbershops-admin.ts`, e a rota dinâmica
  `frontend/app/agendar/[barbeariaId]` → equivalente com `estabelecimento`.
- Atualizar testes afetados: `backend/tests/test_barbearia_funcionamento.py`,
  `backend/tests/test_auth_barbearias.py` (renomear para `test_estabelecimento_*`
  se testarem código que sobrevive à limpeza).
- Todo arquivo candidato à remoção é confirmado como não referenciado (via grafo de
  impacto/busca) antes de ser apagado, para não quebrar nada em produção.

### Fase 2 — Marca visível + checklist de deploy

- `frontend/app/layout.tsx`: `metadata.title` → `"Hagendei | Painel de Gestão"`,
  com `metadata.description` e OG tags condizentes com a marca.
- `frontend/.env.example`: `NEXT_PUBLIC_API_URL=https://api.seudominio.com` →
  `https://api.hagendei.com`.
- Varredura final por qualquer string visível ao usuário (mensagens de WhatsApp,
  e-mail, UI) que ainda mencione "Barbershop"/"Barbearia" como nome de produto
  (não como termo genérico de negócio, ex. "sua barbearia" em copy genérica pode
  ficar se fizer sentido para o público, a decidir caso a caso no plano).
- Novo documento de checklist de deploy (`docs/deploy-hagendei-checklist.md`)
  cobrindo os passos manuais, fora do meu acesso:
  - Registros DNS tipo `A` na Hostinger (ou onde o domínio estiver gerenciado)
    para `hagendei.com` e `api.hagendei.com`, apontando para o IP do servidor de
    produção atual.
  - Atualização de `APP_DOMAIN` e `API_DOMAIN` no `.env` de produção (fora do
    git) e reinício do container Caddy — o certificado TLS é emitido
    automaticamente via Let's Encrypt assim que o DNS resolver.

### Fase 3 — Repositório GitHub

- Renomear `ViniciusLima115/barbershop-chatbot` → `ViniciusLima115/hagendei` via
  `gh repo rename hagendei`.
- Atualizar o remote `origin` local para a nova URL.
- Ação confirmada explicitamente com o usuário antes de executar, por afetar um
  recurso compartilhado (URL pública do repositório).

---

## Fora do escopo

- DNS e infraestrutura de produção reais (documentados no checklist, não
  executados por mim).
- Nome do projeto/banco no Neon.
- Segredos e valores reais em arquivos `.env` de produção (só `.env.example` é
  tocado).
- Criação de logo ou favicon (não existe hoje nenhum asset visual de marca no
  projeto; fora do escopo deste rebrand textual).

---

## Estratégia de execução

Cada fase é implementada e commitada separadamente, na ordem 1 → 2 → 3, para
facilitar revisão e permitir parar entre fases se necessário. A Fase 1 é a maior
e mais arriscada (toca código de produção), por isso vem primeiro e isolada; a
Fase 3 é a única ação irreversível-ish (renomeia recurso externo compartilhado) e
fica por último, com confirmação explícita antes de executar.

---

## Critérios de sucesso

- Nenhuma referência a `barbearia`/`Barbershop` (como identificador de código)
  sobrevive fora de testes/migrations históricas do Alembic (que não devem ser
  reescritas).
- Suite de testes do backend e frontend passam após a Fase 1.
- Título da página e metadata refletem "Hagendei".
- Checklist de deploy existe e contém os valores corretos de DNS/env.
- Repositório GitHub renomeado e remote local atualizado, com `git remote -v`
  confirmando.
