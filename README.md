# Umbra-AI
Uma IA que atua como mestre de RPG no estilo dark fantasy em campanhas individuais 

## Rodando tudo com Docker

```bash
docker compose up -d --build
```

Abra http://localhost:8501 pra jogar (a API fica em http://localhost:8000/docs). Na primeira vez o compose baixa o modelo `gemma3:1b` (~800 MB), então demora um pouco até o backend subir: dá pra acompanhar com `docker compose logs -f ollama-pull`.

O banco e o modelo ficam em volumes do Docker, então sobrevivem a um `docker compose down` (só somem com `down -v`).

## Rodando sem Docker (desenvolvimento)

O narrador usa um modelo local via [Ollama](https://ollama.com). Instale o Ollama na máquina e baixe o modelo com `ollama pull gemma3:1b`.

### Backend

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

### Frontend

Feito em [Streamlit](https://streamlit.io). Com o backend rodando:

```bash
cd frontend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py   # abre em http://localhost:8501
```

Variável de ambiente opcional:
- `UMBRA_API_URL`: endereço do backend, padrão `http://localhost:8000`
