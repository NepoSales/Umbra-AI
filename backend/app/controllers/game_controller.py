import json
from collections.abc import Iterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.controllers.dependencies import get_current_user
from app.core.database import get_db
from app.core.exceptions import ServiceError
from app.models import User
from app.services import game_service
from app.services.game_service import PendingTurn
from app.views.game import ActionIn, GameOut, GameSummary

router = APIRouter(prefix="/games", tags=["games"])

# Rotas com "def" normal: o FastAPI roda cada uma numa thread separada,
# então um jogador esperando a IA não trava a API pros outros.

def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def _stream(pending: PendingTurn, status_code: int = status.HTTP_200_OK) -> StreamingResponse:
    """Narração em SSE. Eventos: start → chunk (vários) → done, ou error se algo falhar no meio."""
    def events() -> Iterator[str]:
        yield _event("start", {
            "game_id": pending.game_id, "number": pending.number,
            "roll": pending.roll, "outcome": pending.outcome,
        })
        try:
            for item in game_service.narrate(pending):
                if isinstance(item, str):
                    yield _event("chunk", {"text": item})
                else:
                    yield _event("done", asdict(item))
        except ServiceError as exc:
            # O status HTTP já foi enviado, então o erro vai como evento
            yield _event("error", {"detail": str(exc)})

    return StreamingResponse(events(), status_code=status_code, media_type="text/event-stream")

@router.post("", status_code=status.HTTP_201_CREATED)
def start(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Começa uma aventura e transmite a narração de abertura (SSE)."""
    return _stream(game_service.start_game(db, user), status.HTTP_201_CREATED)

@router.get("", response_model=list[GameSummary])
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return game_service.list_games(db, user)

@router.get("/{game_id}", response_model=GameOut)
def read(game_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return game_service.get_game(db, user, game_id)

@router.post("/{game_id}/actions")
def act(game_id: int, data: ActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rola o d20 e transmite a narração do resultado (SSE)."""
    return _stream(game_service.prepare_turn(db, user, game_id, data.action))
