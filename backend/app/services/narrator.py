import re
from collections.abc import Iterator

import httpx

from app.core import ollama
from app.core.exceptions import NarratorUnavailableError
from app.models import Game
from app.services.dice import Outcome

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
    """Recria cada pedido exatamente como foi enviado.

    Se o começo do prompt for idêntico ao do turno anterior, o Ollama reaproveita o que
    já processou e só lê a parte nova. Por isso o histórico vai inteiro, sem cortes:
    cortar turnos antigos mudaria o começo e jogaria esse cache fora.
    """
    messages = []
    for turn in game.turns:
        if turn.narration is None:
            continue
        if turn.number == 0:
            prompt = OPENING_PROMPT
        else:
            prompt = _turn_prompt(game, turn.number, turn.action, Outcome(turn.outcome))
        messages.append({"role": "user", "content": prompt})
        messages.append({"role": "assistant", "content": turn.narration})
    return messages

def _pacing(game: Game, number: int) -> str:
    left = game.max_turns - number
    if left == 0:
        return "\n\nEste é o ÚLTIMO turno: conclua a história de forma definitiva, com um desfecho coerente com o resultado."
    if left <= 2:
        return "\n\nA história está chegando ao fim: conduza para o clímax."
    return ""

def trim(text: str) -> str:
    """Corta frase pela metade quando o modelo bate no limite de tokens."""
    text = text.strip()
    if text.endswith((".", "!", "?", "…", '"')):
        return text
    match = re.search(r"^.*[.!?…]", text, flags=re.S)
    return match.group(0) if match else text

def opening_messages(game: Game) -> list[dict]:
    return [_system_message(game), {"role": "user", "content": OPENING_PROMPT}]

def _turn_prompt(game: Game, number: int, action: str, outcome: Outcome) -> str:
    return f"Ação do jogador: {action}\n\n{OUTCOME_INSTRUCTIONS[outcome]}{_pacing(game, number)}\n\n{REMINDER}"

def turn_messages(game: Game, number: int, action: str, outcome: Outcome) -> list[dict]:
    prompt = _turn_prompt(game, number, action, outcome)
    return [_system_message(game), *_history(game), {"role": "user", "content": prompt}]

def stream(messages: list[dict]) -> Iterator[str]:
    try:
        yield from ollama.chat_stream(messages)
    except httpx.HTTPError as exc:
        raise NarratorUnavailableError("O narrador não está disponível agora, tente novamente") from exc
