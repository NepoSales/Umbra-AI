// Front do Umbra: HTML + JS puro, servido pelo próprio backend (mesma origem).

const $ = (sel) => document.querySelector(sel);

const OUTCOME_LABEL = { falha: "Falha", sucesso: "Sucesso", epico: "Épico" };

let token = localStorage.getItem("umbra-token");
let game = null;          // partida aberta: { id, status, max_turns, turns }
let controller = null;    // permite cancelar a narração ao sair da tela

// ---------- API ----------

class ApiError extends Error {}

function errorText(body, fallback) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  // Erro de validação (422) vem como lista
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(". ");
  return fallback;
}

async function request(path, { method = "GET", json, form, signal } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = new URLSearchParams(form);
  }

  const res = await fetch(path, { method, headers, body, signal });
  if (res.status === 401 && token) {
    logout();
    throw new ApiError("Sua sessão expirou, entre de novo");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(errorText(data, "O mestre não respondeu. Tente de novo."));
  }
  return res;
}

const getJson = async (path) => (await request(path)).json();

// Lê a resposta SSE (start → chunk... → done | error) e chama o handler de cada evento
async function stream(path, json, handlers) {
  controller = new AbortController();
  const res = await request(path, { method: "POST", json, signal: controller.signal });
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      handlers[event]?.(JSON.parse(data));
    }
  }
}

// ---------- Telas ----------

function show(id) {
  for (const s of document.querySelectorAll(".screen")) s.hidden = s.id !== id;
  $("#logout").hidden = id === "auth";
}

function logout() {
  controller?.abort();
  token = null;
  localStorage.removeItem("umbra-token");
  show("auth");
}

// ---------- Entrar / criar conta ----------

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    for (const t of document.querySelectorAll(".tab")) t.classList.toggle("active", t === tab);
    $("#login-form").hidden = tab.dataset.tab !== "login";
    $("#register-form").hidden = tab.dataset.tab !== "register";
    $("#auth-error").textContent = "";
  });
}

async function login(username, password) {
  const res = await request("/auth/login", { method: "POST", form: { username, password } });
  token = (await res.json()).access_token;
  localStorage.setItem("umbra-token", token);
  openLobby();
}

async function submitAuth(event, action) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector("button");
  button.disabled = true;
  $("#auth-error").textContent = "";
  try {
    await action(Object.fromEntries(new FormData(form)));
    form.reset();
  } catch (err) {
    $("#auth-error").textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

$("#login-form").addEventListener("submit", (e) =>
  submitAuth(e, (data) => login(data.username, data.password)));

$("#register-form").addEventListener("submit", (e) =>
  submitAuth(e, async (data) => {
    await request("/users", { method: "POST", json: data });
    await login(data.username, data.password);
  }));

$("#logout").addEventListener("click", logout);

// ---------- Lista de aventuras ----------

async function openLobby() {
  controller?.abort();
  game = null;
  show("lobby");
  $("#lobby-error").textContent = "";
  try {
    const games = await getJson("/games");
    const list = $("#games");
    list.replaceChildren(...games.map((g) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      const name = document.createElement("span");
      const status = document.createElement("span");
      name.textContent = `Aventura #${g.id}`;
      status.className = `status ${g.status}`;
      status.textContent = g.status === "finished" ? "concluída" : "em andamento";
      btn.append(name, status);
      btn.addEventListener("click", () => openGame(g.id));
      li.append(btn);
      return li;
    }));
    $("#no-games").hidden = games.length > 0;
  } catch (err) {
    $("#lobby-error").textContent = err.message;
  }
}

$("#new-game").addEventListener("click", async () => {
  game = { id: null, status: "active", max_turns: 12, turns: [] };
  showGameScreen();
  await play("/games", undefined);
});

$("#back").addEventListener("click", openLobby);
$("#ending-back").addEventListener("click", openLobby);

// ---------- Partida ----------

function showGameScreen() {
  show("game");
  $("#story").replaceChildren();
  $("#game-error").textContent = "";
  for (const id of ["#resume", "#action-form", "#ending"]) $(id).hidden = true;
}

async function openGame(id) {
  showGameScreen();
  try {
    game = await getJson(`/games/${id}`);
  } catch (err) {
    $("#game-error").textContent = err.message;
    return;
  }
  for (const turn of game.turns) $("#story").append(turnElement(turn));
  updateControls();
}

