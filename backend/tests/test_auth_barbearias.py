from app.models.barbearia import Barbearia
import app.routes.auth as auth_module
from app.security import hash_senha, verificar_senha


def test_auth_admin_check_ok_e_invalido(client):
    ok = client.post("/auth/admin-check", json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA})
    assert ok.status_code == 200
    assert ok.json()["is_admin"] is True

    invalido = client.post("/auth/admin-check", json={"usuario": "x", "senha": "y"})
    assert invalido.status_code == 200
    assert invalido.json()["is_admin"] is False


def test_auth_login_admin_retorna_token(client):
    resp = client.post("/auth/login", json={"usuario": auth_module.ADMIN_USUARIO, "senha": auth_module.ADMIN_SENHA})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_auth_login_tenant_sucesso_e_senha_invalida(client, db_session):
    barbearia = Barbearia(
        nome="Barbearia Login",
        login="barbearia.login",
        senha=hash_senha("senha123"),
        plano="basico",
        endereco="Rua A",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    sucesso = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "senha123"})
    assert sucesso.status_code == 200
    body = sucesso.json()
    assert body["is_admin"] is False
    assert body["tenant_id"] == barbearia.id
    assert body["tenant_name"] == barbearia.nome
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    invalido = client.post("/auth/login", json={"usuario": "barbearia.login", "senha": "errada"})
    assert invalido.status_code == 401


def test_barbearias_exige_admin_e_bloqueia_tenant(client, make_tenant_headers):
    sem_auth = client.get("/barbearias/")
    assert sem_auth.status_code == 401

    tenant_auth = client.get("/barbearias/", headers=make_tenant_headers(tenant_id=1))
    assert tenant_auth.status_code == 403


def test_barbearias_crud_admin(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    criar = client.post(
        "/barbearias/",
        headers=admin_headers,
        json={
            "nome": "Barbearia Centro",
            "login": "barbearia.centro",
            "senha": "senha",
            "plano": "basico",
            "status_manual": "ativo",
            "vencimento_em": "2026-12-31",
            "trial_ativo": False,
            "trial_fim_em": None,
            "ultimo_acesso_em": None,
            "pagamento_recusado": False,
            "endereco": "Rua A",
        },
    )
    assert criar.status_code == 200
    created = criar.json()
    barbearia_id = created["id"]
    assert created["login"] == "barbearia.centro"

    listar = client.get("/barbearias/", headers=admin_headers)
    assert listar.status_code == 200
    assert any(item["id"] == barbearia_id for item in listar.json())

    atualizar = client.put(
        f"/barbearias/{barbearia_id}",
        headers=admin_headers,
        json={
            "nome": "Barbearia Centro Atualizada",
            "login": "barbearia.centro",
            "senha": "senha-nova",
            "plano": "premium",
            "status_manual": "ativo",
            "vencimento_em": "2027-01-31",
            "trial_ativo": False,
            "trial_fim_em": None,
            "ultimo_acesso_em": None,
            "pagamento_recusado": False,
            "endereco": "Rua B",
        },
    )
    assert atualizar.status_code == 200
    updated = atualizar.json()
    assert updated["nome"] == "Barbearia Centro Atualizada"
    assert updated["plano"] == "premium"

    remover = client.delete(f"/barbearias/{barbearia_id}", headers=admin_headers)
    assert remover.status_code == 204


def test_barbearias_valida_duplicidades(client, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    payload_base = {
        "nome": "Barbearia A",
        "login": "barbearia.a",
        "senha": "senha",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2026-12-31",
        "trial_ativo": False,
        "trial_fim_em": None,
        "ultimo_acesso_em": None,
        "pagamento_recusado": False,
        "endereco": "Rua A",
    }
    primeira = client.post("/barbearias/", headers=admin_headers, json=payload_base)
    assert primeira.status_code == 200

    duplicada_login = dict(payload_base)
    r_login = client.post("/barbearias/", headers=admin_headers, json=duplicada_login)
    assert r_login.status_code == 400

    sem_conflito = dict(payload_base)
    sem_conflito["login"] = "barbearia.b"
    r_ok = client.post("/barbearias/", headers=admin_headers, json=sem_conflito)
    assert r_ok.status_code == 200


def test_barbearias_crud_cria_com_senha_hasheada(client, db_session, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)

    payload = {
        "nome": "Teste Hash",
        "login": "teste.hash",
        "senha": "senha_plain",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2027-01-01",
        "trial_ativo": False,
        "pagamento_recusado": False,
        "endereco": "Rua B",
    }
    resp = client.post("/barbearias/", json=payload, headers=admin_headers)
    assert resp.status_code == 200

    criada = db_session.query(Barbearia).filter(Barbearia.login == "teste.hash").first()
    assert criada is not None
    assert criada.senha != "senha_plain"  # not plaintext
    assert verificar_senha("senha_plain", criada.senha)  # valid bcrypt hash


def test_barbearias_crud_atualiza_com_senha_hasheada(client, db_session, make_tenant_headers):
    admin_headers = make_tenant_headers(is_admin=True)
    barbearia = Barbearia(
        nome="Para Atualizar",
        login="para.atualizar",
        senha=hash_senha("senha_original"),
        plano="basico",
        endereco="Rua C",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    payload = {
        "nome": "Para Atualizar",
        "login": "para.atualizar",
        "senha": "senha_nova",
        "plano": "basico",
        "status_manual": "ativo",
        "vencimento_em": "2027-01-01",
        "trial_ativo": False,
        "pagamento_recusado": False,
        "endereco": "Rua C",
    }
    resp = client.put(f"/barbearias/{barbearia.id}", json=payload, headers=admin_headers)
    assert resp.status_code == 200

    db_session.refresh(barbearia)
    assert barbearia.senha != "senha_nova"
    assert verificar_senha("senha_nova", barbearia.senha)


def test_tenant_header_mismatch_retorna_403(client, dados_base, make_tenant_headers):
    token_tenant_correto = make_tenant_headers(dados_base["barbearia"].id)
    headers_mismatch = {
        **token_tenant_correto,
        "X-Barbearia-Id": str(dados_base["barbearia"].id + 999),
    }
    resp = client.get("/clientes/", headers=headers_mismatch)
    assert resp.status_code == 403
