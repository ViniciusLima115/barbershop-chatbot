from pydantic import BaseModel

class ChatbotMensagem(BaseModel):
    telefone: str
    mensagem: str