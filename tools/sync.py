#!/usr/bin/env python3
"""Copy the games from the Spieleabend add-on (HA-Games-Addon) into this offline app.

    python3 tools/sync.py ../HA-Games-Addon

Game rules (Python) go to py/, the game pages to games/<kind>/, the shared files to games/static/.
The pages stay unchanged except for two small additions: dark theme and embed.js, which connects them
to the offline shell instead of the server.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "HA-Games-Addon") / "spieleabend" / "app"
if not (SRC / "server.py").exists():
    sys.exit(f"Spieleabend nicht gefunden unter {SRC}")

PY = ROOT / "py"
GAMES = ROOT / "games"
PY.mkdir(exist_ok=True)
for f in sorted(SRC.glob("*.py")):
    if f.name != "server.py":
        shutil.copy2(f, PY / f.name)

shutil.rmtree(GAMES / "static", ignore_errors=True)
shutil.copytree(SRC / "static" / "shared", GAMES / "static")
for page in sorted((SRC / "static").glob("*/index.html")):
    kind = page.parent.name
    if kind == "shared":
        continue
    html = page.read_text(encoding="utf-8")
    html = html.replace('<html lang="de">', '<html lang="de" data-theme="dark">', 1)
    if '<script src="../static/common.js"></script>' in html:
        html = html.replace('<script src="../static/common.js"></script>',
                            '<script src="../static/embed.js"></script>\n  <script src="../static/common.js"></script>', 1)
    else:
        html = html.replace("</head>", '  <script src="../static/embed.js"></script>\n</head>', 1)
    (GAMES / kind).mkdir(parents=True, exist_ok=True)
    (GAMES / kind / "index.html").write_text(html, encoding="utf-8")

# Wortgitter loads its words from the server; offline they are a file next to the page.
def words(name: str) -> list[str]:
    return [w.strip() for w in (SRC / "data" / name).read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


(GAMES / "wortgitter" / "woerter.json").write_text(json.dumps(
    {"answers": words("wortgitter_loesungen.txt"), "valid": words("wortgitter_erlaubt.txt")}, ensure_ascii=False), encoding="utf-8")

# embed.js is ours: keep it (copytree above replaced games/static).
shutil.copy2(ROOT / "app" / "embed.js", GAMES / "static" / "embed.js")
print("Spiele übernommen:", ", ".join(sorted(p.parent.name for p in GAMES.glob("*/index.html") if p.parent.name != "static")))
