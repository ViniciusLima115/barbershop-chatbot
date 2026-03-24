"""
Smoke test for rate limiting on /auth/login.
Tests that the @limiter.limit decorator is applied and returns 429 after limit.
Note: slowapi's TestClient respects the rate limit within the same process,
so this test exercises the actual limiting behavior.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import get_db
from app.limiter import limiter, RATE_LIMIT_LOGIN
from app.routes import auth


def make_app(session_factory):
    """Creates a test app backed by the real module-level limiter."""
    test_app = FastAPI()
    test_app.state.limiter = limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    test_app.include_router(auth.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


def test_login_retorna_429_apos_limite(session_factory):
    """Verify that the login endpoint returns 429 after exceeding the rate limit."""
    # Reset the limiter storage to start fresh (avoids state from other tests)
    # NOTE: reseta o storage interno do limiter para isolar o teste.
    # O decorator @limiter.limit() está vinculado ao singleton do módulo no momento
    # do import, então não é possível trocar o limiter por um de teste.
    # Os atributos _storage e _limiter são privados da lib `limits`; se quebrarem
    # em um upgrade, atualize o teste (ou adicione um método público de reset).
    limiter._storage = MemoryStorage()
    limiter._limiter = FixedWindowRateLimiter(limiter._storage)

    app = make_app(session_factory)
    client = TestClient(app)

    # RATE_LIMIT_LOGIN defaults to "5/minute" — exhaust the limit
    limit_count = int(RATE_LIMIT_LOGIN.split("/")[0])

    for i in range(limit_count):
        r = client.post("/auth/login", json={"usuario": "x", "senha": "y"})
        assert r.status_code in (200, 401), f"Request {i+1} expected 200/401, got {r.status_code}"

    # The next request must be rate-limited
    r = client.post("/auth/login", json={"usuario": "x", "senha": "y"})
    assert r.status_code == 429
