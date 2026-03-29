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
  card.style.border = "1px solid rgba(255,255,255,.18)";
  card.innerHTML = `<strong style="display:block;font-size:14px">${title}</strong><div style="margin-top:6px;font-size:13px;line-height:1.42">${text}</div>`;
  host.prepend(card);

  setTimeout(() => card.remove(), 18000);
}

function esc(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function short(text, max = 280) {
  const t = String(text || "").trim().replace(/\s+/g, " ");
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}...`;
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "AUTHLAB_ERROR") {
    renderCard({ title: "VeriLens Forensics", text: msg.payload.message, bg: "#7a271a" });
    return;
  }

  if (msg.type === "AUTHLAB_RESULT") {
    const result = msg.payload.result;
    const confidence = (result.confidence_fake * 100).toFixed(1);
    const trust = (result.trust_score * 100).toFixed(1);
    const drift = (result.reality_drift_score * 100).toFixed(1);
    const top = [...result.factors].sort((a, b) => b.score - a.score).slice(0, 2);
    const summary = top.map((f) => `${f.name}: ${(f.score * 100).toFixed(1)}%`).join(" | ");
    const beginner = short(result.explanation?.beginner || "Explanation unavailable.");
    const policy = result.policy_decision?.action ? `Policy: ${result.policy_decision.action}` : "Policy: n/a";
    const reportUrl = result.report_id ? `https://ipcv-final.onrender.com/reports/${result.report_id}.json` : "";

    let text =
      `${summary}<br/>` +
      `Trust: ${trust}% | Reality Drift: ${drift}%<br/>` +
      `${policy}<br/><br/>` +
      `<em>${esc(beginner)}</em>`;

    if (reportUrl) {
      text += `<br/><br/><a href="${reportUrl}" target="_blank" rel="noreferrer" style="color:#fff;text-decoration:underline">Open forensic report</a>`;
    }

    renderCard({
      title: `Deepfake Suspicion: ${confidence}%`,
      text,
      bg: scoreTone(result.confidence_fake),
    });
  }
});
