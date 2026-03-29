const API_BASE = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "analyze-deepfake",
    title: "Analyze for Deepfake",
    contexts: ["image", "video"],
  });
});

async function fetchAsFile(url) {
  const response = await fetch(url, { mode: "cors" });
  const blob = await response.blob();
  const ext = (blob.type || "application/octet-stream").split("/")[1] || "bin";
  return new File([blob], `captured.${ext}`, { type: blob.type || "application/octet-stream" });
}

async function analyzeUrl(srcUrl) {
  const file = await fetchAsFile(srcUrl);
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Analysis failed with status ${res.status}`);
  }
  return res.json();
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "analyze-deepfake") return;
  if (!tab?.id || !info.srcUrl) return;

  try {
    const result = await analyzeUrl(info.srcUrl);
    chrome.tabs.sendMessage(tab.id, {
      type: "AUTHLAB_RESULT",
      payload: {
        srcUrl: info.srcUrl,
        result,
      },
    });
  } catch (err) {
    chrome.tabs.sendMessage(tab.id, {
      type: "AUTHLAB_ERROR",
      payload: { message: err.message || "Analysis failed" },
    });
  }
});
