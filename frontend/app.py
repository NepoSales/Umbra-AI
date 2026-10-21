"""Front do Umbra em Streamlit: só conversa com a API do backend."""

import json
import os
from collections.abc import Iterator

import httpx
import streamlit as st

API_URL = os.environ.get("UMBRA_API_URL", "http://localhost:8000")

ROLL_LABEL = {"falha": "🩸 Falha", "sucesso": "⚔️ Sucesso", "epico": "✨ Épico"}
PLAYER, MASTER = "🗡️", "💀"

st.set_page_config(page_title="Umbra", page_icon="💀")
state = st.session_state


class ApiError(Exception):
    pass


def _detail(res: httpx.Response) -> str:
    try:
        detail = res.json()["detail"]
    except (ValueError, KeyError):
        return "O mestre não respondeu. Tente de novo."
    # Erro de validação (422) vem como lista
    return detail if isinstance(detail, str) else ". ".join(d["msg"] for d in detail)


def _check(res: httpx.Response) -> None:
    if res.status_code == 401 and "token" in state:
        del state["token"]
        st.rerun()
    if res.is_error:
        res.read()
        raise ApiError(_detail(res))


def _headers() -> dict:
    return {"Authorization": f"Bearer {state.token}"} if "token" in state else {}


def api(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        res = httpx.request(method, API_URL + path, headers=_headers(), timeout=10, **kwargs)
    except httpx.HTTPError:
        raise ApiError("Não consegui falar com o servidor. O backend está rodando?")
    _check(res)
    return res


def sse_events(res: httpx.Response) -> Iterator[tuple[str, dict]]:
    """Lê a resposta SSE do backend: start → chunk (vários) → done, ou error."""
    event = None
    for line in res.iter_lines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            yield event, json.loads(line[6:])


def chunks(events: Iterator[tuple[str, dict]]) -> Iterator[str]:
    for event, data in events:
        if event == "chunk":
            yield data["text"]
        elif event == "error":
            raise ApiError(data["detail"])


def show_turn(action: str | None, roll: int | None, outcome: str | None) -> None:
    if action:
        with st.chat_message("user", avatar=PLAYER):
            st.markdown(f"*{action}*")
            if roll:  # pergunta ao Mestre não rola dado
                st.caption(f"d20: **{roll}** · {ROLL_LABEL[outcome]}")


def play(path: str, body: dict | None = None, resuming: bool = False) -> None:
    """Manda a ação (ou começa o jogo) e mostra a narração chegando aos pedaços."""
    try:
        with httpx.stream("POST", API_URL + path, json=body, headers=_headers(), timeout=None) as res:
            _check(res)
            events = sse_events(res)
            _, start = next(events)
            state.game_id = start["game_id"]
            if not resuming:  # ao retomar, a ação pendente já está na tela
                show_turn(start["action"], start["roll"], start["outcome"])
            with st.chat_message("assistant", avatar=MASTER):
                st.write_stream(chunks(events))
    except httpx.HTTPError:
        state.error = "A conexão com o mestre caiu no meio da narração."
    except ApiError as exc:
        state.error = str(exc)
    # Recarrega a partida do servidor, que tem o texto final já salvo
    st.rerun()


def auth_screen() -> None:
    st.markdown("*Os mortos de Vel'Mora não descansam. Alguém precisa descer até a cripta.*")
    login_tab, register_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab, st.form("login"):
        username = st.text_input("Nome ou email")
        password = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            login(username, password)

    with register_tab, st.form("register"):
        new_user = st.text_input("Nome do herói")
        email = st.text_input("Email")
        new_password = st.text_input("Senha", type="password", help="Mínimo de 8 caracteres")
        if st.form_submit_button("Criar conta", type="primary"):
            try:
                api("POST", "/users", json={"username": new_user, "email": email, "password": new_password})
            except ApiError as exc:
                st.error(exc)
            else:
                login(new_user, new_password)


def login(username: str, password: str) -> None:
    try:
        res = api("POST", "/auth/login", data={"username": username, "password": password})
    except ApiError as exc:
        st.error(exc)
        return
    state.token = res.json()["access_token"]
    st.rerun()


def sidebar() -> None:
    with st.sidebar:
        if st.button("Nova aventura", type="primary", width="stretch"):
            state.new_game = True
            state.pop("game_id", None)

        st.subheader("Suas aventuras")
        try:
            games = api("GET", "/games").json()
        except ApiError as exc:
            st.error(exc)
            games = []
        if not games:
            st.caption("Nenhuma aventura ainda. A vila espera.")
        for g in games:
            mark = "🕯️" if g["status"] == "active" else "⚰️"
            if st.button(f"{mark} Aventura #{g['id']}", key=f"game-{g['id']}", width="stretch"):
                state.game_id = g["id"]

        st.divider()
        if st.button("Sair", width="stretch"):
            state.clear()
            st.rerun()


def game_screen(game: dict) -> None:
    played = sum(1 for t in game["turns"] if t["number"] > 0 and t["narration"] is not None)
    st.caption(f"🕯️ Turnos restantes: {game['max_turns'] - played} de {game['max_turns']}")

    for turn in game["turns"]:
        show_turn(turn["action"], turn["roll"], turn["outcome"])
        if turn["narration"] is not None:
            with st.chat_message("assistant", avatar=MASTER):
                st.markdown(turn["narration"])

    last = game["turns"][-1] if game["turns"] else None
    if game["status"] == "finished":
        st.subheader("Fim.")
    elif last and last["narration"] is None:
        if last["number"] == 0:
            st.warning("Essa aventura se perdeu nas trevas antes de começar. Comece outra.")
        elif st.button("Continuar narração", help="O dado já foi lançado: a mesma ação e o mesmo resultado valem"):
            play(f"/games/{game['id']}/actions", {"action": last["action"]}, resuming=True)
    elif action := st.chat_input("O que você faz?", max_chars=300):
        play(f"/games/{game['id']}/actions", {"action": action})


st.title("Umbra")

if "token" not in state:
    auth_screen()
    st.stop()

sidebar()

if error := state.pop("error", None):
    st.error(error)

if state.pop("new_game", False):
    play("/games")
elif "game_id" in state:
    try:
        game_screen(api("GET", f"/games/{state.game_id}").json())
    except ApiError as exc:
        st.error(exc)
else:
    st.markdown("*Escolha uma aventura ao lado ou comece uma nova.*")
