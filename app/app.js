/* Spieleabend offline – the shell around the game pages.
 *
 * Host:  runs the games (Python in Pyodide, app/engine-worker.js) and is connected to every guest by WebRTC.
 * Guest: shows the game page and passes its messages to the host.
 * The game pages (games/<kind>/) are the same as in the add-on; games/static/embed.js connects them here.
 */
(function () {
  const $ = id => document.getElementById(id);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const toast = text => { const t = $("toast"); t.textContent = text; t.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 2800); };
  const avatar = name => { let h = 0; for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) % 360; return `<span class="avatar" style="--h:${h}">${esc(String(name).slice(0, 1).toUpperCase())}</span>`; };

  const GAMES = [
    ["stapeljagd", "Stapeljagd", 2, 6, "karten", "🃏"], ["tiefpunkt", "Tiefpunkt", 2, 8, "karten", "🂠"],
    ["farbrausch", "Farbrausch", 2, 10, "karten", "🌈"], ["kritzelpost", "Kritzelpost", 3, 10, "zeichnen"],
    ["schnellmaler", "Schnellmaler", 2, 12, "zeichnen"], ["galgenraten", "Galgenraten", 1, 8, "woerter"],
    ["imposter", "Imposter", 3, 16, "party", "🕵️"], ["schaetzmeister", "Schätzmeister", 2, 16, "quiz"],
    ["werwuerde", "Wer würde eher …?", 3, 16, "party"], ["luegenbaron", "Lügenbaron", 3, 12, "quiz"],
    ["punchline", "Punchline", 3, 12, "party"], ["nochnie", "Ich hab noch nie …", 2, 16, "trinken"],
    ["wahrheit", "Wahrheit oder Trinken", 2, 16, "trinken"], ["trinklotto", "Trinklotto", 2, 16, "trinken"],
    ["pyramide", "Pyramide", 2, 9, "trinken", "🔺"], ["pferderennen", "Pferderennen", 2, 16, "trinken", "🏇"],
    ["ringoffire", "Ring of Fire", 2, 16, "trinken", "👑"],
  ].map(([kind, title, min, max, type, emoji]) => ({ kind, title, min, max, type, emoji }));

  // ---------- this device ----------
  const me = { token: store.get("spo-token"), name: store.get("spiele-name") || "" };
  if (!me.token) { me.token = Math.random().toString(36).slice(2) + Date.now().toString(36); store.set("spo-token", me.token); }
  $("name").value = me.name;
  $("name").addEventListener("input", () => { me.name = $("name").value.trim(); store.set("spiele-name", me.name); });
  const needName = () => { me.name = $("name").value.trim(); if (!me.name) { toast("Bitte gib zuerst deinen Namen ein"); $("name").focus(); return false; } return true; };

  let role = null;        // "host" | "guest"
  let kind = null;        // game being played
  let stopScan = null;

  function show(id) {
    for (const s of document.querySelectorAll(".screen")) s.classList.toggle("hidden", s.id !== id);
    $("play").classList.add("hidden");
    if (stopScan && id !== "scr-join") { stopScan(); stopScan = null; }
  }

  // Keep the screen on – a sleeping phone loses the connection.
  let wake = null;
  async function keepAwake() {
    try { if ("wakeLock" in navigator && !wake && document.visibilityState === "visible") { wake = await navigator.wakeLock.request("screen"); wake.onrelease = () => wake = null; } } catch {}
  }
  document.addEventListener("visibilitychange", () => { if (role) keepAwake(); });

  // ---------- the game page (iframe) ----------
  const frame = $("frame");
  let frameKind = null;
  function openGame(k) {
    $("spectate").classList.add("hidden");
    for (const s of document.querySelectorAll(".screen")) s.classList.add("hidden");
    $("play").classList.remove("hidden");
    if (frameKind !== k) { frameKind = k; frame.src = `games/${k}/`; }
  }
  function closeGame() { frameKind = null; frame.src = "about:blank"; $("play").classList.add("hidden"); }
  const toFrame = msg => { if (frame.contentWindow) frame.contentWindow.postMessage(msg, location.origin); };

  window.addEventListener("message", e => {
    if (e.source !== frame.contentWindow || !e.data || !e.data.spo) return;
    const m = e.data;
    if (m.spo === "open") {
      if (m.kind === "wortgitter") return;
      toFrame({ spo: "ready" });
      if (role === "host") host.call("connect", me.token, m.kind);
      else if (role === "guest") guest.send({ t: "open", kind: m.kind });
    } else if (m.spo === "up") {
      if (role === "host") host.call("handle", me.token, m.data);
      else if (role === "guest") guest.send({ t: "up", data: m.data });
    } else if (m.spo === "close") {
      if (role === "host") host.call("disconnect", me.token);
      else if (role === "guest") guest.send({ t: "close" });
    } else if (m.spo === "menu") menu();
  });
  $("menuBtn").onclick = () => menu(true);
  $("spectateBack").onclick = () => menu();

  function menu(ask) {
    if (frameKind === "wortgitter") { closeGame(); show(role === "host" ? "scr-host" : role === "guest" ? "scr-wait" : "scr-start"); return; }
    if (role === "host") {
      if (kind && !confirm(ask ? "Spiel für alle beenden und ein anderes wählen?" : "Zurück zur Spieleauswahl? Das Spiel endet für alle.")) return;
      host.endGame();
    } else if (role === "guest") {
      if (ask && kind && !confirm("Spiel verlassen? Ein Computer-Spieler übernimmt, bis du zurückkommst.")) return;
      if (kind) guest.send({ t: "close" });
      closeGame(); guest.waiting();
    } else { closeGame(); show("scr-start"); }
  }

  const solo = () => { openGame("wortgitter"); };
  $("solo").onclick = solo; $("solo2").onclick = solo;

  // ================= HOST =================
  const host = {
    worker: null, ready: null, peers: new Map(), seq: 0, pending: new Map(),
    start() {
      role = "host"; keepAwake();
      show("scr-host"); this.renderDevices(); this.renderGames();
      if (this.worker) return;
      this.worker = new Worker("app/engine-worker.js");
      this.ready = new Promise((resolve, reject) => {
        this.worker.onmessage = e => {
          const m = e.data;
          if (m.t === "ready") { $("engineState").textContent = "● bereit"; $("engineState").className = "engine ok"; resolve(); }
          else if (m.t === "failed") { $("engineState").textContent = "Fehler beim Laden"; $("engineState").className = "engine bad"; toast(m.error); reject(new Error(m.error)); }
          else if (m.t === "out") m.list.forEach(([token, msg]) => this.deliver(token, msg));
          else if (m.t === "result") { const p = this.pending.get(m.id); this.pending.delete(m.id); if (p) m.error ? p.reject(new Error(m.error)) : p.resolve(); }
        };
      });
      this.call("set_device", me.token, me.name, true);
    },
    async call(fn, ...args) {
      await this.ready;
      const id = ++this.seq;
      return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.worker.postMessage({ fn, args, id }); });
    },
    deliver(token, msg) {
      if (token === me.token) {
        if (msg.t === "spectate") $("spectate").classList.remove("hidden");
        else toFrame({ spo: "down", data: JSON.stringify(msg) });
      } else {
        const peer = this.peers.get(token);
        if (peer && peer.link) peer.link.send({ t: "down", data: msg });
      }
    },
    devices() {
      return [{ name: me.name, host: true, on: true }, ...[...this.peers.values()].map(p => ({ name: p.name, on: !!p.link }))];
    },
    broadcast(msg) { for (const p of this.peers.values()) if (p.link) p.link.send(msg); },
    renderDevices() {
      const list = this.devices();
      $("devices").innerHTML = list.map(d => `<li class="${d.on ? "" : "off"}">${avatar(d.name)}<span class="name">${esc(d.name)}</span>
        ${d.host ? '<span class="tag host">Gastgeber</span>' : ""}<span class="dot" title="${d.on ? "verbunden" : "getrennt"}"></span></li>`).join("");
      this.broadcast({ t: "devices", list });
      this.renderGames();
    },
    renderGames() {
      const type = $("typeFilter").value, n = this.devices().filter(d => d.on).length;
      $("fitInfo").textContent = `${n} ${n === 1 ? "Gerät" : "Geräte"}`;
      $("gameList").innerHTML = GAMES.filter(g => !type || g.type === type).map(g => {
        const fits = n <= g.max + 1;   // + one device as TV
        const pic = window.ART && ART[g.kind] ? ART[g.kind] : `<span>${g.emoji || "🎲"}</span>`;
        return `<button class="game ${fits ? "" : "off"}" data-kind="${g.kind}"><div class="pic">${pic}</div><b>${esc(g.title)}</b><small>${g.min === g.max ? g.min : `${g.min}–${g.max}`} Spieler</small></button>`;
      }).join("");
    },
    async pick(k) {
      try { await this.call("start_game", k); } catch (err) { toast(err.message); return; }
      kind = k;
      this.broadcast({ t: "game", kind: k });
      openGame(k);
    },
    async endGame() {
      kind = null;
      closeGame();
      try { await this.call("end_game"); } catch {}
      this.broadcast({ t: "game", kind: null });
      show("scr-host"); this.renderDevices();
    },
    attach(link, answer) {
      const token = answer.k, name = answer.n || "Gast";
      const old = this.peers.get(token);
      if (old && old.link) old.link.close();
      this.peers.set(token, { name, link });
      link.onmessage = msg => this.fromGuest(token, msg);
      link.onclose = () => {
        const p = this.peers.get(token);
        if (!p || p.link !== link) return;
        p.link = null;
        this.call("drop", token).catch(() => {});
        toast(`${name} ist nicht mehr verbunden`);
        this.renderDevices();
      };
      this.call("set_device", token, name, false).catch(() => {});
      link.send({ t: "welcome", host: me.name, kind });
      this.renderDevices();
    },
    fromGuest(token, msg) {
      if (msg.t === "open") this.call("connect", token, msg.kind).catch(() => {});
      else if (msg.t === "up") this.call("handle", token, msg.data).catch(() => {});
      else if (msg.t === "close") this.call("disconnect", token).catch(() => {});
      else if (msg.t === "bye") { const p = this.peers.get(token); if (p && p.link) p.link.close(); this.peers.delete(token); this.call("remove_device", token).catch(() => {}); this.renderDevices(); }
    },
  };
  $("typeFilter").onchange = () => host.renderGames();
  $("gameList").onclick = e => { const b = e.target.closest("[data-kind]"); if (b) host.pick(b.dataset.kind); };
  $("beHost").onclick = () => { if (needName()) host.start(); };
  $("hostBack").onclick = () => { if (confirm("Spieleabend beenden? Alle Verbindungen werden getrennt.")) location.reload(); };

  // ----- host: pairing dialog -----
  const pair = {
    invite: null,
    async open() {
      $("pair").classList.remove("hidden"); this.step(1); $("pairErr").textContent = "";
      $("pairQr").innerHTML = '<div class="spinner"></div>';
      if (!pair.warmed) { pair.warmed = true; await QR.warmUp(); }
      try {
        if (this.invite) this.invite.cancel();
        this.invite = await Net.offer(me.name);
        $("pairQr").innerHTML = QR.svg(this.invite.code);
      } catch (err) { $("pairErr").textContent = "Konnte keinen Code erstellen: " + err.message; }
    },
    step(n) { for (const i of [1, 2, 3]) $(`pairStep${i}`).classList.toggle("hidden", i !== n); },
    async scan() {
      this.step(2); $("pairErr").textContent = "";
      stopScan = await QR.scan($("pairScanner"), code => this.answer(code), t => t.toUpperCase().startsWith("SPO1"));
    },
    async answer(code) {
      if (stopScan) { stopScan(); stopScan = null; }
      const invite = this.invite;
      try {
        const a = await invite.accept(code);
        $("pairErr").textContent = "";
        $("pairScanner").innerHTML = `<p class="scanerr">Verbinde mit ${esc(a.n)} …</p>`;
        const link = await Promise.race([invite.opened, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 20000))]);
        this.invite = null;
        host.attach(link, a);
        $("pairDone").textContent = `${a.n} ist dabei!`;
        this.step(3);
      } catch (err) {
        $("pairErr").textContent = err.message === "timeout"
          ? "Keine Verbindung – seid ihr im selben WLAN oder Hotspot? Probier es noch einmal."
          : err.message;
        if (err.message === "timeout") { this.open(); }
      }
    },
    close() { if (stopScan) { stopScan(); stopScan = null; } if (this.invite) { this.invite.cancel(); this.invite = null; } $("pair").classList.add("hidden"); },
  };
  $("addGuest").onclick = () => pair.open();
  $("pairNext").onclick = () => pair.scan();
  $("pairMore").onclick = () => pair.open();
  $("pairClose").onclick = () => pair.close();
  $("pairX").onclick = () => pair.close();
  $("pairPasteBtn").onclick = () => pair.answer($("pairPaste").value);
  $("pairShare").onclick = () => shareCode(pair.invite && pair.invite.code);

  async function shareCode(code) {
    if (!code) return;
    if (navigator.share) { try { await navigator.share({ text: code }); return; } catch (e) { if (e.name === "AbortError") return; } }
    try { await navigator.clipboard.writeText(code); toast("Code kopiert"); } catch { prompt("Code kopieren:", code); }
  }

  // ================= GUEST =================
  const guest = {
    link: null, hostName: "", devices: [],
    async join() {
      role = "guest"; keepAwake();
      show("scr-join");
      $("joinStep1").classList.remove("hidden"); $("joinStep2").classList.add("hidden");
      stopScan = await QR.scan($("joinScanner"), code => this.answer(code), t => t.toUpperCase().startsWith("SPO1"));
    },
    async answer(code) {
      if (stopScan) { stopScan(); stopScan = null; }
      let reply;
      try { reply = await Net.answer(code, me); }
      catch (err) { toast(err.message); this.join(); return; }
      this.hostName = reply.host;
      $("joinStep1").classList.add("hidden"); $("joinStep2").classList.remove("hidden");
      $("joinHostName").textContent = reply.host;
      $("joinQr").innerHTML = QR.svg(reply.code);
      $("joinState").textContent = "Warte, bis der Gastgeber scannt …";
      $("joinShare").onclick = () => shareCode(reply.code);
      const link = await reply.opened;
      this.attach(link);
    },
    attach(link) {
      this.link = link;
      link.onmessage = msg => this.fromHost(msg);
      link.onclose = () => {
        if (this.link !== link) return;
        this.link = null; kind = null; closeGame();
        show("scr-wait");
        $("waitConn").textContent = "● getrennt"; $("waitConn").className = "engine bad";
        $("waitTitle").textContent = "Verbindung verloren";
        $("waitText").textContent = "Scanne den Code des Gastgebers noch einmal – du bekommst deinen Platz zurück.";
        $("rejoin").textContent = "Neu verbinden"; $("rejoin").classList.remove("hidden");
        $("rejoin").onclick = () => this.join();
      };
      this.waiting();
    },
    send(msg) { if (this.link) this.link.send(msg); },
    waiting() {
      show("scr-wait");
      const on = !!this.link;
      $("waitConn").textContent = on ? "● verbunden" : "● getrennt"; $("waitConn").className = "engine " + (on ? "ok" : "bad");
      $("waitTitle").textContent = on ? `Verbunden mit ${this.hostName}` : "Nicht verbunden";
      $("waitText").textContent = kind ? "Das Spiel läuft – du kannst jederzeit zurück." : `Warte, bis ${this.hostName} ein Spiel auswählt.`;
      $("rejoin").textContent = "Zurück ins Spiel";
      $("rejoin").classList.toggle("hidden", !kind);
      $("rejoin").onclick = () => openGame(kind);
    },
    fromHost(msg) {
      if (msg.t === "welcome") { this.hostName = msg.host; kind = msg.kind || null; if (kind) openGame(kind); else this.waiting(); }
      else if (msg.t === "game") { kind = msg.kind; if (kind) openGame(kind); else { closeGame(); this.waiting(); } }
      else if (msg.t === "devices") {
        this.devices = msg.list;
        $("guestDevices").innerHTML = msg.list.map(d => `<li class="${d.on ? "" : "off"}">${avatar(d.name)}<span class="name">${esc(d.name)}${d.name === me.name ? " (du)" : ""}</span>
          ${d.host ? '<span class="tag host">Gastgeber</span>' : ""}<span class="dot"></span></li>`).join("");
      } else if (msg.t === "down") {
        if (msg.data && msg.data.t === "spectate") $("spectate").classList.remove("hidden");
        else toFrame({ spo: "down", data: JSON.stringify(msg.data) });
      }
    },
  };
  $("beGuest").onclick = () => { if (needName()) guest.join(); };
  $("joinBack").onclick = () => { if (stopScan) { stopScan(); stopScan = null; } role = null; show("scr-start"); };
  $("joinPasteBtn").onclick = () => guest.answer($("joinPaste").value);
  $("waitLeave").onclick = () => { if (confirm("Den Spieleabend verlassen?")) { guest.send({ t: "bye" }); location.reload(); } };

  window.SPO = { host, guest };   // for debugging in the browser console

  // ---------- offline readiness ----------
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
    navigator.serviceWorker.addEventListener("message", e => {
      if (e.data && e.data.t === "cached") { $("offlineStatus").textContent = "✓ Offline bereit – die App funktioniert jetzt ohne Internet"; $("offlineStatus").className = "status ok"; }
      if (e.data && e.data.t === "progress") $("offlineStatus").textContent = `Wird für offline gespeichert … ${e.data.done} / ${e.data.total}`;
    });
    navigator.serviceWorker.ready.then(reg => reg.active && reg.active.postMessage({ t: "status" })).catch(() => {});
  }
})();
