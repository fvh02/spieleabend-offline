/* Shared page logic for the party games (on top of common.js).
 *
 * Party.start({
 *   kind, title, fan, settings, minPlayers,
 *   build(g, ctx)   – HTML of the stage for the current phase (ctx: { tv, host, me, mine })
 *   bind(g, ctx)    – optional, attach handlers after build
 *   update(g, ctx)  – optional, refresh dynamic bits without rebuilding (keeps typed text)
 *   wait            – optional, { phase: "text shown after answering" }
 *   finishedExtra(g) – optional, extra HTML under the final ranking
 * })
 * One device can be the Host screen (TV): it gets body.tv and a big layout without inputs.
 */
(function () {
  const esc = s => Shell.esc(s);
  const Party = window.Party = {};

  Party.ranking = (g, opts = {}) => {
    const list = g.players.filter(p => !p.screen).sort((a, b) => b.score - a.score);
    return `<div class="pscore">${list.map((p, i) => `
      <div class="ps ${p.id === Shell.me ? "me" : ""}" style="animation-delay:${i * 40}ms"><span class="pos">${i + 1}</span>${Shell.avatar(p)}
        <span class="n">${esc(p.name)}</span>${opts.gained && p.gained ? `<span class="plus">+${p.gained}</span>` : ""}<span class="pts">${p.score}</span></div>`).join("")}</div>`;
  };

  Party.status = g => `<div class="pstatus">${g.players.filter(p => !p.screen).map(p =>
    Shell.avatar(p).replace('class="avatar"', `class="avatar ${p.done ? "ok" : ""}" title="${esc(p.name)}${p.done ? " ✓" : ""}"`)).join("")}</div>`;

  Party.nameOf = (g, id) => (g.players.find(p => p.id === id) || {}).name || "?";
  /* Replace the HTML of a part only when it changed (keeps focus and typed text otherwise). */
  Party.set = (id, html) => {
    const el = typeof id === "string" ? document.getElementById(id) : id;
    if (!el || el._html === html) return false;
    el.innerHTML = html; el._html = html; return true;
  };
  Party.gap = (text, fill) => esc(text).replace("___", fill == null ? '<span class="gap"></span>' : `<b class="fill">${esc(fill)}</b>`);
  Party.num = v => Number(v).toLocaleString("de-DE", { maximumFractionDigits: 2 });
  /* An input + button that sends {t, [field]: value}; Enter submits. */
  Party.form = (id, placeholder, button, max = 40, mode = "text") => `<form class="pform" id="${id}" autocomplete="off">
      <input name="v" maxlength="${max}" placeholder="${esc(placeholder)}" inputmode="${mode}" enterkeyhint="send" required>
      <button class="btn">${button}</button></form>`;
  Party.onForm = (id, send) => {
    const f = document.getElementById(id);
    if (!f || f._bound) return;
    f._bound = true;
    f.onsubmit = e => { e.preventDefault(); const v = f.v.value.trim(); if (v) send(v); };
    if (matchMedia("(pointer: fine)").matches) f.v.focus();
  };

  Party.start = function (cfg) {
    let key = null, endAt = null;
    const stage = () => document.getElementById("stage");

    function ctxFor(g) {
      const me = g.players.find(p => p.id === Shell.me);
      return { tv: !!(me && me.screen), host: g.host === Shell.me, me, hasTv: !!g.screen };
    }

    function frame(g, ctx, inner) {
      const input = !!(cfg.inputPhases || []).includes(g.phase);
      const last = cfg.isLast ? cfg.isLast(g) : g.round >= g.rounds;
      const canNext = ctx.host || (cfg.canNext && cfg.canNext(g, ctx));
      const next = `<button class="btn" data-pact="next">${last ? "Zum Endergebnis 🏆" : (cfg.nextLabel || "Nächste Runde →")}</button>`;
      const controls = g.phase === "reveal"
        ? (ctx.host ? `<div class="row pctl"><button class="btn ghost" data-pact="end_game">Spiel beenden</button>${next}</div>`
          : canNext && !ctx.tv ? `<div class="row pctl">${next}</div>`
          : !ctx.tv ? `<p class="pmuted">Der Gastgeber startet die nächste Runde.</p>` : "")
        : ctx.host && input ? `<div class="row pctl">${cfg.endAnytime ? '<button class="btn ghost small" data-pact="end_game">Spiel beenden</button>' : ""}
            <button class="btn ghost small" data-pact="skip">${cfg.skipLabel || "⏭ Nicht mehr warten"}</button></div>` : "";
      const head = `<div class="phead"><span class="pround">${cfg.head ? cfg.head(g) : `Runde ${g.round} / ${g.rounds}`}</span><span class="ptimer hidden" id="ptimer"></span></div>`;
      if (ctx.tv) {
        return `<div class="tvgrid"><div class="tvmain glass">${head}${inner}</div>
          <aside class="tvside"><div class="glass"><h3 class="plabel">Punkte</h3><div id="tvRank"></div></div>
          <div class="glass tvcode"><span>Mitspielen:</span> <b>${esc(g.code)}</b></div></aside></div>`;
      }
      return `<div class="pstage glass">${head}${inner}${controls}</div>`;
    }

    function render() {
      const g = Shell.game, ctx = ctxFor(g);
      document.body.classList.toggle("tv", ctx.tv);
      document.getElementById("tableCode").textContent = `Code ${g.code}`;
      document.getElementById("leaveGame").onclick = Shell.leaveGame;
      const timed = (cfg.timerPhases || cfg.inputPhases || []).includes(g.phase);
      endAt = g.remaining == null || !timed ? null : Date.now() + g.remaining * 1000;
      const k = `${g.round}|${g.phase}|${g.state}|${ctx.tv}|${ctx.host}|${cfg.key ? cfg.key(g) : ""}`;
      if (k !== key) {
        key = k;
        stage().innerHTML = frame(g, ctx, cfg.build(g, ctx));
        stage().querySelectorAll("[data-pact]").forEach(b => b.onclick = () => {
          if (b.dataset.pact === "end_game" && !confirm("Spiel jetzt beenden?")) return;
          Shell.send({ t: b.dataset.pact });
        });
        if (cfg.bind) cfg.bind(g, ctx);
        if (g.phase === "reveal" && g.state === "playing" && cfg.celebrate && cfg.celebrate(g, ctx)) Shell.confetti();
      }
      if (cfg.update) cfg.update(g, ctx);
      const st = stage().querySelector("[data-status]");
      if (st) st.innerHTML = Party.status(g);
      const rank = document.getElementById("tvRank");
      if (rank) rank.innerHTML = Party.ranking(g, { gained: g.phase === "reveal" });
      tick();
    }

    function tick() {
      const el = document.getElementById("ptimer"), g = Shell.game;
      if (!el) return;
      if (!g || endAt == null) { el.classList.add("hidden"); return; }
      const left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      el.classList.remove("hidden");
      el.textContent = `⏱ ${left}`;
      el.classList.toggle("low", left <= 10);
    }
    setInterval(tick, 300);

    window.GAME = {
      kind: cfg.kind, title: cfg.title, fan: cfg.fan || "", art: cfg.art, settings: cfg.settings,
      minPlayers: cfg.minPlayers || 3, noBots: true,
      countPlayers: g => g.players.filter(p => !p.screen).length,
      roomPlayer: (p, me, g) => {
        if (p.id !== me) return p.screen ? '<span class="tag tv">📺 Host</span>' : "";
        if (p.screen) return '<button class="btn tvbtn" data-room-act="screen" title="Dieses Gerät ist der Bildschirm">📺 Host ✓</button>';
        return g.players.some(q => q.screen) ? "" : '<button class="btn ghost tvbtn" data-room-act="screen" title="Dieses Gerät wird zum Bildschirm (z. B. Fernseher) und spielt nicht mit">📺 Host</button>';
      },
      render,
      finished: () => {
        const g = Shell.game, ranked = g.players.filter(p => !p.screen).sort((a, b) => b.score - a.score);
        const top = ranked[0];
        if (cfg.finished) return cfg.finished(g, ranked);
        return { icon: cfg.icon || "🏆",
          title: top && top.score ? `${top.id === Shell.me ? "Du gewinnst" : top.name + " gewinnt"}!` : "Spiel beendet",
          sub: Party.ranking(g) + (cfg.finishedExtra ? cfg.finishedExtra(g) : "") };
      },
    };
    Shell.start(window.GAME);
    if (cfg.drink) {
      const logo = document.querySelector("#lobby .logo");
      if (logo) logo.insertAdjacentHTML("beforeend", `<p class="drinknote">🍻 Trinkspiel ab 18 – klappt genauso mit Wasser, Saft oder Limo. Trinkt verantwortungsvoll und niemand muss.</p>`);
    }
  };
})();
