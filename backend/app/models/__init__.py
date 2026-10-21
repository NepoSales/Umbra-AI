# Importar todos os models aqui garante que o create_all conheça cada tabela
from app.models.game import Game, Turn
from app.models.user import User

__all__ = ["Game", "Turn", "User"]
