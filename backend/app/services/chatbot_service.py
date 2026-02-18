import ast
import json
import re
from datetime import datetime, timedelta

from app.models.barbeiro import Barbeiro
from app.models.conversa import Conversa
from app.models.servico import Servico
from app.schemas.agendamento import AgendamentoCreate
from app.services.agenda_service import gerar_horarios_disponiveis
from app.services.agendamento_service import criar_agendamento
from app.services.nlp_service import extrair_intencao


def _normalizar_texto(texto: str) -> str:
    return " ".join(texto.lower().strip().split())


def _eh_resposta_positiva(mensagem: str) -> bool:
    msg = _normalizar_texto(mensagem)
    return msg in {"sim", "s", "ok", "claro", "quero", "pode", "pode sim"} or "sim" in msg


def _eh_resposta_negativa(mensagem: str) -> bool:
    msg = _normalizar_texto(mensagem)
    return msg in {"nao", "não", "n", "agora nao", "agora não"}


def _quer_ver_horarios(mensagem: str) -> bool:
    msg = _normalizar_texto(mensagem)
    return (
        "horario" in msg
        or "horário" in msg
        or "mostrar" in msg
        or "mostra" in msg
        or _eh_resposta_positiva(msg)
    )


def _sem_preferencia_profissional(mensagem: str) -> bool:
    msg = _normalizar_texto(mensagem)
    return (
        "sem preferencia" in msg
        or "sem preferência" in msg
        or "qualquer" in msg
        or msg in {"nao", "não", "tanto faz", "nenhum"}
    )


def _carregar_contexto(conversa: Conversa) -> dict:
    contexto = conversa.contexto or {}
    if isinstance(contexto, dict):
        return contexto
    if isinstance(contexto, str):
        try:
            return json.loads(contexto)
        except Exception:
            try:
                return ast.literal_eval(contexto)
            except Exception:
                return {}
    return {}


def _salvar_estado(db, conversa: Conversa, estado: str, contexto: dict | None = None):
    conversa.estado = estado
    conversa.contexto = contexto if contexto is not None else None
    db.commit()


def _listar_servicos(db) -> list[Servico]:
    return db.query(Servico).order_by(Servico.id.asc()).all()


def _listar_barbeiros(db) -> list[Barbeiro]:
    return db.query(Barbeiro).order_by(Barbeiro.id.asc()).all()


def _encontrar_servico(db, mensagem: str):
    servicos = _listar_servicos(db)
    msg = _normalizar_texto(mensagem)

    for servico in servicos:
        if _normalizar_texto(servico.nome) == msg:
            return servico

    for servico in servicos:
        if _normalizar_texto(servico.nome) in msg:
            return servico

    tokens_msg = set(re.findall(r"\w+", msg))
    melhor = None
    maior_score = 0

    for servico in servicos:
        tokens_servico = set(re.findall(r"\w+", _normalizar_texto(servico.nome)))
        score = len(tokens_msg.intersection(tokens_servico))
        if score > maior_score:
            maior_score = score
            melhor = servico

    if melhor and maior_score > 0:
        return melhor
    return None


def _encontrar_barbeiro(db, mensagem: str):
    barbeiros = _listar_barbeiros(db)
    msg = _normalizar_texto(mensagem)

    for barbeiro in barbeiros:
        nome = _normalizar_texto(barbeiro.nome)
        if nome == msg or nome in msg:
            return barbeiro

    return None


def _mensagem_lista_servicos(db) -> str:
    servicos = _listar_servicos(db)
    if not servicos:
        return "Ainda não temos serviços cadastrados."

    nomes = [s.nome for s in servicos]
    return "Temos estes serviços: " + ", ".join(nomes) + ". Qual você quer?"


def _mensagem_lista_horarios(horarios: list[str]) -> str:
    if not horarios:
        return "Não encontrei horários disponíveis para amanhã."

    sugestoes = ", ".join(horarios[:5])
    return f"Tenho estes horários para amanhã: {sugestoes}. Pode escolher um horário ou digitar 'escolhe' que eu seleciono o primeiro disponível."


def _confirmar_agendamento(db, telefone: str, contexto: dict) -> str:
    data = datetime.fromisoformat(contexto["data"])
    horario_escolhido = contexto["horario_escolhido"]

    data_hora_inicio = datetime.combine(
        data.date(),
        datetime.strptime(horario_escolhido, "%H:%M").time(),
    )

    dados_agendamento = AgendamentoCreate(
        telefone=telefone,
        nome_cliente="Cliente WhatsApp",
        barbeiro_id=contexto["barbeiro_id"],
        servico_id=contexto["servico_id"],
        data_hora_inicio=data_hora_inicio,
    )

    try:
        criar_agendamento(db=db, dados=dados_agendamento)
        return f"Agendamento confirmado para amanhã às {horario_escolhido}."
    except Exception:
        return "Esse horário acabou de ficar indisponível. Digite 'mostrar horários' para eu te mostrar novas opções."


