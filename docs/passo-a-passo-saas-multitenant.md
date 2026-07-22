# Passo a Passo SaaS Multi-tenant (Estabelecimentos + WhatsApp)

Este documento mostra o fluxo completo:

1. Cadastro de um novo estabelecimento.
2. Vinculo da instancia/numero de WhatsApp ao tenant correto.
3. Login e uso da API com isolamento de tenant.
4. Como validar que uma mensagem entrou no estabelecimento correto.
5. Como funciona o fluxo publico por link de agendamento.

## 1) Variaveis de ambiente (staging e prod)

Em **cada ambiente** (`staging` e `prod`), configure no backend:

```env
DATABASE_URL=postgresql://SEU_USUARIO:SEU_TOKEN@SEU_HOST_NEON/neondb?sslmode=require
WHATSAPP_TOKEN=...
PHONE_NUMBER_ID=...

JWT_SECRET=<segredo-forte-unico-por-ambiente>
JWT_EXPIRES_MINUTES=480
ADMIN_USUARIO=<usuario-admin>
ADMIN_SENHA=<senha-admin-forte>

# Seguranca do webhook externo (MegaAPI/n8n -> backend)
MEGAAPI_WEBHOOK_TOKEN=<token-compartilhado-no-header>
MEGAAPI_WEBHOOK_SECRET=<opcional-hmac-sha256>
MEGAAPI_WEBHOOK_ALLOW_UNSIGNED=false
MEGAAPI_WEBHOOK_MAX_SKEW_SECONDS=300
```

Se voce usar `npx neonctl@latest init` na raiz do repositorio, o backend agora tambem le esse `.env` automaticamente.

Depois de atualizar, reinicie o backend.

## 2) Login de admin (para cadastrar estabelecimentos)

Endpoint:

- `POST /auth/login`

Exemplo:

```bash
curl -X POST http://SEU_BACKEND/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "usuario":"SEU_ADMIN_USUARIO",
    "senha":"SEU_ADMIN_SENHA"
  }'
```

Resposta esperada:

- `is_admin: true`
- `access_token` (JWT)

Guarde o token admin para as chamadas de `/estabelecimentos`.

## 3) Cadastrar estabelecimento com dados de roteamento WhatsApp

Endpoint:

- `POST /estabelecimentos/` (somente admin)

Campos criticos para roteamento:

- `mega_instance_key` (chave da instancia WhatsApp)
- `whatsapp_number` (numero vinculado)

Exemplo:

```bash
curl -X POST http://SEU_BACKEND/estabelecimentos/ \
  -H "Authorization: Bearer SEU_TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "nome":"Estabelecimento Centro",
    "login":"estabelecimento.centro",
    "senha":"senha-forte",
    "plano":"basico",
    "status_manual":"ativo",
    "vencimento_em":"2026-12-31",
    "trial_ativo":false,
    "trial_fim_em":null,
    "ultimo_acesso_em":null,
    "pagamento_recusado":false,
    "endereco":"Rua A, 100"
  }'
```

> **Nota (desatualizado, nao relacionado ao rebrand):** `mega_instance_key`/`mega_token`/
> `whatsapp_number` nao sao mais aceitos neste `POST` (o schema atual usa
> `extra="forbid"` e rejeitaria a requisicao com `422` se voce reincluir esses
> campos aqui). Hoje `whatsapp_number` e definido depois, via
> `PATCH /configuracoes/perfil`; `mega_instance_key`/`mega_token` nao tem
> endpoint REST no momento e precisam ser setados direto no banco
> (`estabelecimentos.mega_instance_key`/`mega_token`). Esta secao precisa de
> uma revisao funcional a parte — fora do escopo deste rebrand de nomenclatura.

Observacoes:

- `mega_instance_key` e `whatsapp_number` devem ser unicos por estabelecimento.
- Se houver duplicidade, a API retorna `400`.

## 4) Login do estabelecimento (tenant)

Endpoint:

- `POST /auth/login`

Exemplo:

```bash
curl -X POST http://SEU_BACKEND/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "usuario":"estabelecimento.centro",
    "senha":"senha-forte"
  }'
```

Resposta esperada:

- `is_admin: false`
- `tenant_id: <id do estabelecimento>`
- `access_token: <jwt>`

## 5) Chamar endpoints de negocio com isolamento

Para endpoints de negocio (`/clientes`, `/servicos`, `/agendamentos`, `/agenda`, `/chatbot`), envie:

- `Authorization: Bearer <token do estabelecimento>`
- `X-Estabelecimento-Id: <tenant_id do estabelecimento>`

Exemplo:

