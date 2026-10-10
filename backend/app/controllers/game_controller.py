from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.controllers.dependencies import get_current_user
from app.core.database import get_db
from app.models import User
from app.services import game_service
from app.views.game import ActionIn, GameOut, GameSummary, TurnResult

router = APIRouter(prefix="/games", tags=["games"])

# Rotas com "def" normal: o FastAPI roda cada uma numa thread separada,
# então um jogador esperando a IA não trava a API pros outros.

@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def start(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return game_service.start_game(db, user)

@router.get("", response_model=list[GameSummary])
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return game_service.list_games(db, user)

@router.get("/{game_id}", response_model=GameOut)
def read(game_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return game_service.get_game(db, user, game_id)

@router.post("/{game_id}/actions", response_model=TurnResult)
def act(game_id: int, data: ActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game, turn = game_service.play_turn(db, user, game_id, data.action)
    return TurnResult(game_status=game.status, turns_left=game.max_turns - turn.number, turn=turn)
