from sqlalchemy.orm import Session
import logging

from app.models.agendamento import Agendamento
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.servico import Servico
from app.services.agenda_service import gerar_horarios_disponiveis

from datetime import datetime, timedelta
from app.services.agendamento_service import (
    criar_agendamento,
    atualizar_status_agendamento,
    remarcar_agendamento,
)
from app.schemas.agendamento import AgendamentoCreate
from app.services.notificacao_inapp_service import task_notificacao_novo_agendamento


PERIODOS_VALIDOS = {
    "1": "manha",
    "2": "tarde",
    "3": "noite",
    "manha": "manha",
    "manhã": "manha",
    "tarde": "tarde",
    "noite": "noite",
}

PERIODO_LABEL = {
    "manha": "manhã",
    "tarde": "tarde",
    "noite": "noite",
}

PARTICULAS_NOME = {"da", "de", "do", "das", "dos", "e"}
logger = logging.getLogger(__name__)


def _normalizar_texto(texto: str) -> str:
    return " ".join(texto.lower().strip().split())


def _normalizar_telefone(telefone: str) -> str:
    telefone = telefone.split("@")[0]
    telefone = telefone.replace("+", "").strip()

    if not telefone.startswith("55"):
        telefone = "55" + telefone

    return telefone


def _eh_saudacao(mensagem: str) -> bool:
    msg = _normalizar_texto(mensagem)
    return msg in {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"}


def _normalizar_nome(nome: str) -> str:
    partes = " ".join(nome.strip().split()).split(" ")
    normalizadas = []

    for i, parte in enumerate(partes):
        base = parte.lower()
        if i > 0 and base in PARTICULAS_NOME:
            normalizadas.append(base)
        else:
            normalizadas.append(base.capitalize())

    return " ".join(normalizadas)


def _listar_servicos(db: Session, tenant_id: int) -> list[Servico]:
    return (
        db.query(Servico)
        .filter(Servico.barbearia_id == tenant_id)
        .order_by(Servico.id.asc())
        .all()
    )


def _obter_barbeiro_padrao(db: Session, tenant_id: int) -> Barbeiro | None:
    return (
        db.query(Barbeiro)
        .filter(Barbeiro.barbershop_id == tenant_id)
        .order_by(Barbeiro.id.asc())
        .first()
    )


def _mensagem_menu(nome_cliente: str) -> str:
    return (
        f"Olá, {nome_cliente}. Sou a assistente da barbearia.\n"
        "Como posso te ajudar hoje?\n"
        "1️⃣ Agendar horário\n"
        "2️⃣ Ver serviços e preços\n"
        "3️⃣ Remarcar ou cancelar\n"
        "4️⃣ Falar com atendente\n\n"
        "Responda com o número da opção desejada."
    )


def _mensagem_servicos(db: Session, tenant_id: int) -> str:
    servicos = _listar_servicos(db, tenant_id)
    if not servicos:
        return "Ainda não temos serviços cadastrados."

    linhas = ["Aqui estão nossos serviços:"]
    for idx, servico in enumerate(servicos, start=1):
        linhas.append(f"{idx}. {servico.nome} - {servico.duracao_minutos} min - R$ {servico.preco:.2f}")
    return "\n".join(linhas)


def _mensagem_servicos_com_instrucao(db: Session, tenant_id: int) -> str:
    base = _mensagem_servicos(db, tenant_id)
    if base == "Ainda não temos serviços cadastrados.":
        return base
    return (
        f"{base}\n\n"
        "Para agendar, responda com o número do serviço.\n"
        "Para voltar ao menu, digite 0."
    )


def _agendamentos_futuros_cliente(db: Session, cliente_id: int, tenant_id: int) -> list[Agendamento]:
    return (
        db.query(Agendamento)
        .filter(
            Agendamento.cliente_id == cliente_id,
            Agendamento.barbearia_id == tenant_id,
            Agendamento.status.in_(["pendente", "confirmado"]),
            Agendamento.data_hora_inicio >= datetime.now(),
        )
        .order_by(Agendamento.data_hora_inicio.asc())
        .all()
    )


def _mensagem_periodos() -> str:
    return (
        "Escolha um período:\n"
        "1️⃣ Manhã\n"
        "2️⃣ Tarde\n"
        "3️⃣ Noite"
    )


def _normalizar_periodo(mensagem: str) -> str | None:
    return PERIODOS_VALIDOS.get(_normalizar_texto(mensagem))


def _datas_disponiveis_por_periodo(
    db: Session,
    barbeiro_id: int,
    servico_id: int,
    periodo: str,
    tenant_id: int,
    dias_busca: int = 14,
    limite_datas: int = 7,
) -> list[str]:
    datas = []
    hoje = datetime.now()

    for i in range(dias_busca):
        data = hoje + timedelta(days=i)
        horarios = gerar_horarios_disponiveis(
            db=db,
            barbeiro_id=barbeiro_id,
            servico_id=servico_id,
            data=data,
            periodo=periodo,
            tenant_id=tenant_id,
        )
        if horarios:
            datas.append(data.strftime("%d/%m/%Y"))
        if len(datas) >= limite_datas:
            break

    return datas


def _buscar_ou_criar_cliente(db: Session, telefone: str, tenant_id: int) -> Cliente:
    cliente = (
        db.query(Cliente)
        .filter(Cliente.telefone == telefone, Cliente.barbearia_id == tenant_id)
        .first()
    )
    if cliente:
        return cliente

    cliente = Cliente(
        telefone=telefone,
        nome="Cliente",
        etapa_atual="aguardando_nome",
        contexto=None,
        barbearia_id=tenant_id,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def _salvar_etapa(db: Session, cliente: Cliente, etapa: str):
    cliente.etapa_atual = etapa
    db.commit()


def _atualizar_contexto(db: Session, cliente: Cliente, **campos):
    contexto_atual = cliente.contexto if isinstance(cliente.contexto, dict) else {}
    novo_contexto = dict(contexto_atual)
    novo_contexto.update(campos)
    cliente.contexto = novo_contexto
    db.commit()


def responder_mensagem(db: Session, telefone, mensagem, tenant_id: int):
    msg = _normalizar_texto(mensagem)
    telefone = _normalizar_telefone(telefone)
    cliente = _buscar_ou_criar_cliente(db, telefone, tenant_id)
    barbeiro_padrao = _obter_barbeiro_padrao(db, tenant_id)

    if not barbeiro_padrao:
        return "Nao ha barbeiros cadastrados para esta barbearia."

    logger.debug(
        "Mensagem recebida. telefone=%s etapa=%s msg=%s",
        telefone,
        cliente.etapa_atual,
        msg,
    )

    if cliente.etapa_atual == "aguardando_nome":
        nome = mensagem.strip()
        if _eh_saudacao(msg) or len(nome) < 2 or nome.isdigit():
            return "Para te cadastrar, me diga seu nome."

        cliente.nome = _normalizar_nome(nome)
        cliente.contexto = None
        db.commit()
        _salvar_etapa(db, cliente, "menu")
        return _mensagem_menu(cliente.nome)

    if _eh_saudacao(msg):
        _salvar_etapa(db, cliente, "menu")
        return _mensagem_menu(cliente.nome)

    if cliente.etapa_atual == "menu" and msg.startswith("1"):
        cliente.contexto = None
        db.commit()
        _salvar_etapa(db, cliente, "escolhendo_servico")
        return _mensagem_servicos(db, tenant_id)

    if cliente.etapa_atual == "menu" and msg.startswith("2"):
        _salvar_etapa(db, cliente, "vendo_servicos")
        return _mensagem_servicos_com_instrucao(db, tenant_id)

    if cliente.etapa_atual == "menu" and msg.startswith("3"):
        agendamentos = _agendamentos_futuros_cliente(db, cliente.id, tenant_id)

        if not agendamentos:
            _salvar_etapa(db, cliente, "menu")
            return "Você não tem agendamentos futuros no momento.\n\n" + _mensagem_menu(cliente.nome)

        cliente.contexto = {
            "agendamento_ids": [ag.id for ag in agendamentos],
        }
        db.commit()

        _salvar_etapa(db, cliente, "escolhendo_agendamento_gestao")

        linhas = ["Seus próximos agendamentos:"]
        for i, ag in enumerate(agendamentos, start=1):
            linhas.append(
                f"{i}. {ag.data_hora_inicio.strftime('%d/%m/%Y %H:%M')} - {ag.servico.nome}"
            )
        linhas.append("\nDigite o número do agendamento para gerenciar.")
        return "\n".join(linhas)

    if cliente.etapa_atual == "menu" and msg.startswith("4"):
        _salvar_etapa(db, cliente, "falando_com_atendente")
        return "Certo. Vou te direcionar para um atendente."

    if cliente.etapa_atual == "menu":
        return _mensagem_menu(cliente.nome)

    if cliente.etapa_atual == "vendo_servicos":
        if msg in {"0", "menu", "voltar"}:
            _salvar_etapa(db, cliente, "menu")
            return _mensagem_menu(cliente.nome)

        servicos = _listar_servicos(db, tenant_id)
        try:
            indice = int(msg) - 1
            servico = servicos[indice]
        except (ValueError, IndexError):
            return "Escolha um número válido do serviço ou digite 0 para voltar ao menu."

        cliente.contexto = {"servico_id": servico.id}
        db.commit()
        _salvar_etapa(db, cliente, "escolhendo_periodo")
        return _mensagem_periodos()

    if cliente.etapa_atual == "escolhendo_agendamento_gestao":
        if not cliente.contexto or "agendamento_ids" not in cliente.contexto:
            _salvar_etapa(db, cliente, "menu")
            return "Sessão expirada. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

        try:
            indice = int(msg) - 1
            agendamento_id = cliente.contexto["agendamento_ids"][indice]
        except (ValueError, IndexError, TypeError, KeyError):
            return "Escolha um número válido da lista de agendamentos."

        _atualizar_contexto(db, cliente, agendamento_id_gestao=agendamento_id)
        _salvar_etapa(db, cliente, "escolhendo_acao_agendamento")

        return (
            "O que você deseja fazer com esse agendamento?\n"
            "1️⃣ Remarcar\n"
            "2️⃣ Cancelar\n"
            "3️⃣ Voltar ao menu"
        )

    if cliente.etapa_atual == "escolhendo_acao_agendamento":
        if msg.startswith("1"):
            if not cliente.contexto or "agendamento_id_gestao" not in cliente.contexto:
                _salvar_etapa(db, cliente, "menu")
                return "Sessão expirada. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

            agendamento = (
                db.query(Agendamento)
                .filter(
                    Agendamento.id == cliente.contexto["agendamento_id_gestao"],
                    Agendamento.cliente_id == cliente.id,
                    Agendamento.barbearia_id == tenant_id,
                )
                .first()
            )

            if not agendamento:
                cliente.contexto = None
                db.commit()
                _salvar_etapa(db, cliente, "menu")
                return "Não encontrei esse agendamento para remarcação.\n" + _mensagem_menu(cliente.nome)

            cliente.contexto = {
                "modo": "remarcacao",
                "agendamento_id_remarcacao": agendamento.id,
                "servico_id": agendamento.servico_id,
            }
            db.commit()
            _salvar_etapa(db, cliente, "escolhendo_periodo")
            return (
                "Perfeito. Vamos remarcar seu horário.\n"
                + _mensagem_periodos()
            )

        if msg.startswith("2"):
            if not cliente.contexto or "agendamento_id_gestao" not in cliente.contexto:
                _salvar_etapa(db, cliente, "menu")
                return "Sessão expirada. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

            try:
                atualizado = atualizar_status_agendamento(
                    db,
                    cliente.contexto["agendamento_id_gestao"],
                    "cancelado",
                    tenant_id=tenant_id,
                )
            except Exception as e:
                return f"Não consegui cancelar agora: {str(e)}"

            cliente.contexto = None
            db.commit()
            _salvar_etapa(db, cliente, "menu")
            return (
                f"Agendamento de {atualizado['data_hora_inicio'].strftime('%d/%m/%Y %H:%M')} "
                "cancelado com sucesso.\n\n"
                + _mensagem_menu(cliente.nome)
            )

        if msg.startswith("3"):
            cliente.contexto = None
            db.commit()
            _salvar_etapa(db, cliente, "menu")
            return _mensagem_menu(cliente.nome)

        return "Escolha uma opção válida:\n1️⃣ Remarcar\n2️⃣ Cancelar\n3️⃣ Voltar ao menu"

    if cliente.etapa_atual == "escolhendo_servico":
        servicos = _listar_servicos(db, tenant_id)

        try:
            indice = int(msg) - 1
            servico = servicos[indice]
        except (ValueError, IndexError):
            return "Escolha um número válido da lista de serviços."

        cliente.contexto = {"servico_id": servico.id}
        db.commit()

        _salvar_etapa(db, cliente, "escolhendo_periodo")
        return _mensagem_periodos()

    if cliente.etapa_atual == "escolhendo_periodo":
        periodo = _normalizar_periodo(msg)
        if not periodo:
            return "Escolha um período válido:\n1️⃣ Manhã\n2️⃣ Tarde\n3️⃣ Noite"

        if not cliente.contexto or "servico_id" not in cliente.contexto:
            _salvar_etapa(db, cliente, "menu")
            return "Ocorreu um erro na sessão. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

        datas = _datas_disponiveis_por_periodo(
            db=db,
            barbeiro_id=barbeiro_padrao.id,
            servico_id=cliente.contexto["servico_id"],
            periodo=periodo,
            tenant_id=tenant_id,
        )

        if not datas:
            return (
                f"Não encontrei datas disponíveis para {PERIODO_LABEL[periodo]} nos próximos dias.\n"
                "Escolha outro período:\n1️⃣ Manhã\n2️⃣ Tarde\n3️⃣ Noite"
            )

        _atualizar_contexto(
            db,
            cliente,
            periodo=periodo,
            datas_disponiveis=datas,
        )

        _salvar_etapa(db, cliente, "escolhendo_data_disponivel")

        linhas = [f"Datas disponíveis para {PERIODO_LABEL[periodo]}:"]
        for i, data in enumerate(datas, start=1):
            linhas.append(f"{i}. {data}")
        linhas.append("\nDigite o número da data desejada.")
        return "\n".join(linhas)

    if cliente.etapa_atual == "escolhendo_data_disponivel":
        try:
            indice = int(msg) - 1
            data_str = cliente.contexto["datas_disponiveis"][indice]
        except (ValueError, IndexError, TypeError, KeyError):
            return "Escolha um número válido da lista de datas."

        if not cliente.contexto or "servico_id" not in cliente.contexto or "periodo" not in cliente.contexto:
            _salvar_etapa(db, cliente, "menu")
            return "Ocorreu um erro na sessão. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

        data = datetime.strptime(data_str, "%d/%m/%Y")

        horarios = gerar_horarios_disponiveis(
            db=db,
            barbeiro_id=barbeiro_padrao.id,
            servico_id=cliente.contexto["servico_id"],
            data=data,
            periodo=cliente.contexto["periodo"],
            tenant_id=tenant_id,
        )

        if not horarios:
            return "Esse período ficou sem horários nessa data. Escolha outra data da lista."

        _atualizar_contexto(
            db,
            cliente,
            data=data_str,
            horarios_disponiveis=horarios,
        )

        _salvar_etapa(db, cliente, "escolhendo_horario")

        linhas = [f"Horários disponíveis ({PERIODO_LABEL[cliente.contexto['periodo']]}):"]
        for i, h in enumerate(horarios, start=1):
            linhas.append(f"{i}. {h}")

        linhas.append("\nDigite o número do horário desejado.")

        return "\n".join(linhas)

    if cliente.etapa_atual == "escolhendo_horario":

        if not cliente.contexto or "horarios_disponiveis" not in cliente.contexto:
            _salvar_etapa(db, cliente, "menu")
            return "Sessão expirada. Vamos começar novamente.\n" + _mensagem_menu(cliente.nome)

        horarios = cliente.contexto["horarios_disponiveis"]

        try:
            indice = int(msg) - 1
            horario_escolhido = horarios[indice]
        except (ValueError, IndexError):
            return "Escolha um número válido da lista."

        data_str = cliente.contexto["data"]
        data = datetime.strptime(data_str, "%d/%m/%Y")
        hora = datetime.strptime(horario_escolhido, "%H:%M").time()

        data_hora = datetime(
            data.year,
            data.month,
            data.day,
            hora.hour,
            hora.minute,
        )

        try:
            if cliente.contexto.get("modo") == "remarcacao":
                agendamento = remarcar_agendamento(
                    db,
                    cliente.contexto["agendamento_id_remarcacao"],
                    data_hora,
                    tenant_id=tenant_id,
                )
                mensagem_confirmacao = (
                    f"Remarcação confirmada para "
                    f"{agendamento['data_hora_inicio'].strftime('%d/%m/%Y %H:%M')} ✅"
                )
            else:
                agendamento = criar_agendamento(
                    db,
                    AgendamentoCreate(
                        telefone=cliente.telefone,
                        nome_cliente=cliente.nome,
                        barbeiro_id=barbeiro_padrao.id,
                        servico_id=cliente.contexto["servico_id"],
                        data_hora_inicio=data_hora,
                        status="confirmado",
                    ),
                    tenant_id=tenant_id,
                )
                task_notificacao_novo_agendamento(agendamento["id"])
                mensagem_confirmacao = (
                    f"Agendamento confirmado para "
                    f"{agendamento['data_hora_inicio'].strftime('%d/%m/%Y %H:%M')} ✅"
                )
        except Exception as e:
            return f"Erro ao confirmar horário: {str(e)}"

        cliente.contexto = None
        db.commit()

        _salvar_etapa(db, cliente, "menu")

        return mensagem_confirmacao

    return _mensagem_menu(cliente.nome)
