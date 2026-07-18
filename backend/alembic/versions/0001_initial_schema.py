"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estabelecimentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("endereco", sa.String(255), nullable=True, server_default=""),
        sa.Column("mega_instance_key", sa.String(255), nullable=True),
        sa.Column("mega_token", sa.Text(), nullable=True),
        sa.Column("whatsapp_number", sa.String(30), nullable=True),
        sa.Column("login", sa.String(255), nullable=True),
        sa.Column("senha", sa.String(255), nullable=True),
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plano", sa.String(50), nullable=True, server_default="basico"),
        sa.Column("status_manual", sa.String(50), nullable=True, server_default="ativo"),
        sa.Column("vencimento_em", sa.Date(), nullable=True),
        sa.Column("trial_ativo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("trial_fim_em", sa.Date(), nullable=True),
        sa.Column("ultimo_acesso_em", sa.DateTime(), nullable=True),
        sa.Column("pagamento_recusado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("horarios_funcionamento", sa.JSON(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("tipo_servico", sa.String(50), nullable=False, server_default="barbearia"),
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#d4930a"),
        sa.Column("bg_color", sa.String(7), nullable=False, server_default="#ffffff"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("notif_ativo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notif_horas_antes", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("intervalo_minutos", sa.Integer(), nullable=False, server_default="30"),
        sa.UniqueConstraint("slug", name="ux_estabelecimentos_slug"),
        sa.UniqueConstraint("mega_instance_key", name="uq_estabelecimentos_mega_instance_key"),
        sa.UniqueConstraint("whatsapp_number", name="uq_estabelecimentos_whatsapp_number"),
        sa.UniqueConstraint("login", name="uq_estabelecimentos_login"),
    )
    op.create_index("ix_estabelecimentos_id", "estabelecimentos", ["id"])
    op.create_index("ix_estabelecimentos_slug", "estabelecimentos", ["slug"])
    op.create_index("ix_estabelecimentos_mega_instance_key", "estabelecimentos", ["mega_instance_key"])
    op.create_index("ix_estabelecimentos_whatsapp_number", "estabelecimentos", ["whatsapp_number"])

    op.create_table(
        "profissionais",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tempo_por_servico", sa.JSON(), nullable=True),
        sa.Column("horarios_funcionamento", sa.JSON(), nullable=True),
    )
    op.create_index("ix_profissionais_id", "profissionais", ["id"])
    op.create_index("ix_profissionais_estabelecimento_id", "profissionais", ["estabelecimento_id"])
    op.create_index("ix_profissionais_ativo", "profissionais", ["ativo"])

    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("etapa_atual", sa.String(100), nullable=False, server_default="inicio"),
        sa.Column("contexto", sa.JSON(), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
    )
    op.create_index("ix_clientes_id", "clientes", ["id"])
    op.create_index("ix_clientes_telefone", "clientes", ["telefone"])
    op.create_index("ix_clientes_email", "clientes", ["email"])
    op.create_unique_constraint("ux_clientes_estabelecimento_telefone", "clientes", ["estabelecimento_id", "telefone"])

    op.create_table(
        "servicos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("duracao_minutos", sa.Integer(), nullable=False),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False),
        sa.Column("pagamento_adiantado_obrigatorio", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("advance_payment_type", sa.String(20), nullable=True),
        sa.Column("advance_payment_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_description_override", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
    )
    op.create_index("ix_servicos_id", "servicos", ["id"])
    op.create_index("ix_servicos_estabelecimento_id", "servicos", ["estabelecimento_id"])

    op.create_table(
        "agendamentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("profissional_id", sa.Integer(), sa.ForeignKey("profissionais.id"), nullable=False),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id"), nullable=False),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("cliente_nome", sa.String(255), nullable=True),
        sa.Column("cliente_telefone", sa.String(30), nullable=True),
        sa.Column("cliente_email", sa.String(255), nullable=True),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("hora_inicio", sa.Time(), nullable=True),
        sa.Column("data_hora_inicio", sa.DateTime(), nullable=False),
        sa.Column("data_hora_fim", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pendente"),
        sa.Column("confirmation_token", sa.String(36), nullable=False),
        sa.Column("confirmation_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("lembrete_24h_enviado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lembrete_2h_enviado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("compareceu_em", sa.DateTime(), nullable=True),
        sa.Column("pagamento_adiantado_exigido", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payment_type_snapshot", sa.String(20), nullable=True),
        sa.Column("payment_amount_snapshot", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="not_required"),
        sa.Column("payment_hold_expires_at", sa.DateTime(), nullable=True),
        sa.Column("provider_checkout_reference", sa.String(255), nullable=True),
        sa.Column("provider_preference_id", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_agendamentos_id", "agendamentos", ["id"])
    op.create_index("ix_agendamentos_estabelecimento_id", "agendamentos", ["estabelecimento_id"])
    op.create_index("ix_agendamentos_cliente_telefone", "agendamentos", ["cliente_telefone"])
    op.create_index("ix_agendamentos_cliente_email", "agendamentos", ["cliente_email"])
    op.create_index("ix_agendamentos_data", "agendamentos", ["data"])
    op.create_index("ix_agendamentos_confirmation_token", "agendamentos", ["confirmation_token"])
    op.create_index("ix_agendamentos_payment_status", "agendamentos", ["payment_status"])
    op.create_index("ix_agendamentos_payment_hold_expires_at", "agendamentos", ["payment_hold_expires_at"])
    op.create_index("ix_agendamentos_pagamento_adiantado_exigido", "agendamentos", ["pagamento_adiantado_exigido"])
    op.create_index(
        "ix_agendamentos_tenant_data_barbeiro",
        "agendamentos",
        ["estabelecimento_id", "data", "profissional_id"],
    )
    op.create_unique_constraint("ux_agendamentos_confirmation_token", "agendamentos", ["confirmation_token"])

    op.create_table(
        "token_blacklist",
        sa.Column("jti", sa.String(36), primary_key=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_token_blacklist_expires_at", "token_blacklist", ["expires_at"])

    op.create_table(
        "conversas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("estado", sa.String(50), nullable=False, server_default="inicio"),
        sa.Column("contexto", sa.JSON(), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "telefone", name="ux_conversas_tenant_telefone"),
    )
    op.create_index("ix_conversas_id", "conversas", ["id"])
    op.create_index("ix_conversas_tenant_id", "conversas", ["tenant_id"])
    op.create_index("ix_conversas_telefone", "conversas", ["telefone"])
    op.create_index("ix_conversas_ativa", "conversas", ["ativa"])
    op.create_index("ix_conversas_criado_em", "conversas", ["criado_em"])
    op.create_index("ix_conversas_atualizado_em", "conversas", ["atualizado_em"])
    op.create_index("ix_conversas_tenant_ativa", "conversas", ["tenant_id", "ativa"])

    op.create_table(
        "reminder_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agendamento_id", sa.Integer(), sa.ForeignKey("agendamentos.id"), nullable=False),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("enviado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enviar_em", sa.DateTime(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_reminder_jobs_id", "reminder_jobs", ["id"])
    op.create_index("ix_reminder_jobs_agendamento_id", "reminder_jobs", ["agendamento_id"])
    op.create_index("ix_reminder_jobs_estabelecimento_id", "reminder_jobs", ["estabelecimento_id"])
    op.create_index("ix_reminder_jobs_enviar_em", "reminder_jobs", ["enviar_em"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_webhook_events_id", "webhook_events", ["id"])
    op.create_index("ix_webhook_events_estabelecimento_id", "webhook_events", ["estabelecimento_id"])

    op.create_table(
        "payment_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="mercadopago"),
        sa.Column("account_name", sa.String(120), nullable=True),
        sa.Column("client_id_encrypted", sa.Text(), nullable=True),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("external_user_id", sa.String(120), nullable=True),
        sa.Column("external_account_email", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("public_key_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(120), nullable=True),
        sa.Column("updated_by_admin_id", sa.String(120), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("checkout_hold_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("establishment_id", "provider", name="ux_payment_accounts_establishment_provider"),
        sa.UniqueConstraint("provider", "external_user_id", name="ux_payment_accounts_provider_external_user_id"),
    )
    op.create_index("ix_payment_accounts_id", "payment_accounts", ["id"])
    op.create_index("ix_payment_accounts_establishment_id", "payment_accounts", ["establishment_id"])
    op.create_index("ix_payment_accounts_provider", "payment_accounts", ["provider"])
    op.create_index("ix_payment_accounts_status", "payment_accounts", ["status"])

    op.create_table(
        "payment_integrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="mercadopago"),
        sa.Column("environment", sa.String(20), nullable=False, server_default="production"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_validation"),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("credentials_fingerprint", sa.String(64), nullable=True),
        sa.Column("public_metadata_encrypted", sa.Text(), nullable=True),
        sa.Column("account_name", sa.String(120), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("checkout_hold_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_validated_at", sa.DateTime(), nullable=True),
        sa.Column("validation_status", sa.String(30), nullable=False, server_default="not_validated"),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(120), nullable=True),
        sa.Column("updated_by_admin_id", sa.String(120), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "establishment_id", "provider", "environment",
            name="ux_payment_integrations_establishment_provider_environment",
        ),
        sa.UniqueConstraint(
            "provider", "environment", "credentials_fingerprint",
            name="ux_payment_integrations_provider_environment_fingerprint",
        ),
    )
    op.create_index("ix_payment_integrations_id", "payment_integrations", ["id"])
    op.create_index("ix_payment_integrations_establishment_id", "payment_integrations", ["establishment_id"])
    op.create_index("ix_payment_integrations_provider", "payment_integrations", ["provider"])
    op.create_index("ix_payment_integrations_environment", "payment_integrations", ["environment"])
    op.create_index("ix_payment_integrations_status", "payment_integrations", ["status"])
    op.create_index("ix_payment_integrations_validation_status", "payment_integrations", ["validation_status"])

    op.create_table(
        "payment_oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("state_token", sa.String(64), nullable=False, unique=True),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payment_oauth_states_id", "payment_oauth_states", ["id"])
    op.create_index("ix_payment_oauth_states_state_token", "payment_oauth_states", ["state_token"])
    op.create_index("ix_payment_oauth_states_expires_at", "payment_oauth_states", ["expires_at"])

    op.create_table(
        "pagamentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agendamento_id", sa.Integer(), sa.ForeignKey("agendamentos.id"), nullable=False, unique=True),
        sa.Column("estabelecimento_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("payment_account_id", sa.Integer(), sa.ForeignKey("payment_accounts.id"), nullable=True),
        sa.Column("payment_integration_id", sa.Integer(), sa.ForeignKey("payment_integrations.id"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="mercado_pago"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("provider_payment_id", sa.String(120), nullable=True, unique=True),
        sa.Column("preference_id", sa.String(120), nullable=True, unique=True),
        sa.Column("external_merchant_order_id", sa.String(120), nullable=True),
        sa.Column("external_status", sa.String(80), nullable=True),
        sa.Column("external_reference", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_fee_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="BRL"),
        sa.Column("payment_method", sa.String(80), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("checkout_url", sa.String(700), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_pagamentos_id", "pagamentos", ["id"])
    op.create_index("ix_pagamentos_agendamento_id", "pagamentos", ["agendamento_id"])
    op.create_index("ix_pagamentos_estabelecimento_id", "pagamentos", ["estabelecimento_id"])
    op.create_index("ix_pagamentos_payment_account_id", "pagamentos", ["payment_account_id"])
    op.create_index("ix_pagamentos_payment_integration_id", "pagamentos", ["payment_integration_id"])
    op.create_index("ix_pagamentos_provider", "pagamentos", ["provider"])
    op.create_index("ix_pagamentos_status", "pagamentos", ["status"])
    op.create_index("ix_pagamentos_provider_payment_id", "pagamentos", ["provider_payment_id"])
    op.create_index("ix_pagamentos_preference_id", "pagamentos", ["preference_id"])
    op.create_index("ix_pagamentos_expires_at", "pagamentos", ["expires_at"])
    op.create_index("ix_pagamentos_created_at", "pagamentos", ["created_at"])
    op.create_index("ix_pagamentos_updated_at", "pagamentos", ["updated_at"])
    op.create_unique_constraint("ux_pagamentos_idempotency_key", "pagamentos", ["idempotency_key"])
    op.create_unique_constraint("ux_pagamentos_external_reference", "pagamentos", ["external_reference"])

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("pagamentos.id"), nullable=True),
        sa.Column("external_event_id", sa.String(255), nullable=True),
        sa.Column("external_topic", sa.String(120), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "provider", "external_event_id",
            name="ux_payment_webhook_events_provider_external_event_id",
        ),
    )
    op.create_index("ix_payment_webhook_events_id", "payment_webhook_events", ["id"])
    op.create_index("ix_payment_webhook_events_provider", "payment_webhook_events", ["provider"])
    op.create_index("ix_payment_webhook_events_establishment_id", "payment_webhook_events", ["establishment_id"])
    op.create_index("ix_payment_webhook_events_payment_id", "payment_webhook_events", ["payment_id"])
    op.create_index("ix_payment_webhook_events_external_event_id", "payment_webhook_events", ["external_event_id"])
    op.create_index("ix_payment_webhook_events_processing_status", "payment_webhook_events", ["processing_status"])
    op.create_index("ix_payment_webhook_events_received_at", "payment_webhook_events", ["received_at"])

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_user_id", sa.String(120), nullable=False),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=True),
        sa.Column("ip_address", sa.String(80), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_admin_audit_logs_id", "admin_audit_logs", ["id"])
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"])
    op.create_index("ix_admin_audit_logs_establishment_id", "admin_audit_logs", ["establishment_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_entity", "admin_audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_table("payment_webhook_events")
    op.drop_table("pagamentos")
    op.drop_table("payment_oauth_states")
    op.drop_table("payment_integrations")
    op.drop_table("payment_accounts")
    op.drop_table("webhook_events")
    op.drop_table("reminder_jobs")
    op.drop_table("conversas")
    op.drop_table("token_blacklist")
    op.drop_table("agendamentos")
    op.drop_table("servicos")
    op.drop_table("clientes")
    op.drop_table("profissionais")
    op.drop_table("estabelecimentos")
