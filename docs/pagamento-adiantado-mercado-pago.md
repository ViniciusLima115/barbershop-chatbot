# Pagamentos por estabelecimento com Mercado Pago

## Objetivo
Permitir pagamento adiantado por estabelecimento sem expor credenciais ao cliente do estabelecimento.

## Regra atual
- O admin do sistema configura a conta Mercado Pago de cada estabelecimento.
- O estabelecimento configura apenas a regra comercial do servico: sem pagamento, valor total ou sinal.
- O frontend nunca envia nem escolhe `payment_account_id`, `access_token`, `client_secret` ou conta do gateway.
- O backend resolve a conta por `establishment_id` do agendamento.

## Arquitetura aplicada
- `payment_accounts`: conta Mercado Pago por estabelecimento, com credenciais criptografadas.
- `servicos`: regra de pagamento adiantado/sinal.
- `agendamentos`: snapshot da regra de pagamento no momento da criacao.
- `pagamentos`: registro transacional do checkout e status.
- `payment_webhook_events`: auditoria e idempotencia dos webhooks.
- `app/services/payments/providers/`: camada de provider, hoje com Mercado Pago.

## Campos principais
`payment_accounts`:
- `establishment_id`
- `provider`
- `account_name`
- `client_id_encrypted`
- `client_secret_encrypted`
- `access_token_encrypted`
- `public_key_encrypted`
- `status`
- `internal_notes`
- `created_by_admin_id`
- `updated_by_admin_id`
- `checkout_hold_minutes`

As credenciais nunca sao retornadas completas. O admin recebe apenas valores mascarados.

## Endpoints administrativos
- `GET /admin/establishments`
- `GET /admin/establishments/{id}/payment-account`
- `POST /admin/establishments/{id}/payment-account`
- `PATCH /admin/establishments/{id}/payment-account`
- `PATCH /admin/establishments/{id}/payment-account/status`
- `DELETE /admin/establishments/{id}/payment-account`

Todos exigem token admin (`require_admin`).

## Endpoints do estabelecimento
- O estabelecimento continua usando `servicos` para configurar `pagamento_adiantado_obrigatorio`, `advance_payment_type` e `advance_payment_amount`.
- Rotas de conectar/desconectar Mercado Pago pelo estabelecimento retornam `403`.
- `GET /integrations/mercadopago/status` retorna apenas status operacional nao sensivel para orientar a tela de servicos.

## Fluxo de checkout
1. Cliente final escolhe estabelecimento, profissional, servico e horario.
2. Backend valida tenant, profissional e servico.
3. Se o servico nao exige pagamento: booking segue fluxo normal.
4. Se exige pagamento: backend busca `payment_accounts` ativa do estabelecimento.
5. Se nao houver conta ativa: checkout online e bloqueado com mensagem clara.
6. Backend cria `pagamentos` e preference/checkout no Mercado Pago usando o `access_token` criptografado daquela conta.
7. Webhook confirma via consulta server-to-server.
8. Booking so vira `confirmado` quando o pagamento e `approved`.

## Variaveis de ambiente
- `DATABASE_URL`
- `APP_ENV`
- `JWT_SECRET`
- `ENCRYPTION_KEY`
- `FRONTEND_URL`
- `BACKEND_PUBLIC_BASE_URL`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `MERCADOPAGO_WEBHOOK_TOKEN`
- `MERCADOPAGO_TIMEOUT_SECONDS`
- `MERCADOPAGO_API_BASE`

As credenciais Mercado Pago de cada estabelecimento sao cadastradas no painel admin, nao no `.env`.

## Subida local
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

## Banco e migracoes
O projeto aplica schema no startup via `init_db()` e guardas em `app/database.py`.

Para aplicar manualmente:
```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.database import init_db; init_db()"
```

## Como configurar a conta pelo admin
1. Entrar como administrador.
2. Abrir o painel admin.
3. Na lista de estabelecimentos, clicar em `Pagamento`.
4. Informar nome amigavel, `client_id`, `client_secret`, `access_token`, `public_key` se aplicavel, status e tempo de reserva.
5. Salvar. Os campos sensiveis passam a aparecer apenas mascarados.

## Como o estabelecimento configura cobranca
1. Entrar no painel do estabelecimento.
2. Abrir `Gestao > Servicos`.
3. Ativar `Exigir pagamento adiantado`.
4. Escolher `Valor total` ou `Sinal`.
5. Informar o valor do sinal quando aplicavel.

## Expiracao de reservas pendentes
Automatica pelo scheduler interno.

Manual:
```powershell
curl -X POST "http://127.0.0.1:8000/internal/payments/expire-pending?limite=300" ^
  -H "X-Internal-Token: SEU_TOKEN_INTERNO"
```

## Teste de webhook local
```powershell
curl -X POST "http://127.0.0.1:8000/webhooks/mercadopago?payment_id=123&token=SEU_MERCADOPAGO_WEBHOOK_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"id\":\"evt-local-1\",\"type\":\"payment\",\"data\":{\"id\":\"mp-payment-1\"}}"
```

## Testes automatizados
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_payments_module.py -p no:cacheprovider
```

Coberturas principais:
- admin cadastra e edita conta Mercado Pago.
- tenant nao acessa endpoints administrativos.
- credenciais ficam criptografadas.
- booking com pagamento usa a conta configurada pelo admin.
- booking sem pagamento segue normal.
- checkout e bloqueado quando nao ha conta ativa.
- webhook aprova pagamento e confirma booking.
- idempotencia e isolamento multi-tenant.
