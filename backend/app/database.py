import logging
import os
import re
import unicodedata
from datetime import datetime
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

IS_MYSQL = "mysql" in (engine.dialect.name or "").lower()
IS_POSTGRES = "postgresql" in (engine.dialect.name or "").lower()
logger = logging.getLogger(__name__)


def _str_to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _should_run_create_all() -> bool:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    default = app_env not in {"prod", "production"}
    return _str_to_bool(os.getenv("INIT_DB_CREATE_ALL"), default=default)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_token_blacklist_table():
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS token_blacklist ("
                "  jti VARCHAR(36) PRIMARY KEY,"
                "  expires_at TIMESTAMP NOT NULL"
                ")"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_token_blacklist_expires_at "
                "ON token_blacklist (expires_at)"
            ))
    except Exception:
        pass


def init_db():
    from app.models import (
        barbeiro,
        barbearia,
        cliente,
        servico,
        agendamento,
        conversa,
        reminder_job,
        pagamento,
        payment_account,
        payment_oauth_state,
        payment_webhook_event,
        webhook_event,
        token_blacklist,
    )
    if _should_run_create_all():
        Base.metadata.create_all(bind=engine)
    _ensure_clientes_email_column()
    _ensure_barbearias_working_hours_column()
    _ensure_barbeiros_working_hours_column()
    _ensure_agendamentos_public_columns()
    _ensure_agendamentos_notification_columns()
    _ensure_agendamentos_compareceu_column()
    _ensure_servicos_payment_columns()
    _ensure_agendamentos_payment_columns()
    _ensure_pagamentos_table()
    _ensure_postgres_schema_guards()
    if IS_MYSQL:
        _ensure_clientes_contexto_column()
        _ensure_clientes_tenant_indexes()
        _ensure_barbearias_admin_columns()
        _ensure_barbearias_slug()
        _ensure_barbeiros_barbershop_column()
        _ensure_barbeiros_public_columns()
        _ensure_conversas_multi_tenant()
        _ensure_agendamentos_barbearia_column()
    _backfill_agendamentos_notification_defaults()
    _ensure_token_blacklist_table()
    _ensure_rename_para_estabelecimentos()
    _sync_estabelecimentos_e_barbearias()
    _sync_profissionais_e_barbeiros()
    _ensure_tipo_servico_column()
    _ensure_configuracoes_columns()
    _ensure_intervalo_minutos_column()


def _ensure_configuracoes_columns():
    """Adiciona colunas de configuração (tema, notificações) em estabelecimentos."""
    _run_best_effort([
        "ALTER TABLE estabelecimentos ADD COLUMN accent_color VARCHAR(7) NOT NULL DEFAULT '#d4930a'",
        "ALTER TABLE estabelecimentos ADD COLUMN bg_color VARCHAR(7) NOT NULL DEFAULT '#ffffff'",
        "ALTER TABLE estabelecimentos ADD COLUMN logo_url VARCHAR(500)",
        "ALTER TABLE estabelecimentos ADD COLUMN notif_ativo BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE estabelecimentos ADD COLUMN notif_horas_antes INTEGER NOT NULL DEFAULT 2",
    ])


def _ensure_intervalo_minutos_column():
    """Adiciona coluna intervalo_minutos em estabelecimentos (default 30 min)."""
    _run_best_effort([
        "ALTER TABLE estabelecimentos ADD COLUMN intervalo_minutos INTEGER NOT NULL DEFAULT 30",
    ])


def _ensure_clientes_email_column():
    _run_best_effort([
        "ALTER TABLE clientes ADD COLUMN email VARCHAR(255) NULL",
        "CREATE INDEX ix_clientes_email ON clientes (email)",
    ])


def _ensure_agendamentos_compareceu_column():
    _run_best_effort([
        "ALTER TABLE agendamentos ADD COLUMN compareceu_em TIMESTAMP NULL",
    ])


