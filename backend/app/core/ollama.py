import os

import httpx

OLLAMA_URL = os.getenv("UMBRA_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("UMBRA_OLLAMA_MODEL", "gemma3:1b")

# Um cliente só pro app inteiro: reaproveita a conexão e é seguro entre threads.
# O read é longo porque em CPU uma narração pode levar dezenas de segundos.
_client = httpx.Client(base_url=OLLAMA_URL, timeout=httpx.Timeout(10, read=180))

def chat(messages: list[dict]) -> str:
    res = _client.post("/api/chat", json={
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "30m",  # mantém o modelo carregado entre turnos
        "options": {
            "num_ctx": 2048,  # contexto pequeno = menos memória e prompt mais rápido
            "num_predict": 180,  # teto de segurança, caso o modelo ignore o limite de frases
            "temperature": 0.8,
        },
    })
    res.raise_for_status()
    return res.json()["message"]["content"].strip()
