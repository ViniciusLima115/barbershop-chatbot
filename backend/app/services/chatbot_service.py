from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.servico import Servico

from datetime import datetime
from app.services.agendamento_service import criar_agendamento
from app.schemas.agendamento import AgendamentoCreate


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


def _listar_servicos(db: Session) -> list[Servico]:
    return db.query(Servico).order_by(Servico.id.asc()).all()


def _mensagem_menu(nome_cliente: str) -> str:
    return (
        f"Olá, {nome_cliente}! 👋\n"
        "1️⃣ Ver serviços\n"
        "2️⃣ Agendar horário\n"
        "3️⃣ Falar com atendente"
    )


def _mensagem_servicos(db: Session) -> str:
    servicos = _listar_servicos(db)
    if not servicos:
        return "Ainda não temos serviços cadastrados."

    linhas = ["Aqui estão nossos serviços:"]
    for idx, servico in enumerate(servicos, start=1):
        linhas.append(f"{idx}. {servico.nome} - {servico.duracao_minutos} min - R$ {servico.preco:.2f}")
    return "\n".join(linhas)


def _buscar_ou_criar_cliente(db: Session, telefone: str) -> Cliente:
    cliente = db.query(Cliente).filter(Cliente.telefone == telefone).first()
    if cliente:
        return cliente

    cliente = Cliente(
        telefone=telefone,
        nome="Vinicius",
        etapa_atual="inicio",
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def _salvar_etapa(db: Session, cliente: Cliente, etapa: str):
    cliente.etapa_atual = etapa
    db.commit()


def responder_mensagem(db: Session, telefone, mensagem):
    msg = _normalizar_texto(mensagem)
    telefone = _normalizar_telefone(telefone)
    cliente = _buscar_ou_criar_cliente(db, telefone)

    print("========== DEBUG ==========")
    print("TELEFONE:", telefone)
    print("ETAPA ATUAL:", cliente.etapa_atual)
    print("MENSAGEM NORMALIZADA:", msg)
    print("===========================")

    if _eh_saudacao(msg):
        _salvar_etapa(db, cliente, "menu")
        return _mensagem_menu(cliente.nome)

    if cliente.etapa_atual == "menu" and msg.startswith("1"):
        _salvar_etapa(db, cliente, "vendo_servicos")
        return _mensagem_servicos(db)

    if cliente.etapa_atual == "menu" and msg.startswith("2"):
        _salvar_etapa(db, cliente, "escolhendo_data")
        return "Perfeito. Qual data você deseja agendar? (formato: DD/MM/AAAA)"

    if cliente.etapa_atual == "menu" and msg.startswith("3"):
        _salvar_etapa(db, cliente, "falando_com_atendente")
        return "Certo. Vou te direcionar para um atendente."

    if cliente.etapa_atual == "menu":
        return "Escolha uma opção do menu:\n1️⃣ Ver serviços\n2️⃣ Agendar horário\n3️⃣ Falar com atendente"

    if cliente.etapa_atual == "escolhendo_data":
        try:
            data = datetime.strptime(mensagem, "%d/%m/%Y")
        except ValueError:
            return "Data inválida. Use o formato DD/MM/AAAA."

        # Exemplo simples: usando serviço 1 e barbeiro 1 fixos para teste
        try:
            agendamento = criar_agendamento(
                db,
                AgendamentoCreate(
                    telefone=cliente.telefone,
                    nome_cliente=cliente.nome,
                    barbeiro_id=1,
                    servico_id=1,
                    data_hora_inicio=datetime(
                        data.year, data.month, data.day, 14, 0
                    ),
                    status="confirmado",
                ),
            )
        except Exception as e:
            return f"Erro ao criar agendamento: {str(e)}"

        _salvar_etapa(db, cliente, "menu")
        return (
            f"Agendamento confirmado para "
            f"{agendamento.data_hora_inicio.strftime('%d/%m/%Y %H:%M')} ✅"
        )

    return _mensagem_menu(cliente.nome)
