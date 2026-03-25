# Shim de compatibilidade — este módulo será removido na Tarefa 17 (cleanup).
# Todo código legado que importa `from app.models.barbearia import Barbearia`
# continuará funcionando enquanto apontar para o novo modelo Estabelecimento.
from app.models.estabelecimento import Estabelecimento as Barbearia

__all__ = ["Barbearia"]