```bash
curl http://SEU_BACKEND/clientes/ \
  -H "Authorization: Bearer TOKEN_DO_ESTABELECIMENTO" \
  -H "X-Estabelecimento-Id: 12"
```

Regras:

- Se faltar token: `401`.
- Se o `X-Estabelecimento-Id` nao bater com o tenant do token: `403`.
- Se tenant nao existir: `404`.

Observacao importante:

- O n8n/MegaAPI nao deve chamar `/chatbot/mensagem` diretamente.
- Para entrada externa de mensagens, use `POST /webhooks/megaapi`.

## 6) Como o webhook decide o tenant

No recebimento em `POST /webhooks/megaapi`, o backend:

1. Valida autenticacao do webhook (`X-Webhook-Token` ou assinatura HMAC).
2. Recebe o `instance_key`.
3. Resolve tenant no banco.
4. Para saudacoes/mensagens simples, responde com link publico (`https://hagendei.com/{slug}`).
5. Para demais mensagens, pode usar fallback para chatbot interno.

Resolucao de tenant:

1. `instance_key` do payload (preferencial e recomendado).
2. `whatsapp_number` da metadata (fallback controlado).
3. Se nao achar tenant: webhook retorna `{"status":"ignored"}`.

Nao existe mais fallback para tenant fixo em `.env`.

## 10) Fluxo publico de agendamento (modelo moderno)

1. Cliente envia "oi" no WhatsApp.
2. `POST /webhook` responde com link publico do estabelecimento (`/agendar/{estabelecimento_id}`) na primeira interacao ativa.
3. Frontend consulta endpoints publicos para listar barbeiros, servicos e horarios:
   - `GET /public/barbeiros?estabelecimento_id=...`
   - `GET /public/servicos?estabelecimento_id=...`
   - `GET /public/horarios-disponiveis?...`
4. Frontend confirma em `POST /public/agendamentos`.
5. Backend grava no tenant correto, envia confirmacao por WhatsApp e agenda lembretes de 24h e 2h.

Observacao operacional:

- Lembretes sao colocados em fila (`reminder_jobs`).
- Para processar envios pendentes, chame periodicamente:
  - `POST /internal/reminders/process`
  - Header opcional: `X-Internal-Token` (quando `INTERNAL_REMINDER_TOKEN` estiver configurado).

## 7) Como validar se o numero esta correto (checklist pratico)

## 7.1 Validar cadastro no banco

```sql
SELECT id, nome, mega_instance_key, whatsapp_number
FROM estabelecimentos
ORDER BY id DESC;
```

Confirme:

- `mega_instance_key` do estabelecimento esta igual ao da plataforma WhatsApp.
- `whatsapp_number` esta no formato esperado (recomendado E.164 so digitos, ex: `5582999991111`).

## 7.2 Enviar webhook de teste com a instance certa

```bash
curl -X POST http://SEU_BACKEND/webhooks/megaapi \
  -H "X-Webhook-Token: SEU_MEGAAPI_WEBHOOK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_key":"instancia-centro-01",
    "data":{
      "from":"5582988887777",
      "text":"oi"
    }
  }'
```

Esperado:

- Resposta `{"status":"ok"}`.
- Cliente/agendamento (quando houver fluxo) vinculados ao `estabelecimento_id` do estabelecimento certo.

## 7.3 Conferir no banco se caiu no tenant correto

```sql
SELECT id, telefone, nome, estabelecimento_id
FROM clientes
WHERE telefone = '5582988887777'
ORDER BY id DESC;
```

O `estabelecimento_id` deve ser exatamente o tenant do estabelecimento dono da `instance_key`.

## 7.4 Teste negativo (instance errada)

Envie webhook com `instance_key` inexistente.

Esperado:

- `{"status":"ignored"}`
- Nenhum dado novo criado em `clientes`/`agendamentos`.

## 8) Troubleshooting rapido

- `401 Autenticacao obrigatoria`: faltou `Authorization: Bearer`.
- `403 Tenant do token difere do tenant da requisicao`: header `X-Estabelecimento-Id` nao bate com token.
- `401 Assinatura do webhook invalida`: faltou `X-Webhook-Token` valido (ou assinatura HMAC valida).
- `status ignored` no webhook: `instance_key`/`whatsapp_number` nao mapeados para nenhum estabelecimento.

## 9) Checklist de deploy (staging e prod)

1. Atualizar `.env` com `JWT_SECRET`, `ADMIN_USUARIO`, `ADMIN_SENHA`.
2. Reiniciar backend.
3. Fazer login novamente no frontend (tokens antigos podem nao valer).
4. Validar cadastro do estabelecimento com `mega_instance_key` e `whatsapp_number`.
5. Rodar webhook de teste e conferir `estabelecimento_id` no banco.
