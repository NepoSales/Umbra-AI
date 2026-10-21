# Importar todos os models aqui garante que o create_all conheça cada tabela
from app.models.user import User

__all__ = ["User"]
