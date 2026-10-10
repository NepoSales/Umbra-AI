from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Game, Turn, User
from app.services import narrator
from app.services.dice import outcome_for, roll_d20

MAX_TURNS = 12

def start_game(db: Session, user: User) -> Game:
    game = Game(user=user, max_turns=MAX_TURNS)
    game.turns.append(Turn(number=0, narration=narrator.narrate_opening(game)))
    db.add(game)
    db.commit()
    db.refresh(game)
    return game

def list_games(db: Session, user: User) -> list[Game]:
    return list(db.scalars(select(Game).where(Game.user_id == user.id).order_by(Game.id.desc())))

def get_game(db: Session, user: User, game_id: int) -> Game:
    game = db.get(Game, game_id)
    # Jogo de outro usuário responde igual a inexistente, pra não vazar quais ids existem
    if game is None or game.user_id != user.id:
        raise NotFoundError("Jogo não encontrado")
    return game

def play_turn(db: Session, user: User, game_id: int, action: str) -> tuple[Game, Turn]:
    game = get_game(db, user, game_id)
    if game.status == "finished":
        raise ConflictError("Essa aventura já terminou")

    number = len(game.turns)
    roll = roll_d20()
    outcome = outcome_for(roll)
    narration = narrator.narrate_turn(game, number, action, outcome)

    turn = Turn(number=number, action=action, roll=roll, outcome=outcome, narration=narration)
    game.turns.append(turn)
    if number >= game.max_turns:
        game.status = "finished"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Outra ação desse jogo foi processada ao mesmo tempo, tente de novo")
    db.refresh(turn)
    return game, turn