function turnElement(turn) {
  const article = document.createElement("article");
  article.className = "turn";

  if (turn.action) {
    const action = document.createElement("p");
    action.className = "action";
    const text = document.createElement("span");
    text.className = "text";
    text.textContent = turn.action;
    const roll = document.createElement("span");
    roll.className = "roll";
    action.append(text, roll);
    article.append(action);
    if (turn.roll) setRoll(roll, turn.roll, turn.outcome);
  }

  const narration = document.createElement("p");
  narration.className = "narration";
  narration.textContent = turn.narration ?? "";
  article.append(narration);
  return article;
}

function setRoll(el, roll, outcome) {
  el.className = `roll ${outcome}`;
  el.textContent = `${roll} · ${OUTCOME_LABEL[outcome]}`;
}

// O d20 gira um pouco antes de mostrar o resultado (que já veio do servidor)
function animateRoll(el, roll, outcome) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return setRoll(el, roll, outcome);
  el.className = "roll rolling";
  const spin = setInterval(() => { el.textContent = 1 + Math.floor(Math.random() * 20); }, 70);
  setTimeout(() => { clearInterval(spin); setRoll(el, roll, outcome); }, 900);
}

function renderCandles() {
  const played = game.turns.filter((t) => t.number > 0 && t.narration !== null).length;
  const candles = [];
  for (let i = 0; i < game.max_turns; i++) {
    const c = document.createElement("span");
    c.className = i < game.max_turns - played ? "candle lit" : "candle";
    candles.push(c);
  }
  $("#candles").replaceChildren(...candles);
}

// Decide o que aparece embaixo da história: campo de ação, "continuar" ou fim
function updateControls() {
  renderCandles();
  const last = game.turns.at(-1);
  const pending = last && last.narration === null;

  $("#ending").hidden = game.status !== "finished";
  $("#resume").hidden = !(pending && last.number > 0);
  $("#action-form").hidden = game.status === "finished" || pending;

  if (pending && last.number === 0) {
    $("#game-error").textContent = "Essa aventura se perdeu nas trevas antes de começar. Comece outra.";
  }
  if (!$("#action-form").hidden) $("#action-form textarea").focus();
}

async function play(path, json) {
  $("#game-error").textContent = "";
  for (const id of ["#resume", "#action-form"]) $(id).hidden = true;

  let article = null;
  let narration = null;
  let turn = null;

  try {
    await stream(path, json, {
      start(data) {
        game.id = data.game_id;
        // Numa nova tentativa o turno já está na tela: troca pelo que vai ser narrado
        if (game.turns.at(-1)?.number === data.number) {
          game.turns.pop();
          $("#story").lastElementChild?.remove();
        }
        turn = { number: data.number, action: data.action, roll: data.roll, outcome: data.outcome, narration: null };
        game.turns.push(turn);
        article = turnElement({ ...turn, roll: null });
        narration = article.querySelector(".narration");
        narration.classList.add("waiting");
        $("#story").append(article);
        if (data.roll) animateRoll(article.querySelector(".roll"), data.roll, data.outcome);
        article.scrollIntoView({ behavior: "smooth", block: "start" });
      },
      chunk(data) {
        narration.textContent += data.text;
      },
      done(data) {
        narration.textContent = data.narration;
        turn.narration = data.narration;
        game.status = data.game_status;
      },
      error(data) {
        throw new ApiError(data.detail);
      },
    });
  } catch (err) {
    if (err.name === "AbortError") return;   // saiu da tela no meio
    $("#game-error").textContent = err.message;
    narration?.classList.remove("waiting");
    // Se a abertura falha, o servidor apaga o jogo: não há o que continuar
    if (game.id === null || turn?.number === 0) return;
  } finally {
    controller = null;
  }

  narration?.classList.remove("waiting");
  updateControls();
}

$("#action-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const textarea = e.target.querySelector("textarea");
  const action = textarea.value.trim();
  if (!action) return;
  textarea.value = "";
  play(`/games/${game.id}/actions`, { action });
});

// Enter envia, Shift+Enter quebra linha
$("#action-form textarea").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    e.target.form.requestSubmit();
  }
});

// Retoma um turno interrompido: o servidor reaproveita a ação e o dado já salvos
$("#resume-btn").addEventListener("click", () => {
  play(`/games/${game.id}/actions`, { action: game.turns.at(-1).action });
});

// ---------- Início ----------

if (token) openLobby();
else show("auth");
