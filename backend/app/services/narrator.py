import re

import httpx

from app.core import ollama
from app.core.exceptions import NarratorUnavailableError
from app.models import Game
from app.services.dice import Outcome

# Quantos turnos anteriores a IA vê. Pouco contexto = resposta mais rápida em CPU.
HISTORY_TURNS = 3

# O system prompt fica idêntico durante a partida inteira: assim o Ollama
# reaproveita o processamento dele de um turno pro outro.
SYSTEM_PROMPT = """Você é o Mestre de um RPG de dark fantasy para um único jogador.

Ambientação: {name} chega a Vel'Mora, uma vila isolada nas Terras Cinzentas onde os mortos deixaram de descansar há sete noites. O sino da capela toca sozinho à meia-noite, e no alto da colina a cripta da família Aldren está aberta. A missão de {name}: descobrir o que despertou os mortos e dar fim a isso.

Regras:
- Português do Brasil, segunda pessoa ("você").
- Tom sombrio e opressivo.
- Textos CURTOS: no máximo 5 frases.
- Nunca mencione dados, números ou regras.
- Nunca decida o que o jogador faz ou fala."""

OUTCOME_INSTRUCTIONS = {
    Outcome.FAIL: "Narre como essa ação DÁ ERRADO: o jogador falha e sofre uma consequência ruim (ferimento, perda ou um perigo maior). Não descreva nenhum sucesso.",
    Outcome.SUCCESS: "Narre como essa ação DÁ CERTO, por pouco, com muita tensão. O jogador vence: se for um combate, o inimigo cai.",
    Outcome.EPIC: "Narre como essa ação DÁ CERTO de forma ÉPICA e grandiosa. O jogador vence sem sofrer dano: se for um combate, o inimigo é destruído.",
}

# Repetido no fim de todo pedido: modelo pequeno presta mais atenção no final do prompt
REMINDER = "Responda em no máximo 5 frases."

OPENING_PROMPT = f"Comece a aventura: narre a chegada à vila e apresente a primeira cena. {REMINDER}"

def _system_message(game: Game) -> dict:
    return {"role": "system", "content": SYSTEM_PROMPT.format(name=game.user.username)}

def _history(game: Game) -> list[dict]:
    messages = []
    for turn in game.turns[-HISTORY_TURNS:]:
        if turn.action:
            messages.append({"role": "user", "content": f"Ação do jogador: {turn.action}"})
        messages.append({"role": "assistant", "content": turn.narration})
    return messages

def _pacing(game: Game, number: int) -> str:
    left = game.max_turns - number
    if left == 0:
        return "\n\nEste é o ÚLTIMO turno: conclua a história de forma definitiva, com um desfecho coerente com o resultado."
    if left <= 2:
        return "\n\nA história está chegando ao fim: conduza para o clímax."
    return ""

def _trim(text: str) -> str:
    """Corta frase pela metade quando o modelo bate no limite de tokens."""
    if text.endswith((".", "!", "?", "…", '"')):
        return text
    match = re.search(r"^.*[.!?…]", text, flags=re.S)
    return match.group(0) if match else text

def _generate(messages: list[dict]) -> str:
    try:
        return _trim(ollama.chat(messages))
    except httpx.HTTPError as exc:
        raise NarratorUnavailableError("O narrador não está disponível agora, tente novamente") from exc

def narrate_opening(game: Game) -> str:
    return _generate([_system_message(game), {"role": "user", "content": OPENING_PROMPT}])

def narrate_turn(game: Game, number: int, action: str, outcome: Outcome) -> str:
    prompt = f"Ação do jogador: {action}\n\n{OUTCOME_INSTRUCTIONS[outcome]}{_pacing(game, number)}\n\n{REMINDER}"
    return _generate([_system_message(game), *_history(game), {"role": "user", "content": prompt}])
