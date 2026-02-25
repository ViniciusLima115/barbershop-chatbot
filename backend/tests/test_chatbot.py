from datetime import datetime

from app.models.agendamento import Agendamento
from app.models.cliente import Cliente


def _msg(client, telefone, mensagem, headers):
    return client.post(
        "/chatbot/mensagem",
        json={"telefone": telefone, "mensagem": mensagem},
        headers=headers,
    )


def _iniciar_chat_novo_cliente(client, telefone, headers, nome="Teste"):
    r1 = _msg(client, telefone, "oi", headers)
    assert "Para te cadastrar, me diga seu nome." in r1.json()["resposta"]
    r2 = _msg(client, telefone, nome, headers)
    assert "Agendar horário" in r2.json()["resposta"]
    return r2


def _criar_agendamento(client, headers, barbeiro_id, servico_id, telefone, nome, inicio_iso):
    return client.post(
        "/agendamentos/",
        json={
            "telefone": telefone,
            "nome_cliente": nome,
            "barbeiro_id": barbeiro_id,
            "servico_id": servico_id,
            "data_hora_inicio": inicio_iso,
            "status": "confirmado",
        },
        headers=headers,
    )


def test_chatbot_fluxo_agendamento_completo(client, dados_base, tenant_headers):
    telefone = "5582911111111"

    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente Fluxo")

    r2 = _msg(client, telefone, "1", tenant_headers)
    assert r2.status_code == 200
    assert "Aqui estão nossos serviços" in r2.json()["resposta"]

    r3 = _msg(client, telefone, "1", tenant_headers)
    assert r3.status_code == 200
    assert "Escolha um período" in r3.json()["resposta"]

    r4 = _msg(client, telefone, "2", tenant_headers)
    assert r4.status_code == 200
    assert "Datas disponíveis para tarde" in r4.json()["resposta"]

    r5 = _msg(client, telefone, "1", tenant_headers)
    assert r5.status_code == 200
    assert "Horários disponíveis" in r5.json()["resposta"]

    r6 = _msg(client, telefone, "1", tenant_headers)
    assert r6.status_code == 200
    assert "confirmado para" in r6.json()["resposta"].lower()


def test_chatbot_ver_servicos_permite_seguir_para_periodo(client, dados_base, tenant_headers):
    telefone = "5582922222222"

    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente Servicos")
    r2 = _msg(client, telefone, "2", tenant_headers)
    assert "Para agendar, responda com o número do serviço" in r2.json()["resposta"]

    r3 = _msg(client, telefone, "1", tenant_headers)
    assert r3.status_code == 200
    assert "Escolha um período" in r3.json()["resposta"]


def test_chatbot_cancela_agendamento_existente(client, dados_base, tenant_headers):
    telefone = "5582933333333"
    inicio = dados_base["amanha"].replace(hour=16, minute=0, second=0, microsecond=0)
    created = _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        telefone,
        "Cliente Cancelamento",
        inicio.isoformat(),
    )
    assert created.status_code == 200

    _msg(client, telefone, "oi", tenant_headers)
    r2 = _msg(client, telefone, "3", tenant_headers)
    assert "Seus próximos agendamentos" in r2.json()["resposta"]

    r3 = _msg(client, telefone, "1", tenant_headers)
    assert "O que você deseja fazer" in r3.json()["resposta"]

    r4 = _msg(client, telefone, "2", tenant_headers)
    assert "cancelado com sucesso" in r4.json()["resposta"].lower()


