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

Segredo da história (o jogador não sabe; revele uma pista por vez):
- O padre Elias toca o sino à meia-noite para chamar os mortos. Ele quer trazer de volta a filha, Lívia, enterrada na cripta.
- Pistas: na cripta, o caixão de Lívia está vazio e há velas recém-acesas; no altar da cripta, o diário do padre fala em "trazê-la de volta"; na capela, o sino tem ossos gravados com sangue.
- Para acabar com isso: destruir o sino ou deter o padre Elias.

Regras:
- Português do Brasil, segunda pessoa ("você").
- Tom sombrio, mas claro: diga exatamente o que acontece.
- No máximo 3 frases curtas.
- A cada turno acontece algo novo: uma pista, um inimigo ou um lugar novo. Nunca repita a cena anterior.
- Termine sempre mostrando algo concreto na cena: um objeto, uma passagem, uma pessoa ou uma criatura.
- Nunca sugira o que o jogador deve fazer.
- Nunca mencione dados, números ou regras.
- Nunca decida o que o jogador faz ou fala."""

OUTCOME_INSTRUCTIONS = {
    Outcome.FAIL: "Essa ação DÁ ERRADO. Mostre uma consequência concreta: você se fere, perde algo (a tocha, a arma) ou um inimigo aparece. Não descreva nenhum sucesso.",
    Outcome.SUCCESS: "Essa ação DÁ CERTO, por pouco. O jogador consegue o que queria e, se fizer sentido, encontra a próxima pista. Se for um combate, o inimigo cai.",
    Outcome.EPIC: "Essa ação DÁ CERTO de forma ÉPICA. O jogador consegue o que queria sem se ferir e encontra a próxima pista. Se for um combate, o inimigo é destruído.",
}

# Usada quando o jogador só pergunta: não tem dado, então nada dá certo nem errado
QUESTION_INSTRUCTION = "O jogador fez uma PERGUNTA. Responda dentro da história, com o que o personagem consegue ver ou lembrar agora. Nada de bom ou de ruim acontece, e não entregue o segredo."

# Repetido no fim de todo pedido: modelo pequeno presta mais atenção no final do prompt
REMINDER = "Responda em no máximo 3 frases e termine mostrando algo concreto na cena."

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
            outcome = Outcome(turn.outcome) if turn.outcome else None
            prompt = _turn_prompt(game, turn.number, turn.action, outcome)
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

def _turn_prompt(game: Game, number: int, action: str, outcome: Outcome | None) -> str:
    instruction = OUTCOME_INSTRUCTIONS[outcome] if outcome else QUESTION_INSTRUCTION
    return f"Ação do jogador: {action}\n\n{instruction}{_pacing(game, number)}\n\n{REMINDER}"

def turn_messages(game: Game, number: int, action: str, outcome: Outcome | None) -> list[dict]:
    prompt = _turn_prompt(game, number, action, outcome)
    return [_system_message(game), *_history(game), {"role": "user", "content": prompt}]

def stream(messages: list[dict]) -> Iterator[str]:
    try:
        yield from ollama.chat_stream(messages)
    except httpx.HTTPError as exc:
        raise NarratorUnavailableError("O narrador não está disponível agora, tente novamente") from exc
