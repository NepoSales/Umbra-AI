import json
import os
from collections.abc import Iterator

import httpx

OLLAMA_URL = os.getenv("UMBRA_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("UMBRA_OLLAMA_MODEL", "gemma3:1b")

# Um cliente só pro app inteiro: reaproveita a conexão e é seguro entre threads.
# O read é o tempo máximo entre dois pedaços; o primeiro demora mais em CPU.
_client = httpx.Client(base_url=OLLAMA_URL, timeout=httpx.Timeout(10, read=180))

def chat_stream(messages: list[dict]) -> Iterator[str]:
    """Devolve a resposta do modelo aos pedaços, conforme ela é gerada."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "keep_alive": "30m",  # mantém o modelo carregado entre turnos
        "options": {
            "num_ctx": 4096,  # cabe a aventura inteira (~3000 tokens em 12 turnos)
            "num_predict": 180,  # teto de segurança, caso o modelo ignore o limite de frases
            "temperature": 0.8,
        },
    }
    with _client.stream("POST", "/api/chat", json=payload) as res:
        res.raise_for_status()
        # O Ollama manda uma linha JSON por pedaço
        for line in res.iter_lines():
            if line and (chunk := json.loads(line)["message"]["content"]):
                yield chunk
