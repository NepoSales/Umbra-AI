from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Game, Turn, User
from app.services import narrator
from app.services.dice import Outcome, outcome_for, roll_d20

MAX_TURNS = 12

@dataclass
class PendingTurn:
    """Tudo que já foi decidido antes da IA começar a narrar."""
    game_id: int
    number: int
    max_turns: int
    action: str | None
    roll: int | None
    outcome: Outcome | None
    messages: list[dict]

@dataclass
class NarrationDone:
    number: int
    narration: str
    game_status: str
    turns_left: int

def list_games(db: Session, user: User) -> list[Game]:
    return list(db.scalars(select(Game).where(Game.user_id == user.id).order_by(Game.id.desc())))

def get_game(db: Session, user: User, game_id: int) -> Game:
    game = db.get(Game, game_id)
    # Jogo de outro usuário responde igual a inexistente, pra não vazar quais ids existem
    if game is None or game.user_id != user.id:
        raise NotFoundError("Jogo não encontrado")
    return game

def start_game(db: Session, user: User) -> PendingTurn:
    game = Game(user=user, max_turns=MAX_TURNS)
    db.add(game)
    db.commit()
    return PendingTurn(
        game_id=game.id, number=0, max_turns=game.max_turns,
        action=None, roll=None, outcome=None, messages=narrator.opening_messages(game),
    )

def prepare_turn(db: Session, user: User, game_id: int, action: str) -> PendingTurn:
    game = get_game(db, user, game_id)
    if game.status == "finished":
        raise ConflictError("Essa aventura já terminou")
    if not game.turns:
        raise ConflictError("A abertura dessa aventura não foi narrada, comece um jogo novo")

    number = len(game.turns)
    roll = roll_d20()
    outcome = outcome_for(roll)
    return PendingTurn(
        game_id=game.id, number=number, max_turns=game.max_turns,
        action=action, roll=roll, outcome=outcome,
        messages=narrator.turn_messages(game, number, action, outcome),
    )

def narrate(pending: PendingTurn) -> Iterator[str | NarrationDone]:
    """Repassa a narração aos pedaços e, no fim, salva o turno e devolve um NarrationDone.

    Usa uma sessão de banco própria porque roda depois que a requisição já respondeu.
    """
    parts = []
    try:
        for chunk in narrator.stream(pending.messages):
            parts.append(chunk)
            yield chunk
    except Exception:
        if pending.number == 0:
            _discard_game(pending.game_id)
        raise

    narration = narrator.trim("".join(parts))
    finished = pending.number >= pending.max_turns
    with SessionLocal() as db:
        game = db.get(Game, pending.game_id)
        game.turns.append(Turn(
            number=pending.number, action=pending.action, roll=pending.roll,
            outcome=pending.outcome, narration=narration,
        ))
        if finished:
            game.status = "finished"
        try:
            db.commit()
        except IntegrityError:
            raise ConflictError("Outra ação desse jogo foi processada ao mesmo tempo, tente de novo")

    yield NarrationDone(
        number=pending.number,
        narration=narration,
        game_status="finished" if finished else "active",
        turns_left=pending.max_turns - pending.number,
    )

def _discard_game(game_id: int) -> None:
    """Se a abertura falhar, o jogo fica sem sentido: melhor apagar."""
    with SessionLocal() as db:
        if game := db.get(Game, game_id):
            db.delete(game)
            db.commit()
