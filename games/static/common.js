/* Shared shell for all games: connection, lobby, room, overlay, toast and confetti.
 *
 * Load this file first, then call Shell.start(GAME) with:
 *   kind      – "stapeljagd" | "tiefpunkt" (WebSocket path and storage keys)
 *   title     – shown in the lobby
 *   fan       – HTML of a few cards for the lobby logo
 *   art       – optional, name of an illustration from art.js instead of cards (non-card games)
 *   settings  – [{ key, options: [[value, label], ...] }] chosen when creating a room
 *   render(fromServer) – draws #table from Shell.game
 *   finished() – { title, sub, icon? } for the end-of-game overlay
 *   minPlayers – optional, players needed to start (default 2)
 *   countPlayers(game) – optional, how many of the players count towards minPlayers
 *   roomPlayer(p, me, game) – optional, extra HTML for a player row in the waiting room;
 *                 buttons with data-room-act="X" send {t: "X"}
 *   noBots     – optional, hide "+ Computer-Spieler"
 *   onMessage(msg) – optional, other server messages (e.g. live drawing)
 */
(function () {
  const $ = id => document.getElementById(id);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };
  const Shell = window.Shell = {
    game: null, prev: null, me: null, ws: null, token: null,
    $, store,
    send(msg) { if (Shell.ws && Shell.ws.readyState === 1) Shell.ws.send(JSON.stringify(msg)); },
    esc(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); },
    avatar(p) {
      let h = 0; for (const ch of String(p.name)) h = (h * 31 + ch.charCodeAt(0)) % 360;
      return `<span class="avatar" style="--h:${h}">${p.bot ? "🤖" : Shell.esc(p.name.slice(0, 1).toUpperCase())}</span>`;
    },
    toast(text) {
      const t = $("toast");
      t.textContent = text; t.classList.add("show");
      clearTimeout(Shell.toast.timer); Shell.toast.timer = setTimeout(() => t.classList.remove("show"), 2600);
    },
    confetti() {
      const box = $("confetti");
      const colors = ["#a78bfa", "#f472b6", "#34d399", "#60a5fa", "#facc15", "#fb923c"];
      box.innerHTML = Array.from({ length: 140 }, () => {
        const left = Math.random() * 100, dur = 2.2 + Math.random() * 2.2, delay = Math.random() * .8;
        return `<i style="left:${left}vw;background:${colors[Math.random() * colors.length | 0]};--dx:${(Math.random() - .5) * 30}vw;--rot:${Math.random() * 1080 - 540}deg;animation-duration:${dur}s;animation-delay:${delay}s"></i>`;
      }).join("");
      setTimeout(() => box.innerHTML = "", 5200);
    },
    /* A card with a front and back face; `front` is the inner HTML of the front. */
    card(cls, front, attrs = "", extra = "", backLabel = "★") {
      return `<div class="card ${cls}" ${attrs}><div class="inner">
        <div class="face front">${front}</div><div class="face back"><span>${backLabel}</span></div>
      </div>${extra}</div>`;
    },
    /* Animate an element from a rectangle (where the card came from) to its place. */
    fly(el, from) {
      if (!el || !from) return;
      const to = el.getBoundingClientRect();
      const dx = from.left + from.width / 2 - (to.left + to.width / 2);
      const dy = from.top + from.height / 2 - (to.top + to.height / 2);
      const s = Math.max(.4, Math.min(1.6, from.width / to.width));
      el.animate([
        { transform: `translate(${dx}px, ${dy}px) scale(${s}) rotate(-12deg)`, zIndex: 20 },
        { transform: "translate(0, 0) scale(1.12) rotate(3deg)", offset: .75, zIndex: 20 },
        { transform: "none", zIndex: 20 },
      ], { duration: 520, easing: "cubic-bezier(.2,.8,.2,1)" });
    },
    burst(container, text) {
      if (!container) return;
      container.insertAdjacentHTML("beforeend", `<div class="done-burst"></div><div class="done-label">${text}</div>`);
      setTimeout(() => container.querySelectorAll(".done-burst, .done-label").forEach(n => n.remove()), 1400);
    },
    rect(el) { const r = el.getBoundingClientRect(); return { left: r.left, top: r.top, width: r.width, height: r.height }; },
  };

  Shell.start = function (G) {
  Shell.token = store.get(G.kind + "-token");

  // ---------- page skeleton ----------
  const select = (id, short) => G.settings.map(s => `
    <select data-setting="${s.key}" id="${id}-${s.key}" aria-label="${s.label}">
      ${s.options.map(([v, label]) => `<option value="${v}">${short ? (s.short || label).replace("{}", label) : label}</option>`).join("")}
    </select>`).join("");
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="backdrop"><i></i><i></i><i></i><i></i></div>
    <div class="conn glass hidden" id="conn">Verbindung wird hergestellt …</div>
    <section id="lobby" class="page hidden">
      <a class="home" href="../">← Alle Spiele</a>
      <div class="logo">${G.art && window.ART ? `<div class="fan artfan">${window.ART[G.art]}</div>` : `<div class="fan">${G.fan}</div>`}<h1>${G.title}</h1></div>
      <div class="panel glass">
        <p class="label">Dein Name</p>
        <input id="name" maxlength="20" placeholder="z. B. Alex" autocomplete="nickname" style="width:100%">
      </div>
      <div class="panel glass">
        <h2>Neues Spiel</h2>
        <div class="row">${select("new")}<button class="btn" id="create">Spiel erstellen</button></div>
      </div>
      <div class="panel glass">
        <h2>Spiel beitreten</h2>
        <div class="row">
          <input id="joinCode" maxlength="4" placeholder="Code, z. B. KXAB" style="text-transform:uppercase">
          <button class="btn" id="join">Beitreten</button>
        </div>
        <ul class="games" id="games" style="margin-top:12px"></ul>
      </div>
    </section>
    <section id="room" class="page hidden">
      <div class="panel glass roomcode">
        <div class="label">${G.title} · Spielcode</div>
        <div class="big" id="roomCode">----</div>
        <p>Mitspieler öffnen diese Seite und treten mit dem Code bei.</p>
        <button class="btn ghost invite" id="invite">📨 Einladen</button>
      </div>
      <div class="panel glass">
        <h2>Spieler</h2>
        <ul class="players" id="roomPlayers"></ul>
        <div class="row" id="hostControls"><button class="btn ghost" id="addBot">+ Computer-Spieler</button>${select("room")}</div>
      </div>
      <div class="row" style="justify-content:space-between">
        <button class="btn ghost" id="leaveRoom">Verlassen</button>
        <button class="btn" id="start">Spiel starten</button>
      </div>
      <p class="empty" id="waitHost" style="text-align:center"></p>
    </section>`);
  document.body.insertAdjacentHTML("beforeend", `
    <div class="overlay hidden" id="finished">
      <div class="panel glass">
        <div class="trophy" id="trophy">🏆</div>
        <h3 id="winner"></h3>
        <div class="empty" id="winnerSub"></div>
        <div class="row" style="justify-content:center;margin-top:16px">
          <button class="btn ghost" id="toLobby">Zur Lobby</button>
          <button class="btn" id="rematch">Neues Spiel</button>
        </div>
      </div>
    </div>
    <div class="confetti" id="confetti"></div>
    <div class="toast glass" id="toast"></div>`);

  $("name").value = store.get("spiele-name") || "";
  // Invitation links carry the room code: ?code=ABCD
  const invited = (new URLSearchParams(location.search).get("code") || "").toUpperCase().replace(/[^A-Z]/g, "").slice(0, 4);
  if (invited) $("joinCode").value = invited;
  $("name").addEventListener("input", () => store.set("spiele-name", $("name").value.trim()));
  const settingsFrom = prefix => Object.fromEntries(G.settings.map(s => [s.key, +$(`${prefix}-${s.key}`).value]));

  // ---------- connection ----------
  let reconnectTimer;
  function connect() {
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const ws = Shell.ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + base + "ws");
    ws.onopen = () => { $("conn").classList.add("hidden"); ws.send(JSON.stringify({ token: Shell.token })); };
    ws.onmessage = e => handle(JSON.parse(e.data));
    ws.onclose = () => {
      $("conn").classList.remove("hidden");
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 1500);
    };
  }

  let celebrated = null;
  function handle(msg) {
    if (msg.t === "hello") { Shell.token = msg.token; store.set(G.kind + "-token", msg.token); }
    else if (msg.t === "error") { Shell.toast(msg.msg); if (G.onError) G.onError(); }
    else if (msg.t !== "game" && msg.t !== "lobby" && G.onMessage) G.onMessage(msg);
    else if (msg.t === "lobby") { Shell.game = Shell.prev = Shell.me = null; showLobby(msg.games); }
    else if (msg.t === "game") {
      const old = Shell.game;
      Shell.prev = old && old.code === msg.game.code && old.state !== "lobby" && msg.game.state !== "lobby" ? old : null;
      Shell.game = msg.game; Shell.me = msg.me;
      if (msg.game.state === "lobby") showRoom();
      else {
        show("table");
        G.render(true);
        if (msg.game.state === "finished") {
          const f = G.finished();
          $("winner").textContent = f.title;
          $("winnerSub").innerHTML = f.sub || "";
          $("trophy").textContent = f.icon || "🏆";
          $("rematch").classList.toggle("hidden", msg.game.host !== msg.me);
          const round = msg.game.code + msg.game.log.join("|");
          if (celebrated !== round) { celebrated = round; Shell.confetti(); }
        }
      }
    }
  }

  function show(id) {
    for (const s of ["lobby", "room", "table"]) $(s).classList.toggle("hidden", s !== id);
    $("finished").classList.toggle("hidden", !(Shell.game && Shell.game.state === "finished"));
  }
  Shell.show = show;

  function myName() {
    const n = $("name").value.trim();
    if (!n) { Shell.toast("Bitte gib zuerst deinen Namen ein"); $("name").focus(); }
    return n;
  }

  // ---------- lobby ----------
  function showLobby(games) {
    show("lobby");
    const open = games.filter(g => g.state === "lobby" && !g.full);
    $("games").innerHTML = open.length ? open.map(g => `
      <li><span class="code">${Shell.esc(g.code)}</span>
        <span class="who">${Shell.esc(g.players.join(", "))}</span>
        <button class="btn ghost" data-join="${Shell.esc(g.code)}" style="padding:7px 14px">Beitreten</button></li>`).join("")
      : `<li class="empty">Gerade gibt es keine offenen Spiele.</li>`;
  }
  $("create").onclick = () => { const name = myName(); if (name) Shell.send({ t: "create", name, settings: settingsFrom("new") }); };
  $("join").onclick = () => {
    const name = myName(), code = $("joinCode").value.trim().toUpperCase();
    if (name && code) Shell.send({ t: "join", name, code });
  };
  $("joinCode").addEventListener("keydown", e => { if (e.key === "Enter") $("join").click(); });
  $("games").onclick = e => {
    const b = e.target.closest("[data-join]");
    if (b) { const name = myName(); if (name) Shell.send({ t: "join", name, code: b.dataset.join }); }
  };

  // ---------- room ----------
  function showRoom() {
    show("room");
    const { game, me } = Shell;
    const host = game.host === me;
    $("roomCode").textContent = game.code;
    $("roomPlayers").innerHTML = game.players.map(p => `
      <li>${Shell.avatar(p)}<span class="name">${Shell.esc(p.name)}${p.id === me ? " (du)" : ""}</span>
        ${p.id === game.host ? '<span class="tag host">Gastgeber</span>' : p.bot ? '<span class="tag">Computer</span>' : ""}
        ${G.roomPlayer ? G.roomPlayer(p, me, game) : ""}
        ${host && p.id !== me ? `<button class="x" data-kick="${p.id}" title="Entfernen">×</button>` : ""}</li>`).join("");
    $("hostControls").classList.toggle("hidden", !host);
    $("start").classList.toggle("hidden", !host);
    const min = G.minPlayers || 2;
    const count = G.countPlayers ? G.countPlayers(game) : game.players.length;
    $("addBot").classList.toggle("hidden", !!G.noBots);
    $("start").disabled = count < min;
    for (const s of G.settings) $(`room-${s.key}`).value = String(game.settings[s.key]);
    $("waitHost").textContent = host
      ? (count < min ? `Mindestens ${min} Spieler – warte auf Mitspieler${G.noBots ? "" : " oder füge einen Computer-Spieler hinzu"}.` : "")
      : "Warte, bis der Gastgeber das Spiel startet …";
  }
  $("roomPlayers").onclick = e => {
    const b = e.target.closest("[data-kick]"), a = e.target.closest("[data-room-act]");
    if (b) Shell.send({ t: "kick", id: b.dataset.kick });
    if (a) Shell.send({ t: a.dataset.roomAct });
  };
  $("invite").onclick = async () => {
    const code = Shell.game.code;
    const url = location.origin + location.pathname + "?code=" + code;
    const text = `Spiel mit mir ${G.title}! Code: ${code}`;
    if (navigator.share) { try { await navigator.share({ title: G.title, text, url }); return; } catch (e) { if (e.name === "AbortError") return; } }
    try { await navigator.clipboard.writeText(`${text}\n${url}`); Shell.toast("Einladungslink kopiert"); }
    catch { prompt("Diesen Link verschicken:", url); }
  };
  $("addBot").onclick = () => Shell.send({ t: "add_bot" });
  for (const s of G.settings) $(`room-${s.key}`).onchange = () => Shell.send({ t: "settings", settings: settingsFrom("room") });
  $("start").onclick = () => Shell.send({ t: "start" });
  $("leaveRoom").onclick = () => Shell.send({ t: "leave" });
  $("toLobby").onclick = () => Shell.send({ t: "leave" });
  $("rematch").onclick = () => Shell.send({ t: "rematch" });
  Shell.leaveGame = () => {
    if (Shell.game.state !== "playing" || confirm("Spiel verlassen? Ein Computer-Spieler übernimmt deinen Platz.")) Shell.send({ t: "leave" });
  };

  connect();
  };
})();
