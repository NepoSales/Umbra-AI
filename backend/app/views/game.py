from pydantic import BaseModel, ConfigDict, Field

class ActionIn(BaseModel):
    action: str = Field(min_length=1, max_length=300)

class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    action: str | None
    roll: int | None
    outcome: str | None
    narration: str | None

class GameSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    max_turns: int

class GameOut(GameSummary):
    turns: list[TurnOut]
