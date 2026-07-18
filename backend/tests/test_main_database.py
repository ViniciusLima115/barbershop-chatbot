def test_database_get_db_yield():
    from app import database

    gen = database.get_db()
    db = next(gen)
    assert db is not None

    try:
        next(gen)
    except StopIteration:
        pass


def test_database_init_db_chama_encryption_check(monkeypatch):
    from app import database

    chamado = {"ok": False}

    def fake_ensure_key():
        chamado["ok"] = True

    monkeypatch.setattr(
        "app.services.payments.crypto.ensure_encryption_key_for_production",
        fake_ensure_key,
    )

    database.init_db()
    assert chamado["ok"] is True


def test_main_home_e_startup(monkeypatch):
    import app.main as main_module
    from fastapi.testclient import TestClient

    chamado = {"ok": False}

    def fake_init_db():
        chamado["ok"] = True

    monkeypatch.setattr(main_module, "init_db", fake_init_db)

    with TestClient(main_module.app) as client:
        assert chamado["ok"] is True
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