def _ensure_servicos_payment_columns():
    _run_best_effort([
        "ALTER TABLE servicos ADD COLUMN pagamento_adiantado_obrigatorio BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE servicos ADD COLUMN advance_payment_type VARCHAR(20) NULL",
        "ALTER TABLE servicos ADD COLUMN advance_payment_amount FLOAT NULL",
        "ALTER TABLE servicos ADD COLUMN payment_description_override TEXT NULL",
        "ALTER TABLE servicos ADD COLUMN updated_at TIMESTAMP NULL",
    ])


def _ensure_agendamentos_payment_columns():
    _run_best_effort([
        "ALTER TABLE agendamentos ADD COLUMN pagamento_adiantado_exigido BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE agendamentos ADD COLUMN payment_type_snapshot VARCHAR(20) NULL",
        "ALTER TABLE agendamentos ADD COLUMN payment_amount_snapshot FLOAT NULL",
        "ALTER TABLE agendamentos ADD COLUMN payment_status VARCHAR(30) NOT NULL DEFAULT 'not_required'",
        "ALTER TABLE agendamentos ADD COLUMN payment_hold_expires_at TIMESTAMP NULL",
        "ALTER TABLE agendamentos ADD COLUMN provider_checkout_reference VARCHAR(255) NULL",
        "ALTER TABLE agendamentos ADD COLUMN provider_preference_id VARCHAR(255) NULL",
        "ALTER TABLE agendamentos ADD COLUMN updated_at TIMESTAMP NULL",
        "CREATE INDEX ix_agendamentos_payment_status ON agendamentos (payment_status)",
        "CREATE INDEX ix_agendamentos_payment_hold_expires_at ON agendamentos (payment_hold_expires_at)",
    ])


def _ensure_pagamentos_table():
    try:
        from app.models.payment_account import PaymentAccount
        from app.models.payment_oauth_state import PaymentOAuthState
        from app.models.payment_webhook_event import PaymentWebhookEvent
        from app.models.pagamento import Pagamento

        PaymentAccount.__table__.create(bind=engine, checkfirst=True)
        PaymentOAuthState.__table__.create(bind=engine, checkfirst=True)
        Pagamento.__table__.create(bind=engine, checkfirst=True)
        PaymentWebhookEvent.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass

    _run_best_effort([
        "ALTER TABLE payment_accounts ADD COLUMN account_name VARCHAR(120) NULL",
        "ALTER TABLE payment_accounts ADD COLUMN client_id_encrypted TEXT NULL",
        "ALTER TABLE payment_accounts ADD COLUMN client_secret_encrypted TEXT NULL",
        "ALTER TABLE payment_accounts ADD COLUMN internal_notes TEXT NULL",
        "ALTER TABLE payment_accounts ADD COLUMN created_by_admin_id VARCHAR(120) NULL",
        "ALTER TABLE payment_accounts ADD COLUMN updated_by_admin_id VARCHAR(120) NULL",
        "ALTER TABLE pagamentos ADD COLUMN estabelecimento_id INTEGER NULL",
        "ALTER TABLE pagamentos ADD COLUMN payment_account_id INTEGER NULL",
        "ALTER TABLE pagamentos ADD COLUMN idempotency_key VARCHAR(120) NULL",
        "ALTER TABLE pagamentos ADD COLUMN external_merchant_order_id VARCHAR(120) NULL",
        "ALTER TABLE pagamentos ADD COLUMN external_status VARCHAR(80) NULL",
        "ALTER TABLE pagamentos ADD COLUMN platform_fee_amount FLOAT NOT NULL DEFAULT 0",
        "ALTER TABLE pagamentos ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT 'BRL'",
        "ALTER TABLE pagamentos ADD COLUMN payment_method VARCHAR(80) NULL",
        "ALTER TABLE pagamentos ADD COLUMN paid_at TIMESTAMP NULL",
        "ALTER TABLE pagamentos ADD COLUMN expires_at TIMESTAMP NULL",
        "CREATE UNIQUE INDEX ux_pagamentos_idempotency_key ON pagamentos (idempotency_key)",
        "CREATE INDEX ix_pagamentos_estabelecimento_id ON pagamentos (estabelecimento_id)",
        "CREATE INDEX ix_pagamentos_payment_account_id ON pagamentos (payment_account_id)",
        "CREATE INDEX ix_pagamentos_expires_at ON pagamentos (expires_at)",
    ])


