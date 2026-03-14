def test_cors_regex_permite_rede_local_em_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CORS_ALLOWED_ORIGIN_REGEX", raising=False)
    monkeypatch.delenv("CORS_ALLOW_PRIVATE_NETWORKS", raising=False)

    from app.main import _get_cors_allow_origin_regex

    regex = _get_cors_allow_origin_regex()

    assert regex is not None
    assert "192\\.168" in regex


def test_cors_regex_desabilita_rede_local_em_producao(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGIN_REGEX", raising=False)
    monkeypatch.delenv("CORS_ALLOW_PRIVATE_NETWORKS", raising=False)

    from app.main import _get_cors_allow_origin_regex

    assert _get_cors_allow_origin_regex() is None