def responder_mensagem(db, telefone, mensagem):
    conversa = db.query(Conversa).filter(Conversa.telefone == telefone).first()

    if not conversa:
        conversa = Conversa(telefone=telefone, estado="inicio")
        db.add(conversa)
        db.commit()
        db.refresh(conversa)

    msg = _normalizar_texto(mensagem)
    contexto = _carregar_contexto(conversa)

    servico_direto = _encontrar_servico(db, msg)

    if conversa.estado == "inicio":
        if _eh_resposta_positiva(msg):
            _salvar_estado(db, conversa, "aguardando_servico", {})
            return _mensagem_lista_servicos(db)

        if servico_direto:
            _salvar_estado(
                db,
                conversa,
                "aguardando_barbeiro",
                {"servico_id": servico_direto.id, "servico_nome": servico_direto.nome},
            )
            return "Perfeito. Tem preferência de profissional?"

        _salvar_estado(db, conversa, "aguardando_interesse", {})
        return "Olá! Quer ver nossos serviços?"

    if conversa.estado == "aguardando_interesse":
        if _eh_resposta_positiva(msg):
            _salvar_estado(db, conversa, "aguardando_servico", {})
            return _mensagem_lista_servicos(db)

        if servico_direto:
            _salvar_estado(
                db,
                conversa,
                "aguardando_barbeiro",
                {"servico_id": servico_direto.id, "servico_nome": servico_direto.nome},
            )
            return "Perfeito. Tem preferência de profissional?"

        return "Quando quiser agendar, me diga 'sim' que eu te mostro os serviços."

    if conversa.estado == "aguardando_servico":
        servico = servico_direto
        if not servico:
            return _mensagem_lista_servicos(db)

        _salvar_estado(
            db,
            conversa,
            "aguardando_barbeiro",
            {"servico_id": servico.id, "servico_nome": servico.nome},
        )
        return "Ótima escolha. Tem preferência de profissional?"

    if conversa.estado == "aguardando_barbeiro":
        barbeiro = None
        if _sem_preferencia_profissional(msg):
            barbeiros = _listar_barbeiros(db)
            if not barbeiros:
                _salvar_estado(db, conversa, "inicio", None)
                return "Ainda não temos profissionais cadastrados para concluir o agendamento."
            barbeiro = barbeiros[0]
        else:
            barbeiro = _encontrar_barbeiro(db, msg)
            if not barbeiro:
                nomes = [b.nome for b in _listar_barbeiros(db)]
                if not nomes:
                    _salvar_estado(db, conversa, "inicio", None)
                    return "Ainda não temos profissionais cadastrados para concluir o agendamento."
                return "Não encontrei esse profissional. Temos: " + ", ".join(nomes) + "."

        novo_contexto = {
            **contexto,
            "barbeiro_id": barbeiro.id,
            "barbeiro_nome": barbeiro.nome,
            "data": (datetime.now() + timedelta(days=1)).isoformat(),
        }
        _salvar_estado(db, conversa, "aguardando_mostrar_horarios", novo_contexto)
        return f"Perfeito, vou seguir com {barbeiro.nome}. Quer que eu mostre os horários de amanhã?"

    if conversa.estado == "aguardando_mostrar_horarios":
        if _eh_resposta_negativa(msg):
            _salvar_estado(db, conversa, "inicio", None)
            return "Sem problemas. Quando quiser, me chama para agendar."

        if not _quer_ver_horarios(msg):
            return "Se quiser continuar, me diga 'mostra horários'."

        data = datetime.fromisoformat(contexto["data"])
        horarios = gerar_horarios_disponiveis(
            db,
            contexto["barbeiro_id"],
            contexto["servico_id"],
            data,
        )
        novo_contexto = {**contexto, "horarios_sugeridos": horarios[:8]}
        _salvar_estado(db, conversa, "aguardando_horario", novo_contexto)
        return _mensagem_lista_horarios(novo_contexto["horarios_sugeridos"])

    if conversa.estado == "aguardando_horario":
        horarios_sugeridos = contexto.get("horarios_sugeridos", [])
        if not horarios_sugeridos:
            _salvar_estado(db, conversa, "inicio", None)
            return "Não encontrei horários neste momento. Vamos tentar novamente em instantes."

        if "escolhe" in msg or "escolha" in msg:
            horario_escolhido = horarios_sugeridos[0]
            novo_contexto = {**contexto, "horario_escolhido": horario_escolhido}
            _salvar_estado(db, conversa, "aguardando_confirmacao_agendamento", novo_contexto)
            return f"Escolhi {horario_escolhido}. Se quiser confirmar, digite 'agenda'."

        dados_nlp = extrair_intencao(msg)
        horario_escolhido = dados_nlp.get("hora")
        if horario_escolhido and horario_escolhido in horarios_sugeridos:
            novo_contexto = {**contexto, "horario_escolhido": horario_escolhido}
            _salvar_estado(db, conversa, "aguardando_confirmacao_agendamento", novo_contexto)
            return f"Perfeito, horário {horario_escolhido} selecionado. Digite 'agenda' para confirmar."

        sugestoes = ", ".join(horarios_sugeridos[:5])
        return f"Não entendi o horário. Escolha um destes: {sugestoes}. Ou digite 'escolhe'."

    if conversa.estado == "aguardando_confirmacao_agendamento":
        if "agenda" not in msg and "confirm" not in msg:
            return "Para finalizar, digite 'agenda'."

        resultado = _confirmar_agendamento(db, telefone, contexto)
        _salvar_estado(db, conversa, "inicio", None)
        return resultado

    _salvar_estado(db, conversa, "inicio", None)
    return "Vamos recomeçar. Quer ver nossos serviços?"
