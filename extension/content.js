function ensureHost() {
  let host = document.getElementById("authlab-overlay-host");
  if (host) return host;
  host = document.createElement("div");
  host.id = "authlab-overlay-host";
  host.style.position = "fixed";
  host.style.top = "16px";
  host.style.right = "16px";
  host.style.width = "320px";
  host.style.zIndex = "2147483647";
  host.style.fontFamily = "ui-sans-serif, system-ui, -apple-system";
  document.body.appendChild(host);
  return host;
}

function scoreTone(score) {
  if (score >= 0.75) return "#b42318";
  if (score >= 0.45) return "#b54708";
  return "#027a48";
}

function renderCard({ title, text, bg = "#111", color = "#fff" }) {
  const host = ensureHost();
  const card = document.createElement("div");
  card.style.background = bg;
  card.style.color = color;
  card.style.padding = "12px";
  card.style.borderRadius = "12px";
  card.style.marginBottom = "10px";
  card.style.boxShadow = "0 10px 24px rgba(0,0,0,.2)";
  card.innerHTML = `<strong>${title}</strong><div style="margin-top:6px;font-size:13px;line-height:1.35">${text}</div>`;
  host.prepend(card);

  setTimeout(() => card.remove(), 12000);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "AUTHLAB_ERROR") {
    renderCard({ title: "VeriLens Forensics", text: msg.payload.message, bg: "#7a271a" });
    return;
  }

  if (msg.type === "AUTHLAB_RESULT") {
    const result = msg.payload.result;
    const confidence = Math.round(result.confidence_fake * 100);
    const top = [...result.factors].sort((a, b) => b.score - a.score).slice(0, 2);
    const summary = top.map((f) => `${f.name}: ${Math.round(f.score * 100)}%`).join(" | ");

    renderCard({
      title: `Deepfake Suspicion: ${confidence}%`,
      text: `${summary}<br/>Reality Drift: ${Math.round(result.reality_drift_score * 100)}%`,
      bg: scoreTone(result.confidence_fake),
    });
  }
});
