import json

import httpx
import pytest

from app.core import ollama
from app.services import dice

NARRATION = ["As brumas ", "de Vel'Mora ", "se fecham ao seu redor."]

@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch):
    """Troca a IA por uma resposta fixa em pedaços e guarda as mensagens enviadas."""
    calls = []
    def fake_stream(messages):
        calls.append(messages)
        yield from NARRATION
    monkeypatch.setattr(ollama, "chat_stream", fake_stream)
    return calls

def parse_sse(res) -> list[tuple[str, dict]]:
    events = []
    for block in res.text.strip().split("\n\n"):
        name, data = block.split("\n")
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events

def start_game(client, auth) -> int:
    return parse_sse(client.post("/games", headers=auth))[0][1]["game_id"]

def act(client, auth, game_id, action="Avanço"):
    return client.post(f"/games/{game_id}/actions", headers=auth, json={"action": action})

@pytest.mark.parametrize("roll, expected", [
    (1, "falha"), (9, "falha"), (10, "sucesso"), (15, "sucesso"), (16, "epico"), (20, "epico"),
])
def test_outcome_ranges(roll, expected):
    assert dice.outcome_for(roll) == expected

def test_start_game_streams_opening(client, auth):
    res = client.post("/games", headers=auth)
    assert res.status_code == 201
    assert res.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(res)
    assert [name for name, _ in events] == ["start", "chunk", "chunk", "chunk", "done"]
    assert events[0][1]["roll"] is None
    assert events[-1][1]["narration"] == "".join(NARRATION)

    game = client.get(f"/games/{events[0][1]['game_id']}", headers=auth).json()
    assert game["turns"][0]["narration"] == "".join(NARRATION)

def test_play_turn(client, auth, monkeypatch, fake_ollama):
    monkeypatch.setattr(dice.random, "randint", lambda a, b: 17)
    game_id = start_game(client, auth)

    events = parse_sse(act(client, auth, game_id, "Ataco o carniçal"))
    start, done = events[0][1], events[-1][1]
    assert start["roll"] == 17 and start["outcome"] == "epico"
    assert done["turns_left"] == 11 and done["game_status"] == "active"
    # A IA recebe a ação e a instrução do resultado
    assert "ÉPICA" in fake_ollama[-1][-1]["content"]

def test_game_ends_after_max_turns(client, auth, fake_ollama):
    game_id = start_game(client, auth)
    for _ in range(12):
        res = act(client, auth, game_id)
    assert parse_sse(res)[-1][1]["game_status"] == "finished"
    assert "ÚLTIMO turno" in fake_ollama[-1][-1]["content"]
    assert act(client, auth, game_id).status_code == 409

def test_cannot_see_other_users_game(client, auth):
    game_id = start_game(client, auth)
    client.post("/users", json={"username": "kael", "email": "kael@umbra.com", "password": "senha-forte"})
    token = client.post("/auth/login", data={"username": "kael", "password": "senha-forte"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/games/{game_id}", headers=other).status_code == 404
    assert act(client, other, game_id).status_code == 404

def test_narrator_offline_on_opening(client, auth, monkeypatch):
    def offline(messages):
        raise httpx.ConnectError("sem ollama")
        yield
    monkeypatch.setattr(ollama, "chat_stream", offline)

    events = parse_sse(client.post("/games", headers=auth))
    assert events[-1][0] == "error"
    # Jogo sem abertura não fica pra trás
    assert client.get("/games", headers=auth).json() == []

def test_narrator_offline_on_turn_saves_nothing(client, auth, monkeypatch):
    game_id = start_game(client, auth)
    def offline(messages):
        raise httpx.ReadTimeout("demorou")
        yield
    monkeypatch.setattr(ollama, "chat_stream", offline)

    assert parse_sse(act(client, auth, game_id))[-1][0] == "error"
    assert len(client.get(f"/games/{game_id}", headers=auth).json()["turns"]) == 1

def test_each_prompt_extends_the_previous_one(client, auth, fake_ollama):
    """Garante o reaproveitamento do cache do Ollama: o pedido novo começa igual ao anterior."""
    game_id = start_game(client, auth)
    for i in range(4):
        act(client, auth, game_id, f"ação {i}")

    for before, after in zip(fake_ollama, fake_ollama[1:]):
        assert after[:len(before)] == before
