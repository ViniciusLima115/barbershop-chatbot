"""
Testes para cenários não cobertos e bugs identificados durante análise.

Bugs identificados:
- Bug #1 (CORRIGIDO): chatbot_service._buscar_ou_criar_cliente criava cliente com
  etapa_atual="aguardando_nome!!!!!!" (com exclamações), mas o handler verifica
  == "aguardando_nome". Resultado: novos clientes nunca viam o formulário de cadastro.

- Bug #2 (EXPOSTO AQUI): buscar_cliente_publico usa getattr(cliente, "email", None)
  mas o model Cliente não possui campo `email`. Retorna sempre None.

Inconsistências:
- Endpoint /agendamentos/{token}/reagendar define status "reagendamento_solicitado"
  mas não remarca de fato. O endpoint real de remarcar é PUT /agendamentos/{token}/remarcar.
  Os nomes podem confundir (reagendar vs remarcar).

- Telefone normalizado no public_booking_service (remove DDI 55) mas não no
  agendamento_service (admin route). Clientes criados via admin com "558299..." não
  são encontrados via busca pública com "82999...".
"""
from datetime import datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.barbearia import Barbearia
from app.models.servico import Servico
from app.models.cliente import Cliente
from app.services.public_booking_service import buscar_cliente_publico, _normalizar_telefone_storage


# ---------------------------------------------------------------------------
# Fixtures de setup
# ---------------------------------------------------------------------------

@pytest.fixture
def barbearia_com_barbeiro_e_servico(db_session):
    """Cria estrutura básica: barbearia, barbeiro ativo e serviço."""
    barbearia = Barbearia(
        nome="Barbearia Cenarios",
        slug="cenarios",
        endereco="Rua Cenarios, 1",
    )
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro = Barbeiro(nome="Barbeiro Cenarios", barbershop_id=barbearia.id, ativo=True)
    servico = Servico(nome="Corte Cenarios", duracao_minutos=40, preco=50.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro, servico])
    db_session.commit()
    db_session.refresh(barbeiro)
    db_session.refresh(servico)

    return {"barbearia": barbearia, "barbeiro": barbeiro, "servico": servico}


def _criar_agendamento_publico(client, barbearia_id, barbeiro_id, servico_id, *, offset_days=2):
    """Helper: cria agendamento via rota pública e retorna o body."""
    data_hora = datetime.now() + timedelta(days=offset_days)
    payload = {
        "barbearia_id": barbearia_id,
        "cliente_nome": "Cliente Token",
        "cliente_telefone": "5582991111111",
        "cliente_email": "token@example.com",
        "barbeiro_id": barbeiro_id,
        "servico_id": servico_id,
        "data": data_hora.date().isoformat(),
        "hora_inicio": "10:00",
    }
    resp = client.post("/public/agendamentos", json=payload)
    return resp


# ---------------------------------------------------------------------------
# Testes: token inválido retorna 404
# ---------------------------------------------------------------------------

def test_token_invalido_retorna_404_ao_buscar_dados(client):
    resp = client.get("/agendamentos/token-que-nao-existe/dados")
    assert resp.status_code == 404


def test_token_invalido_retorna_404_ao_confirmar(client):
    resp = client.post("/agendamentos/token-invalido/confirmar")
    assert resp.status_code == 404


def test_token_invalido_retorna_404_ao_cancelar(client):
    resp = client.post("/agendamentos/token-invalido/cancelar")
    assert resp.status_code == 404


def test_token_invalido_retorna_404_ao_reagendar(client):
    resp = client.post("/agendamentos/token-invalido/reagendar")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Testes: operações em agendamento cancelado retornam 400
# ---------------------------------------------------------------------------

