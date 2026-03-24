import pytest
from app.security import hash_senha, verificar_senha, create_access_token, decode_access_token, TokenClaims


def test_hash_senha_retorna_bcrypt():
    h = hash_senha("minha-senha")
    assert h.startswith("$2b$")


def test_verificar_senha_correta():
    h = hash_senha("minha-senha")
    assert verificar_senha("minha-senha", h) is True


def test_verificar_senha_errada():
    h = hash_senha("minha-senha")
    assert verificar_senha("senha-errada", h) is False


def test_hashes_diferentes_para_mesma_senha():
    h1 = hash_senha("abc")
    h2 = hash_senha("abc")
    assert h1 != h2  # salt diferente a cada chamada


def test_verificar_senha_plaintext_correto():
    """Fallback: aceita plaintext ainda não migrado."""
    assert verificar_senha("abc", "abc") is True


def test_verificar_senha_plaintext_errado():
    """Fallback: rejeita plaintext errado."""
    assert verificar_senha("abc", "xyz") is False


def test_create_and_decode_token_tenant():
    token = create_access_token(sub="user1", tenant_id=42, is_admin=False)
    claims = decode_access_token(token)
    assert claims.sub == "user1"
    assert claims.tenant_id == 42
    assert claims.is_admin is False
    assert claims.jti is not None  # new field


def test_create_and_decode_token_admin():
    token = create_access_token(sub="admin", tenant_id=None, is_admin=True)
    claims = decode_access_token(token)
    assert claims.is_admin is True
    assert claims.tenant_id is None


def test_token_expirado_levanta_erro():
    token = create_access_token(sub="user", tenant_id=1, is_admin=False, expires_minutes=-1)
    with pytest.raises(ValueError, match="[Ee]xpirado|[Ee]xpired"):
        decode_access_token(token)


def test_token_adulterado_levanta_erro():
    token = create_access_token(sub="user", tenant_id=1, is_admin=False)
    partes = token.split(".")
    token_adulterado = partes[0] + ".ADULTERADO." + partes[2]
    with pytest.raises(ValueError):
        decode_access_token(token_adulterado)
