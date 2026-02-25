def test_barbeiros_criar_e_listar(client, db_session):
    from app.models.barbearia import Barbearia

    premium = Barbearia(nome="Barbearia Premium", plano="premium")
    db_session.add(premium)
    db_session.commit()
    db_session.refresh(premium)
    db_headers = {"X-Barbearia-Id": str(premium.id)}

    criar = client.post("/barbeiros/", json={"nome": "Carlos"}, headers=db_headers)
    assert criar.status_code == 200
    assert criar.json()["nome"] == "Carlos"
    assert criar.json()["barbershop_id"] == premium.id

    listar = client.get("/barbeiros/", headers=db_headers)
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 1
    assert body[0]["nome"] == "Carlos"
    assert body[0]["barbershop_id"] == premium.id


def test_barbeiros_exige_header_tenant(client):
    criar = client.post("/barbeiros/", json={"nome": "Carlos"})
    assert criar.status_code == 400
    assert criar.json()["detail"] == "X-Barbearia-Id obrigatorio."


def test_barbeiros_basico_permite_um_e_bloqueia_mais_com_upgrade(client, db_session):
    from app.models.barbearia import Barbearia

    basico = Barbearia(nome="Barbearia Basica", plano="basico")
    db_session.add(basico)
    db_session.commit()

    criar_primeiro = client.post(
        "/barbeiros/",
        json={"nome": "Carlos"},
        headers={"X-Barbearia-Id": str(basico.id)},
    )
    assert criar_primeiro.status_code == 200

    criar_segundo = client.post(
        "/barbeiros/",
        json={"nome": "Andre"},
        headers={"X-Barbearia-Id": str(basico.id)},
    )
    assert criar_segundo.status_code == 403
    assert (
        criar_segundo.json()["detail"]
        == "Deseja adicionar mais barbeiros? Faca o upgrade para o plano premium."
    )


def test_barbeiros_premium_limite_edicao_e_exclusao(client, db_session):
    from app.models.barbearia import Barbearia

    premium = Barbearia(nome="Barbearia Premium", plano="premium")
    db_session.add(premium)
    db_session.commit()

    headers = {"X-Barbearia-Id": str(premium.id)}

    for nome in ("Carlos", "Andre", "Rafael"):
        criar = client.post("/barbeiros/", json={"nome": nome}, headers=headers)
        assert criar.status_code == 200

    excedente = client.post("/barbeiros/", json={"nome": "Quarto"}, headers=headers)
    assert excedente.status_code == 400
    assert excedente.json()["detail"] == "Limite de 3 barbeiros ativos atingido."

    listar = client.get("/barbeiros/", headers=headers)
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 3

    primeiro_id = body[0]["id"]

    atualizar = client.put(
        f"/barbeiros/{primeiro_id}",
        json={"nome": "Carlos Atualizado"},
        headers=headers,
    )
    assert atualizar.status_code == 200
    assert atualizar.json()["nome"] == "Carlos Atualizado"

    remover = client.delete(f"/barbeiros/{primeiro_id}", headers=headers)
    assert remover.status_code == 204


def test_barbeiro_nao_pode_ser_acessado_por_outra_barbearia(client, db_session):
    from app.models.barbearia import Barbearia

    premium_a = Barbearia(nome="Premium A", plano="premium")
    premium_b = Barbearia(nome="Premium B", plano="premium")
    db_session.add_all([premium_a, premium_b])
    db_session.commit()

    headers_a = {"X-Barbearia-Id": str(premium_a.id)}
    headers_b = {"X-Barbearia-Id": str(premium_b.id)}

    criar = client.post("/barbeiros/", json={"nome": "Vinicius"}, headers=headers_a)
    assert criar.status_code == 200
    barbeiro_id = criar.json()["id"]

    listar_b = client.get("/barbeiros/", headers=headers_b)
    assert listar_b.status_code == 200
    assert listar_b.json() == []

    atualizar_b = client.put(
        f"/barbeiros/{barbeiro_id}",
        json={"nome": "Nao Pode"},
        headers=headers_b,
    )
    assert atualizar_b.status_code == 404

    remover_b = client.delete(f"/barbeiros/{barbeiro_id}", headers=headers_b)
    assert remover_b.status_code == 404


def test_servicos_criar_e_listar(client, tenant_headers):
    criar = client.post(
        "/servicos/",
        json={"nome": "Barba", "duracao_minutos": 30, "preco": 25.0},
        headers=tenant_headers,
    )
    assert criar.status_code == 200
    assert criar.json()["nome"] == "Barba"

    listar = client.get("/servicos/", headers=tenant_headers)
    assert listar.status_code == 200
    body = listar.json()
    assert any(item["nome"] == "Barba" and item["duracao_minutos"] == 30 for item in body)


def test_clientes_criar_listar_e_duplicado(client, tenant_headers):
    criar = client.post(
        "/clientes/",
        json={"telefone": "5582980000000", "nome": "Cliente A"},
        headers=tenant_headers,
    )
    assert criar.status_code == 200
    assert criar.json()["telefone"] == "5582980000000"

    duplicado = client.post(
        "/clientes/",
        json={"telefone": "5582980000000", "nome": "Cliente B"},
        headers=tenant_headers,
    )
    assert duplicado.status_code == 400
    assert duplicado.json()["detail"] == "Telefone já cadastrado"

    listar = client.get("/clientes/", headers=tenant_headers)
    assert listar.status_code == 200
    body = listar.json()
    assert len(body) == 1
    assert body[0]["nome"] == "Cliente A"
