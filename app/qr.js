/* Show a code as QR and scan codes with the camera (BarcodeDetector where available, jsQR otherwise). */
(function () {
  const QR = window.QR = {};

  QR.svg = text => {
    const qr = qrcode(0, "L");
    qr.addData(text, /^[0-9A-Z $%*+\-./:]*$/.test(text) ? "Alphanumeric" : "Byte");
    qr.make();
    const n = qr.getModuleCount(), m = 2;
    let path = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) path += `M${c + m} ${r + m}h1v1h-1z`;
    return `<svg xmlns="http://www.w3.org/2000/svg" class="qr" viewBox="0 0 ${n + 2 * m} ${n + 2 * m}" shape-rendering="crispEdges" role="img" aria-label="QR-Code">
      <rect width="100%" height="100%" fill="#fff"/><path d="${path}" fill="#111"/></svg>`;
  };

  /* Opens the camera in `box`, calls onCode(text) for the first code that passes `accept`. Returns stop(). */
  QR.scan = async (box, onCode, accept = () => true) => {
    box.innerHTML = `<video playsinline muted></video><div class="frame"></div><p class="scanhint">Halte die Kamera auf den Code</p>`;
    const video = box.querySelector("video");
    let stream, stopped = false, timer;
    const stop = () => { stopped = true; clearTimeout(timer); if (stream) stream.getTracks().forEach(t => t.stop()); };
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1280 } }, audio: false });
    } catch (err) {
      box.innerHTML = `<p class="scanerr">Kamera nicht verfügbar (${err.name === "NotAllowedError" ? "keine Erlaubnis" : "nicht gefunden"}).
        Nutze unten „Code einfügen“.</p>`;
      return stop;
    }
    video.srcObject = stream;
    await video.play().catch(() => {});
    const detector = "BarcodeDetector" in window ? new BarcodeDetector({ formats: ["qr_code"] }) : null;
    const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d", { willReadFrequently: true });
    const loop = async () => {
      if (stopped) return;
      try {
        let text = null;
        if (video.readyState >= 2) {
          if (detector) {
            const codes = await detector.detect(video);
            text = codes[0] && codes[0].rawValue;
          } else {
            const w = video.videoWidth, h = video.videoHeight, s = Math.min(1, 800 / Math.max(w, h));
            canvas.width = w * s; canvas.height = h * s;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const hit = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
            text = hit && hit.data;
          }
        }
        if (text && accept(text)) { stop(); if (navigator.vibrate) navigator.vibrate(60); onCode(text); return; }
      } catch {}
      timer = setTimeout(loop, 160);
    };
    loop();
    return stop;
  };

  /* Ask for the camera once, so the browser also shares the local network address (better WebRTC). */
  QR.warmUp = async () => {
    try { const s = await navigator.mediaDevices.getUserMedia({ video: true }); s.getTracks().forEach(t => t.stop()); return true; }
    catch { return false; }
  };
})();
