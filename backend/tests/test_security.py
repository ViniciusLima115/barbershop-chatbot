import pytest
from app.security import hash_senha, verificar_senha


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
