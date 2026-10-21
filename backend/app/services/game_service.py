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
    turn_id: int
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
    opening = Turn(number=0)
    game.turns.append(opening)
    db.add(game)
    db.commit()
    return PendingTurn(
        game_id=game.id, turn_id=opening.id, number=0, max_turns=game.max_turns,
        action=None, roll=None, outcome=None, messages=narrator.opening_messages(game),
    )

def prepare_turn(db: Session, user: User, game_id: int, action: str) -> PendingTurn:
    """Rola o dado e salva o turno ANTES de narrar.

    Se o jogador desconectar no meio da narração, a próxima chamada reaproveita a mesma
    ação e o mesmo dado. Assim não dá pra rolar de novo nem trocar de ação depois de
    ver o resultado.
    """
    game = get_game(db, user, game_id)
    if game.status == "finished":
        raise ConflictError("Essa aventura já terminou")

    turn = game.turns[-1] if game.turns and game.turns[-1].narration is None else None
    if turn is not None and turn.number == 0:
        raise ConflictError("A abertura dessa aventura não foi narrada, comece um jogo novo")

    if turn is None:
        roll = roll_d20()
        turn = Turn(number=len(game.turns), action=action, roll=roll, outcome=outcome_for(roll))
        game.turns.append(turn)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConflictError("Outra ação desse jogo foi processada ao mesmo tempo, tente de novo")

    return PendingTurn(
        game_id=game.id, turn_id=turn.id, number=turn.number, max_turns=game.max_turns,
        action=turn.action, roll=turn.roll, outcome=Outcome(turn.outcome),
        messages=narrator.turn_messages(game, turn.number, turn.action, Outcome(turn.outcome)),
    )

def narrate(pending: PendingTurn) -> Iterator[str | NarrationDone]:
    """Repassa a narração aos pedaços e, no fim, salva o texto e devolve um NarrationDone.

    Usa uma sessão de banco própria porque roda depois que a requisição já respondeu.
    """
    parts = []
    try:
        for chunk in narrator.stream(pending.messages):
            parts.append(chunk)
            yield chunk
    except BaseException:  # BaseException inclui o cliente desconectando no meio
        # Num turno normal o dado continua salvo pra próxima tentativa.
        # Já sem abertura o jogo não faz sentido, então ele é apagado.
        if pending.number == 0:
            _discard_game(pending.game_id)
        raise

    narration = narrator.trim("".join(parts))
    finished = pending.number >= pending.max_turns
    with SessionLocal() as db:
        turn = db.get(Turn, pending.turn_id)
        turn.narration = narration
        if finished:
            turn.game.status = "finished"
        db.commit()

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
