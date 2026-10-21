# Umbra-AI
Uma IA que atua como mestre de RPG no estilo dark fantasy em campanhas individuais 

## IA (Ollama)

O narrador roda num modelo local via [Ollama](https://ollama.com). Pra subir em container:

```bash
docker compose up -d
docker compose exec ollama ollama pull gemma3:1b
```

## Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload   # docs interativas em http://localhost:8000/docs
.venv/bin/pytest                          # testes
```

Variáveis de ambiente (opcionais em dev):
- `UMBRA_SECRET_KEY`: chave de assinatura do JWT (**obrigatório trocar em produção**)
- `UMBRA_DATABASE_URL`: padrão `sqlite:///./umbra.db`
- `UMBRA_OLLAMA_URL`: padrão `http://localhost:11434`
- `UMBRA_OLLAMA_MODEL`: padrão `gemma3:1b`
