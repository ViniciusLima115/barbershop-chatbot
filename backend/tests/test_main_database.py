from contextlib import contextmanager

from fastapi.testclient import TestClient


def test_main_home_e_startup(monkeypatch):
    import app.main as main_module

    chamado = {"ok": False}

    def fake_init_db():
        chamado["ok"] = True

    monkeypatch.setattr(main_module, "init_db", fake_init_db)

    # Cobre o corpo da funcao de startup explicitamente.
    main_module.startup()
    assert chamado["ok"] is True

    with TestClient(main_module.app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_database_get_db_yield():
    from app import database

    gen = database.get_db()
    db = next(gen)
    assert db is not None

    try:
        next(gen)
    except StopIteration:
        pass


def test_database_init_db_chama_create_all(monkeypatch):
    from app import database

    chamadas = {"create_all": False, "clientes": False, "barbearias": False, "barbeiros": False}

    def fake_create_all(bind):
        chamadas["create_all"] = True
        assert bind is database.engine

    def fake_ensure_clientes():
        chamadas["clientes"] = True

    def fake_ensure_barbearias():
        chamadas["barbearias"] = True

    def fake_ensure_barbeiros():
        chamadas["barbeiros"] = True

    monkeypatch.setattr(database.Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr(database, "_ensure_clientes_contexto_column", fake_ensure_clientes)
    monkeypatch.setattr(database, "_ensure_barbearias_admin_columns", fake_ensure_barbearias)
    monkeypatch.setattr(database, "_ensure_barbeiros_barbershop_column", fake_ensure_barbeiros)

    database.init_db()
    assert chamadas["create_all"] is True
    assert chamadas["clientes"] is True
    assert chamadas["barbearias"] is True
    assert chamadas["barbeiros"] is True


def test_database_ensure_clientes_contexto_column_sucesso(monkeypatch):
    from app import database

    chamadas = {"begin": False, "execute": False}

    class DummyConn:
        def execute(self, _sql):
            chamadas["execute"] = True

    @contextmanager
    def fake_begin():
        chamadas["begin"] = True
        yield DummyConn()

    monkeypatch.setattr(database.engine, "begin", fake_begin)
    database._ensure_clientes_contexto_column()

    assert chamadas["begin"] is True
    assert chamadas["execute"] is True


def test_database_ensure_clientes_contexto_column_ignora_excecao(monkeypatch):
    from app import database

    @contextmanager
    def fake_begin_com_erro():
        raise RuntimeError("erro proposital")
        yield

    monkeypatch.setattr(database.engine, "begin", fake_begin_com_erro)
    # Nao deve levantar excecao.
    database._ensure_clientes_contexto_column()


def test_database_ensure_barbeiros_barbershop_column_sucesso(monkeypatch):
    from app import database

    chamadas = {"begin": 0, "execute": 0}

    class DummyConn:
        def execute(self, _sql):
            chamadas["execute"] += 1

    @contextmanager
    def fake_begin():
        chamadas["begin"] += 1
        yield DummyConn()

    monkeypatch.setattr(database.engine, "begin", fake_begin)
    database._ensure_barbeiros_barbershop_column()

    assert chamadas["begin"] == 3
    assert chamadas["execute"] == 3


def test_database_ensure_barbeiros_barbershop_column_ignora_excecao(monkeypatch):
    from app import database

    @contextmanager
    def fake_begin_com_erro():
        raise RuntimeError("erro proposital")
        yield

    monkeypatch.setattr(database.engine, "begin", fake_begin_com_erro)
    # Nao deve levantar excecao.
    database._ensure_barbeiros_barbershop_column()