def test_chatbot_remarca_agendamento_com_sucesso(client, dados_base, db_session, tenant_headers):
    telefone = "5582944444444"
    inicio_original = dados_base["amanha"].replace(hour=16, minute=0, second=0, microsecond=0)
    created = _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        telefone,
        "Cliente Remarcacao",
        inicio_original.isoformat(),
    )
    assert created.status_code == 200
    agendamento_id = created.json()["id"]

    _msg(client, telefone, "oi", tenant_headers)
    _msg(client, telefone, "3", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    r4 = _msg(client, telefone, "1", tenant_headers)
    assert "Vamos remarcar" in r4.json()["resposta"]

    _msg(client, telefone, "2", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    r7 = _msg(client, telefone, "1", tenant_headers)
    assert "remarcação confirmada para" in r7.json()["resposta"].lower()

    agendamento = db_session.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    assert agendamento is not None
    assert agendamento.data_hora_inicio != inicio_original
    assert agendamento.status == "confirmado"


def test_chatbot_remarcacao_com_conflito_apos_listar_horarios(client, dados_base, db_session, tenant_headers):
    telefone = "5582955555554"
    inicio_original = dados_base["amanha"].replace(hour=16, minute=0, second=0, microsecond=0)
    created = _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        telefone,
        "Cliente Conflito",
        inicio_original.isoformat(),
    )
    assert created.status_code == 200

    _msg(client, telefone, "oi", tenant_headers)
    _msg(client, telefone, "3", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "2", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)

    cliente = db_session.query(Cliente).filter(Cliente.telefone == telefone).first()
    assert cliente is not None
    assert isinstance(cliente.contexto, dict)
    data_str = cliente.contexto["data"]
    horario_str = cliente.contexto["horarios_disponiveis"][0]
    conflito_inicio = datetime.strptime(f"{data_str} {horario_str}", "%d/%m/%Y %H:%M")

    conflito = _criar_agendamento(
        client,
        tenant_headers,
        dados_base["barbeiro"].id,
        dados_base["servico"].id,
        "5582966666664",
        "Cliente Ocupando Slot",
        conflito_inicio.isoformat(),
    )
    assert conflito.status_code == 200

    r_final = _msg(client, telefone, "1", tenant_headers)
    assert "erro ao confirmar horário" in r_final.json()["resposta"].lower()
    assert "horário indisponível" in r_final.json()["resposta"].lower()


def test_chatbot_erro_data_invalida_na_lista(client, dados_base, tenant_headers):
    telefone = "5582971111111"
    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente Data")
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "2", tenant_headers)

    resp = _msg(client, telefone, "99", tenant_headers)
    assert "Escolha um número válido da lista de datas." in resp.json()["resposta"]


def test_chatbot_erro_servico_invalido(client, tenant_headers):
    telefone = "5582972222222"
    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente Servico")
    _msg(client, telefone, "1", tenant_headers)
    resp = _msg(client, telefone, "99", tenant_headers)

    assert "Escolha um número válido da lista de serviços." in resp.json()["resposta"]


def test_chatbot_erro_horario_invalido(client, dados_base, tenant_headers):
    telefone = "5582973333333"
    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente Horario")
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "2", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    resp = _msg(client, telefone, "99", tenant_headers)

    assert "Escolha um número válido da lista." in resp.json()["resposta"]


def test_chatbot_sessao_expirada(client, db_session, tenant_headers, dados_base):
    cliente = Cliente(
        nome="Sessao",
        telefone="5582974444444",
        etapa_atual="escolhendo_horario",
        contexto=None,
        barbearia_id=dados_base["barbearia"].id,
    )
    db_session.add(cliente)
    db_session.commit()

    resp = _msg(client, cliente.telefone, "1", tenant_headers)
    assert "Sessão expirada. Vamos começar novamente." in resp.json()["resposta"]


def test_chatbot_ausencia_de_horarios(client, monkeypatch, dados_base, tenant_headers):
    import app.services.chatbot_service as chatbot_service

    def sem_horarios(*args, **kwargs):
        return []

    monkeypatch.setattr(chatbot_service, "gerar_horarios_disponiveis", sem_horarios)

    telefone = "5582975555555"
    _iniciar_chat_novo_cliente(client, telefone, tenant_headers, "Cliente SemHorario")
    _msg(client, telefone, "1", tenant_headers)
    _msg(client, telefone, "1", tenant_headers)
    resp = _msg(client, telefone, "2", tenant_headers)

    assert "Não encontrei datas disponíveis para tarde nos próximos dias." in resp.json()["resposta"]


def test_chatbot_normaliza_nome_no_cadastro(client, db_session, tenant_headers, dados_base):
    telefone = "5582976666666"
    r1 = _msg(client, telefone, "oi", tenant_headers)
    assert "Para te cadastrar, me diga seu nome." in r1.json()["resposta"]

    r2 = _msg(client, telefone, "   joao   da   silva   ", tenant_headers)
    assert "Olá, Joao da Silva." in r2.json()["resposta"]

    cliente = (
        db_session.query(Cliente)
        .filter(
            Cliente.telefone == telefone,
            Cliente.barbearia_id == dados_base["barbearia"].id,
        )
        .first()
    )
    assert cliente is not None
    assert cliente.nome == "Joao da Silva"