def _ensure_postgres_schema_guards():
    """
    Guardas explícitas para colunas críticas em Postgres (Neon).
    Evita 500 por schema defasado quando o app evolui mais rápido que o banco.
    """
    if not IS_POSTGRES:
        return

    statements = [
        # clientes.email
        """
        ALTER TABLE clientes
        ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL
        """,
        "CREATE INDEX IF NOT EXISTS ix_clientes_email ON clientes (email)",

        # agendamentos.compareceu_em
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS compareceu_em TIMESTAMP NULL
        """,

        # servicos.pagamento_adiantado_obrigatorio
        """
        ALTER TABLE servicos
        ADD COLUMN IF NOT EXISTS pagamento_adiantado_obrigatorio BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE servicos
        ADD COLUMN IF NOT EXISTS advance_payment_type VARCHAR(20) NULL
        """,
        """
        ALTER TABLE servicos
        ADD COLUMN IF NOT EXISTS advance_payment_amount FLOAT NULL
        """,
        """
        ALTER TABLE servicos
        ADD COLUMN IF NOT EXISTS payment_description_override TEXT NULL
        """,
        """
        ALTER TABLE servicos
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NULL
        """,

        # agendamentos.pagamento_adiantado_exigido
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS pagamento_adiantado_exigido BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS payment_type_snapshot VARCHAR(20) NULL
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS payment_amount_snapshot FLOAT NULL
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS payment_status VARCHAR(30) NOT NULL DEFAULT 'not_required'
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS payment_hold_expires_at TIMESTAMP NULL
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS provider_checkout_reference VARCHAR(255) NULL
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS provider_preference_id VARCHAR(255) NULL
        """,
        """
        ALTER TABLE agendamentos
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NULL
        """,
        "CREATE INDEX IF NOT EXISTS ix_agendamentos_payment_status ON agendamentos (payment_status)",
        "CREATE INDEX IF NOT EXISTS ix_agendamentos_payment_hold_expires_at ON agendamentos (payment_hold_expires_at)",

        # payment_accounts administrado pelo master
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS account_name VARCHAR(120) NULL
        """,
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS client_id_encrypted TEXT NULL
        """,
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS client_secret_encrypted TEXT NULL
        """,
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS internal_notes TEXT NULL
        """,
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS created_by_admin_id VARCHAR(120) NULL
        """,
        """
        ALTER TABLE payment_accounts
        ADD COLUMN IF NOT EXISTS updated_by_admin_id VARCHAR(120) NULL
        """,

        # pagamentos v2
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS estabelecimento_id INTEGER NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS payment_account_id INTEGER NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(120) NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS external_merchant_order_id VARCHAR(120) NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS external_status VARCHAR(80) NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS platform_fee_amount FLOAT NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS currency VARCHAR(10) NOT NULL DEFAULT 'BRL'
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS payment_method VARCHAR(80) NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP NULL
        """,
        """
        ALTER TABLE pagamentos
        ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP NULL
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_pagamentos_idempotency_key ON pagamentos (idempotency_key)",
        "CREATE INDEX IF NOT EXISTS ix_pagamentos_estabelecimento_id ON pagamentos (estabelecimento_id)",
        "CREATE INDEX IF NOT EXISTS ix_pagamentos_payment_account_id ON pagamentos (payment_account_id)",
        "CREATE INDEX IF NOT EXISTS ix_pagamentos_expires_at ON pagamentos (expires_at)",
    ]

    for sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            logger.exception("Falha ao aplicar guarda de schema Postgres: %s", sql.strip().splitlines()[0])


def _ensure_barbearias_working_hours_column():
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE barbearias ADD COLUMN horarios_funcionamento JSON NULL"))
    except Exception:
        pass


def _ensure_barbeiros_working_hours_column():
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE barbeiros ADD COLUMN horarios_funcionamento JSON NULL"))
    except Exception:
        pass


def _run_best_effort(statements: list[str]):
    for sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass


def _ensure_clientes_contexto_column():
    # Backward-compatible schema fix for deployments created before `clientes.contexto`.
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clientes ADD COLUMN contexto JSON NULL"))
    except Exception:
        # Ignore if the column already exists or if DB dialect does not support JSON ALTER syntax.
        pass


def _ensure_clientes_tenant_indexes():
    # Best-effort migration for multi-tenant uniqueness: (barbearia_id, telefone).
    drop_global_unique = [
        "ALTER TABLE clientes DROP INDEX telefone",
        "ALTER TABLE clientes DROP INDEX ix_clientes_telefone",
        "ALTER TABLE clientes DROP INDEX uq_clientes_telefone",
    ]

    create_indexes = [
        "CREATE INDEX ix_clientes_telefone ON clientes (telefone)",
        "CREATE UNIQUE INDEX ux_clientes_barbearia_telefone ON clientes (barbearia_id, telefone)",
    ]

    _run_best_effort(drop_global_unique)
    _run_best_effort(create_indexes)


def _ensure_barbearias_admin_columns():
    alter_statements = [
        "ALTER TABLE barbearias ADD COLUMN login VARCHAR(255) NULL UNIQUE",
        "ALTER TABLE barbearias ADD COLUMN senha VARCHAR(255) NULL",
        "ALTER TABLE barbearias ADD COLUMN slug VARCHAR(120) NULL",
        "ALTER TABLE barbearias ADD COLUMN mega_instance_key VARCHAR(255) NULL UNIQUE",
        "ALTER TABLE barbearias ADD COLUMN mega_token VARCHAR(255) NULL",
        "ALTER TABLE barbearias ADD COLUMN whatsapp_number VARCHAR(30) NULL UNIQUE",
        "ALTER TABLE barbearias ADD COLUMN plano VARCHAR(50) NULL DEFAULT 'basico'",
        "ALTER TABLE barbearias ADD COLUMN status_manual VARCHAR(50) NULL DEFAULT 'ativo'",
        "ALTER TABLE barbearias ADD COLUMN vencimento_em DATE NULL",
        "ALTER TABLE barbearias ADD COLUMN trial_ativo BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE barbearias ADD COLUMN trial_fim_em DATE NULL",
        "ALTER TABLE barbearias ADD COLUMN ultimo_acesso_em DATETIME NULL",
        "ALTER TABLE barbearias ADD COLUMN pagamento_recusado BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE barbearias ADD COLUMN criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    ]

    _run_best_effort(alter_statements)


def _slugify(value: str | None) -> str:
    texto = (value or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto or "barbearia"


def _ensure_barbearias_slug():
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT id, nome, slug FROM barbearias ORDER BY id ASC")).mappings().all()
            if not rows:
                return

            usados: set[str] = set()
            updates: list[dict[str, str | int]] = []
            for row in rows:
                valor_origem = row.get("slug") or row.get("nome") or f"barbearia-{row['id']}"
                base = _slugify(str(valor_origem))
                slug = base
                idx = 2
                while slug in usados:
                    slug = f"{base}-{idx}"
                    idx += 1
                usados.add(slug)
                if row.get("slug") != slug:
                    updates.append({"id": int(row["id"]), "slug": slug})

            for payload in updates:
                conn.execute(
                    text("UPDATE barbearias SET slug = :slug WHERE id = :id"),
                    payload,
                )
    except Exception:
        pass

    _run_best_effort(
        [
            "CREATE UNIQUE INDEX ux_barbearias_slug ON barbearias (slug)",
            "CREATE INDEX ix_barbearias_slug ON barbearias (slug)",
        ]
    )


def _ensure_barbeiros_barbershop_column():
    statements = [
        "ALTER TABLE barbeiros ADD COLUMN barbershop_id INTEGER NULL",
        "UPDATE barbeiros SET barbershop_id = barbearia_id WHERE barbershop_id IS NULL",
        "CREATE INDEX ix_barbeiros_barbershop_id ON barbeiros (barbershop_id)",
    ]

    _run_best_effort(statements)


def _ensure_barbeiros_public_columns():
    _run_best_effort(
        [
            "ALTER TABLE barbeiros ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE barbeiros ADD COLUMN tempo_por_servico JSON NULL",
            "ALTER TABLE barbeiros ADD COLUMN horarios_funcionamento JSON NULL",
            "CREATE INDEX ix_barbeiros_ativo ON barbeiros (ativo)",
        ]
    )


def _ensure_conversas_multi_tenant():
    _run_best_effort(
        [
            "ALTER TABLE conversas ADD COLUMN tenant_id INTEGER NULL",
            "ALTER TABLE conversas ADD COLUMN ativa BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE conversas ADD COLUMN criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE conversas ADD COLUMN atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "CREATE INDEX ix_conversas_tenant_id ON conversas (tenant_id)",
            "CREATE INDEX ix_conversas_ativa ON conversas (ativa)",
            "CREATE INDEX ix_conversas_tenant_ativa ON conversas (tenant_id, ativa)",
        ]
    )

    _run_best_effort(
        [
            "ALTER TABLE conversas DROP INDEX telefone",
            "ALTER TABLE conversas DROP INDEX ix_conversas_telefone",
        ]
    )

    _run_best_effort(
        [
            "CREATE INDEX ix_conversas_telefone ON conversas (telefone)",
            "CREATE UNIQUE INDEX ux_conversas_tenant_telefone ON conversas (tenant_id, telefone)",
        ]
    )


def _ensure_agendamentos_barbearia_column():
    statements = [
        "ALTER TABLE agendamentos ADD COLUMN barbearia_id INTEGER NULL",
        (
            "UPDATE agendamentos SET barbearia_id = ("
            "SELECT barbershop_id FROM barbeiros WHERE barbeiros.id = agendamentos.barbeiro_id"
            ") WHERE barbearia_id IS NULL"
        ),
        "CREATE INDEX ix_agendamentos_barbearia_id ON agendamentos (barbearia_id)",
    ]

    _run_best_effort(statements)


def _as_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _ensure_agendamentos_public_columns():
    _run_best_effort(
        [
            "ALTER TABLE agendamentos ADD COLUMN cliente_nome VARCHAR(255) NULL",
            "ALTER TABLE agendamentos ADD COLUMN cliente_telefone VARCHAR(30) NULL",
            "ALTER TABLE agendamentos ADD COLUMN data DATE NULL",
            "ALTER TABLE agendamentos ADD COLUMN hora_inicio TIME NULL",
            "CREATE INDEX ix_agendamentos_cliente_telefone ON agendamentos (cliente_telefone)",
            "CREATE INDEX ix_agendamentos_data ON agendamentos (data)",
            (
                "CREATE INDEX ix_agendamentos_tenant_data_barbeiro "
                "ON agendamentos (barbearia_id, data, barbeiro_id)"
            ),
        ]
    )

    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT a.id, a.data_hora_inicio, a.cliente_nome, a.cliente_telefone, a.data, a.hora_inicio, "
                    "c.nome AS nome_cliente, c.telefone AS telefone_cliente "
                    "FROM agendamentos a LEFT JOIN clientes c ON c.id = a.cliente_id"
                )
            ).mappings().all()
            for row in rows:
                dt = _as_datetime(row.get("data_hora_inicio"))
                payload = {
                    "id": row["id"],
                    "cliente_nome": row.get("cliente_nome") or row.get("nome_cliente"),
                    "cliente_telefone": row.get("cliente_telefone") or row.get("telefone_cliente"),
                    "data": row.get("data") or (dt.date().isoformat() if dt else None),
                    "hora_inicio": row.get("hora_inicio") or (dt.time().replace(microsecond=0).isoformat() if dt else None),
                }
                conn.execute(
                    text(
                        "UPDATE agendamentos SET "
                        "cliente_nome = COALESCE(cliente_nome, :cliente_nome), "
                        "cliente_telefone = COALESCE(cliente_telefone, :cliente_telefone), "
                        "data = COALESCE(data, :data), "
                        "hora_inicio = COALESCE(hora_inicio, :hora_inicio) "
                        "WHERE id = :id"
                    ),
                    payload,
                )
    except Exception:
        pass


def _ensure_agendamentos_notification_columns():
    _run_best_effort(
        [
            "ALTER TABLE agendamentos ADD COLUMN cliente_email VARCHAR(255) NULL",
            "ALTER TABLE agendamentos ADD COLUMN confirmation_token VARCHAR(36) NULL",
            "ALTER TABLE agendamentos ADD COLUMN lembrete_24h_enviado BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE agendamentos ADD COLUMN lembrete_2h_enviado BOOLEAN NOT NULL DEFAULT FALSE",
            "CREATE INDEX ix_agendamentos_cliente_email ON agendamentos (cliente_email)",
            "CREATE UNIQUE INDEX ux_agendamentos_confirmation_token ON agendamentos (confirmation_token)",
        ]
    )


def _ensure_rename_para_estabelecimentos():
    """Renomeia tabelas e colunas para a nomenclatura genérica."""
    _run_best_effort([
        # Renomear tabelas
        "ALTER TABLE barbearias RENAME TO estabelecimentos",
        "ALTER TABLE barbeiros RENAME TO profissionais",

        # Renomear colunas em agendamentos
        "ALTER TABLE agendamentos RENAME COLUMN barbearia_id TO estabelecimento_id",
        "ALTER TABLE agendamentos RENAME COLUMN barbeiro_id TO profissional_id",

        # Renomear colunas em profissionais (ex-barbeiros)
        "ALTER TABLE profissionais RENAME COLUMN barbershop_id TO estabelecimento_id",

        # Renomear colunas em clientes
        "ALTER TABLE clientes RENAME COLUMN barbearia_id TO estabelecimento_id",

        # Renomear colunas em servicos
        "ALTER TABLE servicos RENAME COLUMN barbearia_id TO estabelecimento_id",

        # Renomear colunas em conversas
        "ALTER TABLE conversas RENAME COLUMN tenant_id TO estabelecimento_id",

        # Renomear colunas em reminder_jobs
        "ALTER TABLE reminder_jobs RENAME COLUMN tenant_id TO estabelecimento_id",
    ])


def _ensure_tipo_servico_column():
    """Adiciona coluna tipo_servico em estabelecimentos."""
    _run_best_effort([
        "ALTER TABLE estabelecimentos ADD COLUMN tipo_servico VARCHAR(50) NOT NULL DEFAULT 'barbearia'",
        "UPDATE estabelecimentos SET tipo_servico = 'barbearia' WHERE tipo_servico IS NULL",
    ])


def _sync_estabelecimentos_e_barbearias():
    """
    Mantem compatibilidade entre schemas legados (barbearias) e novo schema (estabelecimentos).
    Algumas FKs antigas ainda apontam para `barbearias`, entao garantimos linhas espelho.
    """
    statements = [
        # Copia registros novos do schema atual para tabela legada (usada por FKs antigas).
        """
        INSERT INTO barbearias (
            id, nome, slug, endereco, mega_instance_key, mega_token, whatsapp_number,
            login, senha, plano, status_manual, vencimento_em, trial_ativo, trial_fim_em,
            ultimo_acesso_em, pagamento_recusado, horarios_funcionamento, criado_em
        )
        SELECT
            e.id, e.nome, e.slug, e.endereco, e.mega_instance_key, e.mega_token, e.whatsapp_number,
            e.login, e.senha, e.plano, e.status_manual, e.vencimento_em, e.trial_ativo, e.trial_fim_em,
            e.ultimo_acesso_em, e.pagamento_recusado, e.horarios_funcionamento, e.criado_em
        FROM estabelecimentos e
        LEFT JOIN barbearias b ON b.id = e.id
        WHERE b.id IS NULL
        """,

        # Copia registros legados para schema atual, caso existam apenas em barbearias.
        """
        INSERT INTO estabelecimentos (
            id, nome, slug, endereco, mega_instance_key, mega_token, whatsapp_number,
            login, senha, plano, status_manual, vencimento_em, trial_ativo, trial_fim_em,
            ultimo_acesso_em, pagamento_recusado, horarios_funcionamento, criado_em
        )
        SELECT
            b.id, b.nome, b.slug, b.endereco, b.mega_instance_key, b.mega_token, b.whatsapp_number,
            b.login, b.senha, b.plano, b.status_manual, b.vencimento_em, b.trial_ativo, b.trial_fim_em,
            b.ultimo_acesso_em, b.pagamento_recusado, b.horarios_funcionamento, b.criado_em
        FROM barbearias b
        LEFT JOIN estabelecimentos e ON e.id = b.id
        WHERE e.id IS NULL
        """,

        # Mantem dados principais alinhados (evita drift entre tabelas).
        """
        UPDATE barbearias b
        SET
            nome = e.nome,
            slug = e.slug,
            endereco = e.endereco,
            mega_instance_key = e.mega_instance_key,
            mega_token = e.mega_token,
            whatsapp_number = e.whatsapp_number,
            login = e.login,
            senha = e.senha,
            plano = e.plano,
            status_manual = e.status_manual,
            vencimento_em = e.vencimento_em,
            trial_ativo = e.trial_ativo,
            trial_fim_em = e.trial_fim_em,
            ultimo_acesso_em = e.ultimo_acesso_em,
            pagamento_recusado = e.pagamento_recusado,
            horarios_funcionamento = e.horarios_funcionamento,
            criado_em = e.criado_em
        FROM estabelecimentos e
        WHERE b.id = e.id
        """,

        # Ajusta sequencias para evitar colisao de PK apos inserts manuais de id.
        "SELECT setval('barbearias_id_seq', COALESCE((SELECT MAX(id) FROM barbearias), 1), true)",
        "SELECT setval('estabelecimentos_id_seq', COALESCE((SELECT MAX(id) FROM estabelecimentos), 1), true)",
    ]

    _run_best_effort(statements)


def _sync_profissionais_e_barbeiros():
    """
    Mantem compatibilidade entre `profissionais` (novo) e `barbeiros` (legado).
    Algumas FKs antigas de agendamentos ainda apontam para `barbeiros`.
    """
    statements = [
        # Copia profissionais novos para tabela legada.
        """
        INSERT INTO barbeiros (
            id, nome, barbershop_id, ativo, tempo_por_servico, horarios_funcionamento
        )
        SELECT
            p.id, p.nome, p.estabelecimento_id, p.ativo, p.tempo_por_servico, p.horarios_funcionamento
        FROM profissionais p
        LEFT JOIN barbeiros b ON b.id = p.id
        WHERE b.id IS NULL
        """,

        # Copia barbeiros legados para tabela nova.
        """
        INSERT INTO profissionais (
            id, nome, estabelecimento_id, ativo, tempo_por_servico, horarios_funcionamento
        )
        SELECT
            b.id, b.nome, b.barbershop_id, b.ativo, b.tempo_por_servico, b.horarios_funcionamento
        FROM barbeiros b
        LEFT JOIN profissionais p ON p.id = b.id
        WHERE p.id IS NULL
        """,

        # Mantem dados principais alinhados.
        """
        UPDATE barbeiros b
        SET
            nome = p.nome,
            barbershop_id = p.estabelecimento_id,
            ativo = p.ativo,
            tempo_por_servico = p.tempo_por_servico,
            horarios_funcionamento = p.horarios_funcionamento
        FROM profissionais p
        WHERE b.id = p.id
        """,

        # Ajusta sequencias.
        "SELECT setval('barbeiros_id_seq', COALESCE((SELECT MAX(id) FROM barbeiros), 1), true)",
        "SELECT setval('profissionais_id_seq', COALESCE((SELECT MAX(id) FROM profissionais), 1), true)",
    ]

    _run_best_effort(statements)


def _backfill_agendamentos_notification_defaults():
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE agendamentos SET lembrete_24h_enviado = FALSE "
                    "WHERE lembrete_24h_enviado IS NULL"
                )
            )
            conn.execute(
                text(
                    "UPDATE agendamentos SET lembrete_2h_enviado = FALSE "
                    "WHERE lembrete_2h_enviado IS NULL"
                )
            )

            rows = conn.execute(
                text(
                    "SELECT id FROM agendamentos "
                    "WHERE confirmation_token IS NULL OR confirmation_token = ''"
                )
            ).mappings().all()
            for row in rows:
                conn.execute(
                    text(
                        "UPDATE agendamentos SET confirmation_token = :token WHERE id = :id"
                    ),
                    {"id": int(row["id"]), "token": str(uuid4())},
                )
    except Exception:
        pass
