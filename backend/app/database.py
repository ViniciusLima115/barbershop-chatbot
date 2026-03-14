import os
import re
import unicodedata
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

IS_MYSQL = "mysql" in (engine.dialect.name or "").lower()


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


def init_db():
    from app.models import (
        barbeiro,
        barbearia,
        cliente,
        servico,
        agendamento,
        conversa,
        reminder_job,
        webhook_event,
    )
    if _should_run_create_all():
        Base.metadata.create_all(bind=engine)
    _ensure_barbearias_working_hours_column()
    _ensure_barbeiros_working_hours_column()
    if IS_MYSQL:
        _ensure_clientes_contexto_column()
        _ensure_clientes_tenant_indexes()
        _ensure_barbearias_admin_columns()
        _ensure_barbearias_slug()
        _ensure_barbeiros_barbershop_column()
        _ensure_barbeiros_public_columns()
        _ensure_conversas_multi_tenant()
        _ensure_agendamentos_barbearia_column()
        _ensure_agendamentos_public_columns()


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
