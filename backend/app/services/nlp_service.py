from datetime import datetime, timedelta


def extrair_intencao(mensagem: str):

    mensagem = mensagem.lower()

    resultado = {
        "servico": None,
        "data": None,
        "hora": None
    }

    # SERVIÇO
    if "corte" in mensagem and "barba" in mensagem:
        resultado["servico"] = "corte_barba"
    elif "corte" in mensagem:
        resultado["servico"] = "corte"
    elif "barba" in mensagem:
        resultado["servico"] = "barba"

    # DATA
    if "amanhã" in mensagem or "amanha" in mensagem:
        resultado["data"] = datetime.now() + timedelta(days=1)

    if "hoje" in mensagem:
        resultado["data"] = datetime.now()

    # HORA
    import re
    match = re.search(r"(\d{1,2}):?(\d{2})?", mensagem)

    if match:
        hora = match.group(1)
        minuto = match.group(2) or "00"
        resultado["hora"] = f"{hora.zfill(2)}:{minuto}"

    return resultado