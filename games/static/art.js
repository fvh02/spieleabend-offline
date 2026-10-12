/* Small illustrations for the games that are not card games (start page tiles and game lobbies).
 * ART.<name> is an SVG string; elements with data-art="<name>" are filled automatically. */
(function () {
  const defs = (id, a, b) => `<linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
  const svg = (body, grads = "") => `<svg class="art" viewBox="0 0 220 120" role="img" aria-hidden="true"><defs>${grads}
    <filter id="sh" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#140a3c" flood-opacity=".28"/></filter></defs>${body}</svg>`;
  const tile = (x, y, s, fill, letter, rot = 0) =>
    `<g transform="translate(${x} ${y}) rotate(${rot} ${s / 2} ${s / 2})" filter="url(#sh)"><rect width="${s}" height="${s}" rx="${s * .2}" fill="${fill}"/>
     <text x="${s / 2}" y="${s * .7}" text-anchor="middle" font-size="${s * .56}" font-weight="850" fill="#fff" font-family="Inter,system-ui,sans-serif">${letter}</text></g>`;
  const bubble = (x, y, w, h, fill, text, tail = "left", color = "#1e1b3a", size = 13) => {
    const tx = tail === "left" ? x + 16 : x + w - 16, dir = tail === "left" ? -1 : 1;
    return `<g filter="url(#sh)"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2.4}" fill="${fill}"/>
      <path d="M${tx - 6} ${y + h - 1} L${tx + dir * 8} ${y + h + 11} L${tx + 8} ${y + h - 1} Z" fill="${fill}"/></g>
      <text x="${x + w / 2}" y="${y + h / 2 + size * .36}" text-anchor="middle" font-size="${size}" font-weight="750" fill="${color}" font-family="Inter,system-ui,sans-serif">${text}</text>`;
  };
  const face = (cx, cy, r, grad, letter) => `<g filter="url(#sh)"><circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${grad})"/></g>
    <text x="${cx}" y="${cy + r * .36}" text-anchor="middle" font-size="${r * .95}" font-weight="850" fill="#fff" font-family="Inter,system-ui,sans-serif">${letter}</text>`;

  window.ART = {
    galgenraten: svg(`
      <g stroke="currentColor" stroke-width="5" stroke-linecap="round" fill="none" opacity=".85">
        <path d="M18 108 H78 M34 108 V14 H74 M34 34 L52 14"/>
      </g>
      <path d="M74 14 V30" stroke="#d97706" stroke-width="3" stroke-linecap="round"/>
      <circle cx="74" cy="40" r="10" fill="none" stroke="url(#gg)" stroke-width="4"/>
      <path d="M74 50 V72 M74 58 L64 66 M74 58 L84 66" stroke="url(#gg)" stroke-width="4" stroke-linecap="round" fill="none"/>
      ${tile(104, 74, 24, "url(#ga)", "G", -6)}${tile(132, 74, 24, "url(#gb)", "A", 4)}
      <rect x="160" y="96" width="22" height="4" rx="2" fill="currentColor" opacity=".45"/>
      <rect x="186" y="96" width="22" height="4" rx="2" fill="currentColor" opacity=".45"/>
      ${tile(150, 22, 30, "url(#gc)", "?", 10)}`,
      defs("ga", "#a78bfa", "#5b21b6") + defs("gb", "#f472b6", "#9d174d") + defs("gc", "#60a5fa", "#1e40af") + defs("gg", "#f472b6", "#a78bfa")),

    wortgitter: svg(
      ["T", "R", "A", "U", "M"].map((l, i) => tile(29 + i * 33, 14, 29, ["#6b7280", "#d97706", "#6b7280", "#6b7280", "#059669"][i], l)).join("") +
      ["W", "O", "R", "T", "E"].map((l, i) => tile(29 + i * 33, 50, 29, "#059669", l)).join("") +
      [0, 1, 2, 3, 4].map(i => `<rect x="${29 + i * 33}" y="86" width="29" height="29" rx="6" fill="none" stroke="currentColor" stroke-opacity=".3" stroke-width="2"/>`).join("")),

    schnellmaler: svg(`
      <g filter="url(#sh)"><rect x="26" y="10" width="128" height="94" rx="12" fill="#fff"/></g>
      <circle cx="122" cy="34" r="12" fill="none" stroke="#f59e0b" stroke-width="4"/>
      <path d="M122 14 v-2 M140 34 h3 M104 34 h-3 M135 21 l2 -2 M109 21 l-2 -2" stroke="#f59e0b" stroke-width="3" stroke-linecap="round"/>
      <path d="M46 88 V60 L70 42 L94 60 V88 Z" fill="none" stroke="#7c3aed" stroke-width="4" stroke-linejoin="round"/>
      <path d="M64 88 V72 H76 V88" fill="none" stroke="#ec4899" stroke-width="4" stroke-linejoin="round"/>
      <path d="M36 94 C60 88 110 98 146 90" stroke="#10b981" stroke-width="4" fill="none" stroke-linecap="round"/>
      <g transform="translate(150 30) rotate(35)" filter="url(#sh)">
        <rect x="0" y="0" width="14" height="66" rx="3" fill="url(#mp)"/><path d="M0 66 L7 82 L14 66 Z" fill="#fcd5b5"/><path d="M4.5 76 L7 82 L9.5 76 Z" fill="#1e1b3a"/>
        <rect x="0" y="-8" width="14" height="10" rx="3" fill="#fb7185"/></g>
      ${[["#ef4444", 182, 100], ["#facc15", 196, 88], ["#22c55e", 204, 104]].map(([c, x, y]) => `<circle cx="${x}" cy="${y}" r="6" fill="${c}"/>`).join("")}`,
      defs("mp", "#a78bfa", "#ec4899")),

    kritzelpost: svg(`
      ${bubble(6, 14, 66, 30, "#fff", "Ein Hund …", "left", "#1e1b3a", 11)}
      <path d="M76 36 q10 -10 22 0" stroke="currentColor" stroke-opacity=".55" stroke-width="3" fill="none" stroke-linecap="round"/>
      <g filter="url(#sh)" transform="rotate(-4 130 60)"><rect x="98" y="30" width="62" height="54" rx="8" fill="#fff"/></g>
      <g transform="rotate(-4 130 60)" stroke="#7c3aed" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="128" cy="62" rx="16" ry="10"/><circle cx="146" cy="52" r="7"/><path d="M116 70 v8 M138 70 v8 M112 60 q-6 -6 -2 -12"/></g>
      <path d="M160 86 q12 10 22 -2" stroke="currentColor" stroke-opacity=".55" stroke-width="3" fill="none" stroke-linecap="round"/>
      ${bubble(140, 88, 74, 26, "url(#kb)", "Eine Wurst?", "right", "#fff", 11)}
      <path d="M96 36 l-6 -2 l2 6" stroke="currentColor" stroke-opacity=".55" stroke-width="3" fill="none" stroke-linecap="round"/>`,
      defs("kb", "#f472b6", "#a78bfa")),

    schaetzmeister: svg(`
      <path d="M14 86 H206" stroke="currentColor" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>
      ${[14, 50, 86, 122, 158, 194].map(x => `<path d="M${x} 80 V92" stroke="currentColor" stroke-opacity=".4" stroke-width="3" stroke-linecap="round"/>`).join("")}
      ${[[42, "sa", "A", 54], [96, "sb", "B", 40], [168, "sc", "C", 58]].map(([x, g, l, y]) =>
        `<path d="M${x} ${y + 12} V84" stroke="currentColor" stroke-opacity=".35" stroke-width="2" stroke-dasharray="3 3"/>${face(x, y, 13, g, l)}`).join("")}
      <g filter="url(#sh)"><path d="M120 84 V20" stroke="#10b981" stroke-width="4" stroke-linecap="round"/><path d="M120 20 H150 L142 30 L150 40 H120 Z" fill="url(#sd)"/></g>
      <text x="132" y="34" text-anchor="middle" font-size="12" font-weight="850" fill="#fff" font-family="Inter,system-ui,sans-serif">✓</text>
      <text x="120" y="112" text-anchor="middle" font-size="14" font-weight="850" fill="currentColor" font-family="Inter,system-ui,sans-serif">8.849 m</text>`,
      defs("sa", "#60a5fa", "#4338ca") + defs("sb", "#fb7185", "#be123c") + defs("sc", "#fbbf24", "#b45309") + defs("sd", "#34d399", "#047857")),

    werwuerde: svg(`
      ${bubble(48, 4, 124, 28, "#fff", "Wer würde eher …?", "left", "#1e1b3a", 12)}
      ${[[50, "wa", "L", 26], [110, "wb", "M", 52], [170, "wc", "T", 14]].map(([x, g, l, h]) => `
        <rect x="${x - 15}" y="${108 - h}" width="30" height="${h}" rx="6" fill="url(#${g})" opacity=".35"/>
        ${face(x, 78 - (x === 110 ? 6 : 0), x === 110 ? 19 : 15, g, l)}`).join("")}
      <path d="M98 40 L104 48 L110 38 L116 48 L122 40 L120 52 H100 Z" fill="#facc15" filter="url(#sh)"/>`,
      defs("wa", "#60a5fa", "#4338ca") + defs("wb", "#f472b6", "#be185d") + defs("wc", "#34d399", "#047857")),

    luegenbaron: svg(`
      ${bubble(8, 10, 92, 32, "#fff", "Wahrheit?", "left", "#059669", 13)}
      ${bubble(120, 30, 92, 32, "url(#la)", "Gelogen!", "right", "#fff", 13)}
      <g filter="url(#sh)"><circle cx="78" cy="88" r="22" fill="url(#lb)"/></g>
      <circle cx="71" cy="84" r="3.2" fill="#1e1b3a"/><circle cx="85" cy="84" r="3.2" fill="#1e1b3a"/>
      <path d="M70 96 q8 6 16 0" stroke="#1e1b3a" stroke-width="2.6" fill="none" stroke-linecap="round"/>
      <path d="M90 88 L150 92 L92 93 Z" fill="#f59e0b" filter="url(#sh)"/>
      <path d="M58 70 q4 -14 20 -12 q16 -2 20 12" fill="#4c1d95"/><rect x="62" y="56" width="32" height="14" rx="4" fill="#4c1d95"/>
      <rect x="56" y="68" width="44" height="5" rx="2.5" fill="#312e81"/>`,
      defs("la", "#fb7185", "#be123c") + defs("lb", "#fde68a", "#fdba74")),

    punchline: svg(`
      <g filter="url(#sh)"><rect x="92" y="14" width="34" height="52" rx="17" fill="url(#pa)"/></g>
      ${[24, 32, 40, 48].map(y => `<path d="M96 ${y} H122" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>`).join("")}
      <path d="M82 50 q0 30 27 30 q27 0 27 -30" stroke="currentColor" stroke-opacity=".7" stroke-width="5" fill="none" stroke-linecap="round"/>
      <path d="M109 80 V108 M90 110 H128" stroke="currentColor" stroke-opacity=".7" stroke-width="5" stroke-linecap="round"/>
      ${bubble(8, 18, 66, 30, "#fff", "Haha!", "right", "#db2777", 15)}
      ${bubble(146, 40, 66, 30, "url(#pb)", "😂 😂", "left", "#fff", 15)}
      <text x="40" y="98" text-anchor="middle" font-size="26" font-family="system-ui">🎤</text>`,
      defs("pa", "#a78bfa", "#4c1d95") + defs("pb", "#fbbf24", "#d97706")),

    nochnie: svg(`
      ${bubble(30, 6, 160, 30, "#fff", "Ich hab noch nie …", "left", "#1e1b3a", 13)}
      ${[[62, -10], [110, 0], [158, 10]].map(([x, r], i) => `<g transform="rotate(${r} ${x} 86)" filter="url(#sh)">
        <path d="M${x - 20} 56 h40 l-4 52 q0 6 -6 6 h-20 q-6 0 -6 -6 Z" fill="url(#n${i})"/>
        <path d="M${x - 20} 56 h40 v-6 q-6 -8 -20 -6 q-14 -2 -20 6 Z" fill="#fff"/>
        <circle cx="${x - 8}" cy="51" r="6" fill="#fff"/><circle cx="${x + 6}" cy="50" r="7" fill="#fff"/></g>`).join("")}
      <text x="110" y="92" text-anchor="middle" font-size="16" font-weight="900" fill="#fff" font-family="Inter,system-ui,sans-serif">🍻</text>`,
      defs("n0", "#fbbf24", "#d97706") + defs("n1", "#fcd34d", "#b45309") + defs("n2", "#fbbf24", "#c2410c")),

    wahrheit: svg(`
      <g filter="url(#sh)" transform="rotate(-8 70 64)"><rect x="22" y="18" width="96" height="92" rx="14" fill="url(#wa1)"/></g>
      <text x="70" y="70" text-anchor="middle" font-size="34" font-family="system-ui" transform="rotate(-8 70 64)">😇</text>
      <text x="70" y="98" text-anchor="middle" font-size="12" font-weight="850" fill="#fff" font-family="Inter,system-ui,sans-serif" transform="rotate(-8 70 64)">WAHRHEIT</text>
      <g filter="url(#sh)" transform="rotate(8 150 64)"><rect x="102" y="18" width="96" height="92" rx="14" fill="url(#wa2)"/></g>
      <text x="150" y="70" text-anchor="middle" font-size="34" font-family="system-ui" transform="rotate(8 150 64)">🍺</text>
      <text x="150" y="98" text-anchor="middle" font-size="12" font-weight="850" fill="#fff" font-family="Inter,system-ui,sans-serif" transform="rotate(8 150 64)">TRINKEN</text>
      <g filter="url(#sh)"><circle cx="110" cy="62" r="17" fill="#fff"/></g>
      <text x="110" y="68" text-anchor="middle" font-size="14" font-weight="900" fill="#7c3aed" font-family="Inter,system-ui,sans-serif">oder</text>`,
      defs("wa1", "#34d399", "#047857") + defs("wa2", "#fbbf24", "#c2410c")),

    trinklotto: svg(`
      ${[["#ef4444", 36, 30], ["#3b82f6", 70, 18], ["#22c55e", 104, 28], ["#eab308", 60, 52], ["#a855f7", 96, 58], ["#f97316", 30, 72]].map(([c, x, y], i) =>
        `<g filter="url(#sh)"><circle cx="${x}" cy="${y}" r="15" fill="${c}"/></g><text x="${x}" y="${y + 6}" text-anchor="middle" font-size="15" font-weight="900" fill="#fff" font-family="Inter,system-ui,sans-serif">${i + 1}</text>`).join("")}
      <text x="72" y="108" text-anchor="middle" font-size="22" font-family="system-ui">🐱 🦊 🐸</text>
      ${bubble(124, 36, 92, 44, "url(#tl)", "Blau trinkt!", "left", "#fff", 13)}`,
      defs("tl", "#3b82f6", "#4338ca")),
  };
  const fill = () => document.querySelectorAll("[data-art]").forEach(el => { el.innerHTML = window.ART[el.dataset.art] || ""; });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fill); else fill();
})();
