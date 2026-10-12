/* The host's game engine: the Spieleabend rules (Python) running in Pyodide, in a worker thread.
 * Messages in:  {t: "call", id, fn, args}   Messages out: {t: "ready"} · {t: "out", list} · {t: "result", id, ...} */
importScripts("../vendor/pyodide/pyodide.js");

const FILES = ["common.py", "party.py", "wortschatz.py", "stapeljagd.py", "tiefpunkt.py", "kritzelpost.py", "farbrausch.py",
  "schnellmaler.py", "galgenraten.py", "imposter.py", "schaetzmeister.py", "werwuerde.py", "luegenbaron.py", "punchline.py",
  "nochnie.py", "wahrheit.py", "ringoffire.py", "trinklotto.py", "pyramide.py", "pferderennen.py", "offline_hub.py"];
let hub = null;

async function boot() {
  const py = await loadPyodide({ indexURL: new URL("../vendor/pyodide/", self.location).href });
  py.FS.mkdirTree("/home/pyodide/games");
  for (const f of FILES) {
    const res = await fetch(new URL(`../py/${f}`, self.location));
    if (!res.ok) throw new Error(`${f} fehlt`);
    py.FS.writeFile(`/home/pyodide/games/${f}`, await res.text());
  }
  py.runPython('import sys; sys.path.insert(0, "/home/pyodide/games"); import offline_hub');
  hub = py.pyimport("offline_hub").hub;
  postMessage({ t: "ready" });
  setInterval(() => emit(hub.tick()), 250);
}

function emit(json) {
  if (json && json !== "[]") postMessage({ t: "out", list: JSON.parse(json) });
}

onmessage = e => {
  const { fn, args = [], id } = e.data;
  if (!hub) return postMessage({ t: "result", id, error: "Die Spiele werden noch geladen" });
  try {
    let out;
    if (fn === "set_device" || fn === "remove_device") { hub[fn](...args); out = hub.flush_json(); }
    else out = hub[fn](...args);
    emit(out);
    postMessage({ t: "result", id, ok: true });
  } catch (err) {
    const msg = String(err && err.message || err).split("\n").filter(Boolean).pop();
    postMessage({ t: "result", id, error: msg });
  }
};

boot().catch(err => postMessage({ t: "failed", error: String(err && err.message || err) }));
