import pytest

from app.core import ollama
from app.services import dice

@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch):
    """Troca a IA por uma resposta fixa e guarda as mensagens enviadas."""
    calls = []
    def fake_chat(messages):
        calls.append(messages)
        return "As brumas de Vel'Mora se fecham ao seu redor."
    monkeypatch.setattr(ollama, "chat", fake_chat)
    return calls

@pytest.mark.parametrize("roll, expected", [
    (1, "falha"), (9, "falha"), (10, "sucesso"), (15, "sucesso"), (16, "epico"), (20, "epico"),
])
def test_outcome_ranges(roll, expected):
    assert dice.outcome_for(roll) == expected

def test_start_game(client, auth):
    res = client.post("/games", headers=auth)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "active"
    assert body["turns"][0]["number"] == 0
    assert body["turns"][0]["roll"] is None

def test_play_turn(client, auth, monkeypatch, fake_ollama):
    monkeypatch.setattr(dice.random, "randint", lambda a, b: 17)
    game_id = client.post("/games", headers=auth).json()["id"]

    res = client.post(f"/games/{game_id}/actions", headers=auth, json={"action": "Ataco o carniçal"})
    assert res.status_code == 200
    body = res.json()
    assert body["turn"]["roll"] == 17
    assert body["turn"]["outcome"] == "epico"
    assert body["turns_left"] == 11
    # A IA recebe a ação e a instrução do resultado
    assert "ÉPICA" in fake_ollama[-1][-1]["content"]

def test_game_ends_after_max_turns(client, auth, fake_ollama):
    game_id = client.post("/games", headers=auth).json()["id"]
    for _ in range(12):
        res = client.post(f"/games/{game_id}/actions", headers=auth, json={"action": "Avanço"})
    assert res.json()["game_status"] == "finished"
    assert "ÚLTIMO turno" in fake_ollama[-1][-1]["content"]

    res = client.post(f"/games/{game_id}/actions", headers=auth, json={"action": "Mais uma"})
    assert res.status_code == 409

def test_cannot_see_other_users_game(client, auth):
    game_id = client.post("/games", headers=auth).json()["id"]
    client.post("/users", json={"username": "kael", "email": "kael@umbra.com", "password": "senha-forte"})
    token = client.post("/auth/login", data={"username": "kael", "password": "senha-forte"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/games/{game_id}", headers=other).status_code == 404
    assert client.post(f"/games/{game_id}/actions", headers=other, json={"action": "x"}).status_code == 404

def test_narrator_offline(client, auth, monkeypatch):
    import httpx
    def offline(messages):
        raise httpx.ConnectError("sem ollama")
    monkeypatch.setattr(ollama, "chat", offline)
    assert client.post("/games", headers=auth).status_code == 503

def test_history_is_limited(client, auth, fake_ollama):
    game_id = client.post("/games", headers=auth).json()["id"]
    for i in range(10):
        client.post(f"/games/{game_id}/actions", headers=auth, json={"action": f"ação {i}"})
    # system + até 3 turnos (abertura não tem ação) + ação atual
    assert len(fake_ollama[-1]) <= 1 + 3 * 2 + 1
