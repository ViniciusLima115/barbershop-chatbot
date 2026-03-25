import pytest
from app.models.estabelecimento import Estabelecimento
from app.security import hash_senha


@pytest.fixture
def tenant_com_senha(db_session):
    est = Estabelecimento(
        nome="Config Teste",
        login="config.teste",
        senha=hash_senha("senha123"),
        slug="config-teste",
        endereco="Rua A",
        plano="basico",
    )
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


@pytest.fixture
def headers_tenant(tenant_com_senha, make_tenant_headers):
    return make_tenant_headers(
        tenant_id=tenant_com_senha.id,
        include_tenant_header=False,
    )


def test_configuracoes_requer_autenticacao(client):
    resp = client.patch("/configuracoes/perfil", json={"nome": "Novo"})
    assert resp.status_code == 401


def test_admin_nao_acessa_configuracoes(client, make_tenant_headers):
    headers = make_tenant_headers(is_admin=True)
    resp = client.patch("/configuracoes/perfil", json={"nome": "Novo"}, headers=headers)
    assert resp.status_code == 403


def test_atualizar_perfil_sucesso(client, db_session, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/perfil",
        json={"nome": "Novo Nome", "endereco": "Rua B"},
        headers=headers_tenant,
    )
    assert resp.status_code == 200
    db_session.refresh(tenant_com_senha)
    assert tenant_com_senha.nome == "Novo Nome"
    assert tenant_com_senha.endereco == "Rua B"


def test_atualizar_perfil_slug_duplicado(client, db_session, tenant_com_senha, headers_tenant):
    # Criar outro estabelecimento com slug existente
    outro = Estabelecimento(nome="Outro", slug="slug-existente")
    db_session.add(outro)
    db_session.commit()

    resp = client.patch(
        "/configuracoes/perfil",
        json={"slug": "slug-existente"},
        headers=headers_tenant,
    )
    assert resp.status_code == 409


def test_trocar_senha_correto(client, db_session, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/senha",
        json={"senha_atual": "senha123", "nova_senha": "novaSenha456"},
        headers=headers_tenant,
    )
    assert resp.status_code == 200
    db_session.refresh(tenant_com_senha)
    from app.security import verificar_senha
    assert verificar_senha("novaSenha456", tenant_com_senha.senha)


def test_trocar_senha_atual_errada(client, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/senha",
        json={"senha_atual": "errada", "nova_senha": "novaSenha456"},
        headers=headers_tenant,
    )
    assert resp.status_code == 400


def test_trocar_senha_muito_curta(client, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/senha",
        json={"senha_atual": "senha123", "nova_senha": "curta"},
        headers=headers_tenant,
    )
    assert resp.status_code == 422


def test_atualizar_tema_sucesso(client, db_session, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/tema",
        json={"accent_color": "#ff0000", "bg_color": "#000000", "logo_url": "https://example.com/logo.png"},
        headers=headers_tenant,
    )
    assert resp.status_code == 200
    db_session.refresh(tenant_com_senha)
    assert tenant_com_senha.accent_color == "#ff0000"
    assert tenant_com_senha.bg_color == "#000000"
    assert tenant_com_senha.logo_url == "https://example.com/logo.png"


def test_atualizar_tema_cor_invalida(client, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/tema",
        json={"accent_color": "vermelho"},
        headers=headers_tenant,
    )
    assert resp.status_code == 422


def test_atualizar_tema_logo_url_invalida(client, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/tema",
        json={"logo_url": "http://insecure.com/logo.png"},
        headers=headers_tenant,
    )
    assert resp.status_code == 422


def test_atualizar_notificacoes_sucesso(client, db_session, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/notificacoes",
        json={"notif_ativo": False, "notif_horas_antes": 24},
        headers=headers_tenant,
    )
    assert resp.status_code == 200
    db_session.refresh(tenant_com_senha)
    assert tenant_com_senha.notif_ativo is False
    assert tenant_com_senha.notif_horas_antes == 24


def test_atualizar_notificacoes_horas_invalidas(client, tenant_com_senha, headers_tenant):
    resp = client.patch(
        "/configuracoes/notificacoes",
        json={"notif_horas_antes": 3},
        headers=headers_tenant,
    )
    assert resp.status_code == 422


def test_me_retorna_campos_de_tema(client, db_session, tenant_com_senha, headers_tenant):
    tenant_com_senha.accent_color = "#aabbcc"
    db_session.commit()

    resp = client.get("/auth/me", headers=headers_tenant)
    assert resp.status_code == 200
    body = resp.json()
    assert body["accent_color"] == "#aabbcc"
    assert "bg_color" in body
    assert "notif_ativo" in body
    assert "notif_horas_antes" in body
