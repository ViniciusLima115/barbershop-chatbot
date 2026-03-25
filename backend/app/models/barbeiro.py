# Shim de compatibilidade — este módulo será removido na Tarefa 17 (cleanup).
# Todo código legado que importa `from app.models.barbeiro import Barbeiro`
# continuará funcionando enquanto apontar para o novo modelo Profissional.
from app.models.profissional import Profissional as Barbeiro

__all__ = ["Barbeiro"]
