from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


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
        conversa
    )
    Base.metadata.create_all(bind=engine)
    _ensure_clientes_contexto_column()
    _ensure_clientes_tenant_indexes()
    _ensure_barbearias_admin_columns()
    _ensure_barbeiros_barbershop_column()
    _ensure_agendamentos_barbearia_column()


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

    for sql in drop_global_unique:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass

    create_indexes = [
        "CREATE INDEX ix_clientes_telefone ON clientes (telefone)",
        "CREATE UNIQUE INDEX ux_clientes_barbearia_telefone ON clientes (barbearia_id, telefone)",
    ]

    for sql in create_indexes:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass


def _ensure_barbearias_admin_columns():
    alter_statements = [
        "ALTER TABLE barbearias ADD COLUMN login VARCHAR(255) NULL UNIQUE",
        "ALTER TABLE barbearias ADD COLUMN senha VARCHAR(255) NULL",
        "ALTER TABLE barbearias ADD COLUMN plano VARCHAR(50) NULL DEFAULT 'basico'",
        "ALTER TABLE barbearias ADD COLUMN status_manual VARCHAR(50) NULL DEFAULT 'ativo'",
        "ALTER TABLE barbearias ADD COLUMN vencimento_em DATE NULL",
        "ALTER TABLE barbearias ADD COLUMN trial_ativo BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE barbearias ADD COLUMN trial_fim_em DATE NULL",
        "ALTER TABLE barbearias ADD COLUMN ultimo_acesso_em DATETIME NULL",
        "ALTER TABLE barbearias ADD COLUMN pagamento_recusado BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE barbearias ADD COLUMN criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    ]

    for sql in alter_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            # Ignore when column already exists or DB dialect has different ALTER semantics.
            pass


def _ensure_barbeiros_barbershop_column():
    statements = [
        "ALTER TABLE barbeiros ADD COLUMN barbershop_id INTEGER NULL",
        "UPDATE barbeiros SET barbershop_id = barbearia_id WHERE barbershop_id IS NULL",
        "CREATE INDEX ix_barbeiros_barbershop_id ON barbeiros (barbershop_id)",
    ]

    for sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            # Ignore when column/index already exists or if SQL dialect differs.
            pass


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

    for sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            # Ignore when column/index already exists or if SQL dialect differs.
            pass
