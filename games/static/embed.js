/* Runs inside a game page (iframe of the offline app). The pages were written for a WebSocket to the
 * Spieleabend server; here a stand-in WebSocket passes everything to the shell around the iframe,
 * which relays it to the host's phone (or handles it locally on the host). */
(function () {
  if (window.parent === window) return;
  const origin = location.origin;
  const up = msg => parent.postMessage(msg, origin);
  const kind = location.pathname.split("/").filter(Boolean).pop();

  class OfflineSocket {
    constructor() {
      this.readyState = 0;
      OfflineSocket.current = this;
      up({ spo: "open", kind });
    }
    send(data) {
      if (this.readyState !== 1) return;
      let msg = {};
      try { msg = JSON.parse(data); } catch {}
      up({ spo: "up", data });
      if (msg.t === "leave") up({ spo: "menu", reason: "leave" });
    }
    close() { this.readyState = 3; up({ spo: "close" }); }
  }
  OfflineSocket.OPEN = 1;
  window.WebSocket = OfflineSocket;

  window.addEventListener("message", e => {
    if (e.source !== parent || !e.data || !e.data.spo) return;
    const ws = OfflineSocket.current, m = e.data;
    if (!ws) return;
    if (m.spo === "ready") { ws.readyState = 1; if (ws.onopen) ws.onopen(); }
    else if (m.spo === "down") { if (ws.onmessage) ws.onmessage({ data: m.data }); }
    else if (m.spo === "closed") { ws.readyState = 3; if (ws.onclose) ws.onclose(); }
  });

  // "← Alle Spiele" and other links back to the start page open the game list of the app instead.
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href]");
    if (a && /^(\.\.\/?|\/)$/.test(a.getAttribute("href"))) { e.preventDefault(); up({ spo: "menu", reason: "home" }); }
  }, true);
})();
