import random
from enum import StrEnum

class Outcome(StrEnum):
    FAIL = "falha"
    SUCCESS = "sucesso"
    EPIC = "epico"

def roll_d20() -> int:
    return random.randint(1, 20)

def outcome_for(roll: int) -> Outcome:
    if roll <= 9:
        return Outcome.FAIL
    if roll <= 15:
        return Outcome.SUCCESS
    return Outcome.EPIC
