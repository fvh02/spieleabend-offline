/* Connections between the phones: WebRTC data channels, paired by scanning QR codes.
 * No server and no internet: the codes carry everything the two phones need to find each other
 * on the same Wi-Fi or hotspot. */
(function () {
  const Net = window.Net = {};
  const PREFIX = "SPO1";
  const CHUNK = 16000;

  // ---------- pairing codes: JSON → deflate → Base45 (fits the QR alphanumeric mode) ----------
  const B45 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";
  function b45encode(bytes) {
    let out = "";
    for (let i = 0; i < bytes.length; i += 2) {
      if (i + 1 < bytes.length) {
        let x = bytes[i] * 256 + bytes[i + 1];
        out += B45[x % 45]; x = Math.floor(x / 45); out += B45[x % 45]; out += B45[Math.floor(x / 45)];
      } else {
        const x = bytes[i]; out += B45[x % 45] + B45[Math.floor(x / 45)];
      }
    }
    return out;
  }
  function b45decode(str) {
    const vals = [...str].map(c => { const v = B45.indexOf(c); if (v < 0) throw new Error("Ungültiger Code"); return v; });
    const out = [];
    for (let i = 0; i < vals.length; i += 3) {
      if (i + 2 < vals.length) { const x = vals[i] + vals[i + 1] * 45 + vals[i + 2] * 2025; out.push(x >> 8, x & 255); }
      else out.push(vals[i] + vals[i + 1] * 45);
    }
    return new Uint8Array(out);
  }
  async function pipe(bytes, stream) {
    const blob = new Blob([bytes]).stream().pipeThrough(stream);
    return new Uint8Array(await new Response(blob).arrayBuffer());
  }
  const canZip = typeof CompressionStream === "function";
  Net.encode = async obj => {
    const raw = new TextEncoder().encode(JSON.stringify(obj));
    return canZip ? PREFIX + "Z" + b45encode(await pipe(raw, new CompressionStream("deflate-raw")))
                  : PREFIX + "J" + b45encode(raw);
  };
  Net.decode = async code => {
    code = String(code || "").replace(/[\r\n\t]/g, "").replace(/^ +/, "").toUpperCase();  // spaces are part of Base45
    if (!code.startsWith(PREFIX)) throw new Error("Das ist kein Spieleabend-Code");
    const bytes = b45decode(code.slice(5));
    const raw = code[4] === "Z" ? await pipe(bytes, new DecompressionStream("deflate-raw")) : bytes;
    return JSON.parse(new TextDecoder().decode(raw));
  };

  // Only what the other side needs; keeps the QR code small.
  const slim = sdp => sdp.split("\r\n").filter(l => l && !/^a=(extmap|rtcp-fb|ssrc|msid)|^a=candidate:.* tcp /.test(l)).join("\r\n") + "\r\n";

  function gathered(pc, ms = 2500) {
    return new Promise(resolve => {
      if (pc.iceGatheringState === "complete") return resolve();
      const t = setTimeout(resolve, ms);
      pc.addEventListener("icegatheringstatechange", () => { if (pc.iceGatheringState === "complete") { clearTimeout(t); resolve(); } });
    });
  }

  // ---------- a channel that sends JSON of any size ----------
  class Link {
    constructor(pc, dc) {
      this.pc = pc; this.dc = dc; this.parts = {}; this.closed = false; this.queue = []; this._onmessage = null; this.onclose = null;
      dc.onmessage = e => this.receive(e.data);
      const end = () => { if (!this.closed) { this.closed = true; if (this.onclose) this.onclose(); } };
      dc.onclose = end;
      let grace = null;   // "disconnected" can recover (e.g. Wi-Fi hiccup); give it a few seconds
      pc.addEventListener("connectionstatechange", () => {
        const st = pc.connectionState;
        clearTimeout(grace);
        if (st === "failed" || st === "closed") end();
        else if (st === "disconnected") grace = setTimeout(() => { if (pc.connectionState !== "connected") end(); }, 5000);
      });
    }
    send(obj) {
      if (this.dc.readyState !== "open") return;
      const text = JSON.stringify(obj);
      if (text.length <= CHUNK) { this.dc.send(text); return; }
      const id = Math.random().toString(36).slice(2, 8), n = Math.ceil(text.length / CHUNK);
      for (let i = 0; i < n; i++) this.dc.send(JSON.stringify({ t: "chunk", id, i, n, p: text.slice(i * CHUNK, (i + 1) * CHUNK) }));
    }
    receive(text) {
      let msg; try { msg = JSON.parse(text); } catch { return; }
      if (msg.t === "chunk") {
        const box = this.parts[msg.id] || (this.parts[msg.id] = []);
        box[msg.i] = msg.p;
        if (box.filter(x => x !== undefined).length < msg.n) return;
        delete this.parts[msg.id];
        try { msg = JSON.parse(box.join("")); } catch { return; }
      }
      if (this._onmessage) this._onmessage(msg); else this.queue.push(msg);
    }
    close() { try { this.dc.close(); this.pc.close(); } catch {} }
    // Messages that arrive before anyone listens are kept until onmessage is set.
    set onmessage(fn) { this._onmessage = fn; while (fn && this.queue.length) fn(this.queue.shift()); }
    get onmessage() { return this._onmessage; }
  }

  const config = { iceServers: [] };   // no STUN/TURN: only the local network

  // ---------- host side: one offer per guest ----------
  Net.offer = async (hostName) => {
    const pc = new RTCPeerConnection(config);
    const dc = pc.createDataChannel("spieleabend", { ordered: true });
    await pc.setLocalDescription(await pc.createOffer());
    await gathered(pc);
    const id = Math.random().toString(36).slice(2, 8);
    const code = await Net.encode({ v: 1, t: "o", id, n: hostName, s: slim(pc.localDescription.sdp) });
    let resolveOpen;
    const opened = new Promise(r => resolveOpen = r);
    dc.onopen = () => resolveOpen(new Link(pc, dc));
    return {
      id, code, opened,
      async accept(answerCode) {
        const a = await Net.decode(answerCode);
        if (a.t !== "a") throw new Error("Das ist kein Antwort-Code");
        if (a.id !== id) throw new Error("Dieser Code gehört zu einer anderen Einladung");
        await pc.setRemoteDescription({ type: "answer", sdp: a.s });
        return a;   // { n: guest name, k: guest token }
      },
      cancel() { try { pc.close(); } catch {} },
    };
  };

  // ---------- guest side: answer the host's code ----------
  Net.answer = async (offerCode, me) => {
    const o = await Net.decode(offerCode);
    if (o.t !== "o") throw new Error("Bitte den Code des Gastgebers scannen");
    const pc = new RTCPeerConnection(config);
    let resolveOpen;
    const opened = new Promise(r => resolveOpen = r);
    pc.ondatachannel = e => { const dc = e.channel; dc.onopen = () => resolveOpen(new Link(pc, dc)); };
    await pc.setRemoteDescription({ type: "offer", sdp: o.s });
    await pc.setLocalDescription(await pc.createAnswer());
    await gathered(pc);
    const code = await Net.encode({ v: 1, t: "a", id: o.id, n: me.name, k: me.token, s: slim(pc.localDescription.sdp) });
    return { host: o.n, code, opened, cancel() { try { pc.close(); } catch {} } };
  };
})();