def test_confirmar_agendamento_cancelado_retorna_400(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    resp = _criar_agendamento_publico(
        client,
        fix["barbearia"].id,
        fix["barbeiro"].id,
        fix["servico"].id,
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["confirmation_token"]

    cancelar = client.post(f"/agendamentos/{token}/cancelar")
    assert cancelar.status_code == 200
    assert cancelar.json()["status"] == "cancelado"

    confirmar = client.post(f"/agendamentos/{token}/confirmar")
    assert confirmar.status_code == 400
    assert "cancelado" in confirmar.json()["detail"].lower()


def test_reagendar_agendamento_cancelado_retorna_400(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    resp = _criar_agendamento_publico(
        client,
        fix["barbearia"].id,
        fix["barbeiro"].id,
        fix["servico"].id,
    )
    assert resp.status_code == 200
    token = resp.json()["confirmation_token"]

    client.post(f"/agendamentos/{token}/cancelar")

    nova_data = datetime.now() + timedelta(days=5)
    remarcar = client.put(
        f"/agendamentos/{token}/remarcar",
        json={"data_hora_inicio": nova_data.replace(hour=11, minute=0, second=0, microsecond=0).isoformat()},
    )
    assert remarcar.status_code == 400
    assert "cancelado" in remarcar.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Testes: idempotência — confirmar já confirmado retorna 200 com mesmo status
# ---------------------------------------------------------------------------

def test_confirmar_ja_confirmado_e_idempotente(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    resp = _criar_agendamento_publico(
        client,
        fix["barbearia"].id,
        fix["barbeiro"].id,
        fix["servico"].id,
    )
    assert resp.status_code == 200
    token = resp.json()["confirmation_token"]

    primeira = client.post(f"/agendamentos/{token}/confirmar")
    assert primeira.status_code == 200
    assert primeira.json()["status"] == "confirmado"

    segunda = client.post(f"/agendamentos/{token}/confirmar")
    assert segunda.status_code == 200
    assert segunda.json()["status"] == "confirmado"


# ---------------------------------------------------------------------------
# Testes: PUT /agendamentos/{token}/remarcar (rota de remarcar de fato)
# ---------------------------------------------------------------------------

def test_remarcar_por_token_altera_data_hora(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    resp = _criar_agendamento_publico(
        client,
        fix["barbearia"].id,
        fix["barbeiro"].id,
        fix["servico"].id,
        offset_days=3,
    )
    assert resp.status_code == 200
    token = resp.json()["confirmation_token"]
    data_hora_original = resp.json()["data_hora_inicio"]

    nova_data_hora = (datetime.now() + timedelta(days=5)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    remarcar = client.put(
        f"/agendamentos/{token}/remarcar",
        json={"data_hora_inicio": nova_data_hora.isoformat()},
    )
    assert remarcar.status_code == 200
    body = remarcar.json()
    assert body["status"] == "confirmado"
    assert body["data_hora_inicio"] != data_hora_original


def test_remarcar_com_conflito_retorna_400(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico

    # Cria primeiro agendamento às 10:00
    data_base = datetime.now() + timedelta(days=4)
    payload1 = {
        "barbearia_id": fix["barbearia"].id,
        "cliente_nome": "Cliente Um",
        "cliente_telefone": "5582911111111",
        "barbeiro_id": fix["barbeiro"].id,
        "servico_id": fix["servico"].id,
        "data": data_base.date().isoformat(),
        "hora_inicio": "10:00",
    }
    r1 = client.post("/public/agendamentos", json=payload1)
    assert r1.status_code == 200

    # Cria segundo agendamento em horário diferente
    payload2 = {
        "barbearia_id": fix["barbearia"].id,
        "cliente_nome": "Cliente Dois",
        "cliente_telefone": "5582922222222",
        "barbeiro_id": fix["barbeiro"].id,
        "servico_id": fix["servico"].id,
        "data": data_base.date().isoformat(),
        "hora_inicio": "11:00",
    }
    r2 = client.post("/public/agendamentos", json=payload2)
    assert r2.status_code == 200
    token2 = r2.json()["confirmation_token"]

    # Tenta remarcar segundo para colidir com o primeiro
    conflito_hora = data_base.replace(hour=10, minute=0, second=0, microsecond=0)
    remarcar = client.put(
        f"/agendamentos/{token2}/remarcar",
        json={"data_hora_inicio": conflito_hora.isoformat()},
    )
    assert remarcar.status_code == 400
    assert "indisponível" in remarcar.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Testes: filtro por barbeiro_id em listar agendamentos
# ---------------------------------------------------------------------------

def test_listar_agendamentos_filtra_por_barbeiro_id(client, db_session, make_tenant_headers):
    barbearia = Barbearia(nome="Barbearia Filtro", endereco="Rua Filtro")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    barbeiro_a = Barbeiro(nome="Barbeiro A", barbershop_id=barbearia.id, ativo=True)
    barbeiro_b = Barbeiro(nome="Barbeiro B", barbershop_id=barbearia.id, ativo=True)
    servico = Servico(nome="Corte", duracao_minutos=40, preco=40.0, barbearia_id=barbearia.id)
    db_session.add_all([barbeiro_a, barbeiro_b, servico])
    db_session.commit()
    db_session.refresh(barbeiro_a)
    db_session.refresh(barbeiro_b)
    db_session.refresh(servico)

    headers = make_tenant_headers(barbearia.id)
    amanha = datetime.now() + timedelta(days=1)

    payload_a = {
        "telefone": "5582911111111",
        "nome_cliente": "Cliente A",
        "barbeiro_id": barbeiro_a.id,
        "servico_id": servico.id,
        "data_hora_inicio": amanha.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "status": "confirmado",
    }
    payload_b = {
        "telefone": "5582922222222",
        "nome_cliente": "Cliente B",
        "barbeiro_id": barbeiro_b.id,
        "servico_id": servico.id,
        "data_hora_inicio": amanha.replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
        "status": "confirmado",
    }
    assert client.post("/agendamentos/", json=payload_a, headers=headers).status_code == 200
    assert client.post("/agendamentos/", json=payload_b, headers=headers).status_code == 200

    resp = client.get(
        "/agendamentos/",
        params={"barbeiro_id": barbeiro_a.id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["barbeiro_nome"] == "Barbeiro A"


# ---------------------------------------------------------------------------
# Testes: normalização de telefone no agendamento público
# ---------------------------------------------------------------------------

def test_telefone_com_ddi_55_e_armazenado_sem_prefixo(client, db_session, barbearia_com_barbeiro_e_servico):
    """Telefone '5582991234567' deve ser armazenado como '82991234567' (sem DDI)."""
    fix = barbearia_com_barbeiro_e_servico
    data_hora = datetime.now() + timedelta(days=2)
    payload = {
        "barbearia_id": fix["barbearia"].id,
        "cliente_nome": "Cliente DDI",
        "cliente_telefone": "5582991234567",
        "barbeiro_id": fix["barbeiro"].id,
        "servico_id": fix["servico"].id,
        "data": data_hora.date().isoformat(),
        "hora_inicio": "10:00",
    }
    resp = client.post("/public/agendamentos", json=payload)
    assert resp.status_code == 200

    agendamento = (
        db_session.query(Agendamento)
        .filter(Agendamento.id == resp.json()["id"])
        .first()
    )
    assert agendamento.cliente_telefone == "82991234567"


def test_buscar_cliente_por_telefone_com_ddi(client, db_session, barbearia_com_barbeiro_e_servico):
    """Cliente criado com '5582991234567' deve ser encontrado pela busca pública."""
    fix = barbearia_com_barbeiro_e_servico
    data_hora = datetime.now() + timedelta(days=2)
    payload = {
        "barbearia_id": fix["barbearia"].id,
        "cliente_nome": "Cliente Busca DDI",
        "cliente_telefone": "5582991234567",
        "barbeiro_id": fix["barbeiro"].id,
        "servico_id": fix["servico"].id,
        "data": data_hora.date().isoformat(),
        "hora_inicio": "10:00",
    }
    client.post("/public/agendamentos", json=payload)

    # Busca com DDI completo
    resp = client.get(
        f"/public/{fix['barbearia'].id}/cliente",
        params={"telefone": "5582991234567"},
    )
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Cliente Busca DDI"

    # Busca sem DDI
    resp_sem_ddi = client.get(
        f"/public/{fix['barbearia'].id}/cliente",
        params={"telefone": "82991234567"},
    )
    assert resp_sem_ddi.status_code == 200
    assert resp_sem_ddi.json()["nome"] == "Cliente Busca DDI"


# ---------------------------------------------------------------------------
# Testes: agendamento no passado é rejeitado
# ---------------------------------------------------------------------------

def test_agendamento_publico_no_passado_retorna_400(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    ontem = datetime.now() - timedelta(days=1)
    payload = {
        "barbearia_id": fix["barbearia"].id,
        "cliente_nome": "Cliente Passado",
        "cliente_telefone": "5582991111111",
        "barbeiro_id": fix["barbeiro"].id,
        "servico_id": fix["servico"].id,
        "data": ontem.date().isoformat(),
        "hora_inicio": ontem.strftime("%H:%M"),
    }
    resp = client.post("/public/agendamentos", json=payload)
    assert resp.status_code == 400
    assert "passado" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Campo email no model Cliente
# ---------------------------------------------------------------------------

def test_buscar_cliente_publico_retorna_email(db_session, barbearia_com_barbeiro_e_servico):
    """
    Cliente possui campo email. buscar_cliente_publico retorna o email armazenado.
    """
    fix = barbearia_com_barbeiro_e_servico
    barbearia_id = fix["barbearia"].id

    cliente = Cliente(
        nome="Cliente Com Email",
        telefone="82991111111",
        email="cliente@example.com",
        barbearia_id=barbearia_id,
    )
    db_session.add(cliente)
    db_session.commit()

    resultado = buscar_cliente_publico(db_session, barbearia_id=barbearia_id, telefone="82991111111")
    assert resultado is not None
    assert resultado["nome"] == "Cliente Com Email"
    assert resultado["email"] == "cliente@example.com"


def test_buscar_cliente_publico_email_none_quando_nao_informado(db_session, barbearia_com_barbeiro_e_servico):
    """
    Cliente sem email retorna email=None.
    """
    fix = barbearia_com_barbeiro_e_servico
    barbearia_id = fix["barbearia"].id

    cliente = Cliente(
        nome="Cliente Sem Email",
        telefone="82992222222",
        barbearia_id=barbearia_id,
    )
    db_session.add(cliente)
    db_session.commit()

    resultado = buscar_cliente_publico(db_session, barbearia_id=barbearia_id, telefone="82992222222")
    assert resultado is not None
    assert resultado["email"] is None


# ---------------------------------------------------------------------------
# Testes: agendamento admin gera confirmation_token automaticamente
# ---------------------------------------------------------------------------

def test_agendamento_admin_gera_confirmation_token(client, db_session, dados_base, tenant_headers):
    inicio = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582911111111",
        "nome_cliente": "Cliente Token Admin",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "confirmado",
    }
    resp = client.post("/agendamentos/", json=payload, headers=tenant_headers)
    assert resp.status_code == 200

    agendamento_id = resp.json()["id"]
    agendamento = db_session.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    assert agendamento is not None
    assert agendamento.confirmation_token is not None
    assert len(agendamento.confirmation_token) == 36  # UUID4 padrão


def test_dados_por_token_retorna_agendamento_admin(client, db_session, dados_base, tenant_headers):
    """Token gerado por agendamento admin deve funcionar nas rotas públicas de token."""
    inicio = (datetime.now() + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0)
    payload = {
        "telefone": "5582911111111",
        "nome_cliente": "Cliente Token Admin",
        "barbeiro_id": dados_base["barbeiro"].id,
        "servico_id": dados_base["servico"].id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "pendente",
    }
    agendamento_criado = client.post("/agendamentos/", json=payload, headers=tenant_headers).json()
    agendamento_id = agendamento_criado["id"]

    agendamento = db_session.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    token = agendamento.confirmation_token

    dados = client.get(f"/agendamentos/{token}/dados")
    assert dados.status_code == 200
    assert dados.json()["status"] == "pendente"


# ---------------------------------------------------------------------------
# Testes: normalização de status inválido retorna 'pendente'
# ---------------------------------------------------------------------------

def test_status_invalido_normalizado_para_pendente(client, db_session, barbearia_com_barbeiro_e_servico):
    """Agendamento com status desconhecido deve ser serializado como 'pendente'."""
    fix = barbearia_com_barbeiro_e_servico
    data_hora = datetime.now() + timedelta(days=2)

    cliente = Cliente(nome="Cliente Status", telefone="82999999999", barbearia_id=fix["barbearia"].id)
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)

    # Insere diretamente com status desconhecido
    agendamento = Agendamento(
        cliente_id=cliente.id,
        barbeiro_id=fix["barbeiro"].id,
        servico_id=fix["servico"].id,
        barbearia_id=fix["barbearia"].id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        data=data_hora.date(),
        hora_inicio=data_hora.time(),
        data_hora_inicio=data_hora,
        data_hora_fim=data_hora + timedelta(minutes=40),
        status="status_desconhecido",
    )
    db_session.add(agendamento)
    db_session.commit()
    db_session.refresh(agendamento)

    token = agendamento.confirmation_token
    dados = client.get(f"/agendamentos/{token}/dados")
    assert dados.status_code == 200
    assert dados.json()["status"] == "pendente"


# ---------------------------------------------------------------------------
# Testes: lookup de barbearia inexistente retorna 404
# ---------------------------------------------------------------------------

def test_lookup_barbearia_inexistente_retorna_404(client):
    resp = client.get("/public/barbearia/slug-que-nao-existe")
    assert resp.status_code == 404


def test_lookup_barbearia_por_id_inexistente_retorna_404(client):
    resp = client.get("/public/barbearia-id/999999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Testes: barbeiro inativo não aparece na listagem pública
# ---------------------------------------------------------------------------

def test_barbeiro_inativo_nao_aparece_na_listagem_publica(client, db_session):
    barbearia = Barbearia(nome="Barbearia Ativo Inativo", slug="ativo-inativo", endereco="Rua X")
    db_session.add(barbearia)
    db_session.commit()
    db_session.refresh(barbearia)

    ativo = Barbeiro(nome="Ativo", barbershop_id=barbearia.id, ativo=True)
    inativo = Barbeiro(nome="Inativo", barbershop_id=barbearia.id, ativo=False)
    db_session.add_all([ativo, inativo])
    db_session.commit()

    resp = client.get("/public/barbeiros", params={"barbearia_id": barbearia.id})
    assert resp.status_code == 200
    nomes = [b["nome"] for b in resp.json()]
    assert "Ativo" in nomes
    assert "Inativo" not in nomes


# ---------------------------------------------------------------------------
# Testes: cliente não encontrado retorna 404
# ---------------------------------------------------------------------------

def test_buscar_cliente_inexistente_retorna_404(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    resp = client.get(
        f"/public/{fix['barbearia'].id}/cliente",
        params={"telefone": "0000000000"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Testes: tokens únicos por agendamento
# ---------------------------------------------------------------------------

def test_cada_agendamento_tem_token_unico(client, db_session, barbearia_com_barbeiro_e_servico):
    fix = barbearia_com_barbeiro_e_servico
    data_base = datetime.now() + timedelta(days=3)

    payloads = [
        {
            "barbearia_id": fix["barbearia"].id,
            "cliente_nome": f"Cliente {i}",
            "cliente_telefone": f"558299999{i:04d}",
            "barbeiro_id": fix["barbeiro"].id,
            "servico_id": fix["servico"].id,
            "data": data_base.date().isoformat(),
            "hora_inicio": f"{10 + i}:00",
        }
        for i in range(3)
    ]

    tokens = []
    for p in payloads:
        r = client.post("/public/agendamentos", json=p)
        assert r.status_code == 200
        tokens.append(r.json()["confirmation_token"])

    assert len(set(tokens)) == 3, "Cada agendamento deve ter um token único"
