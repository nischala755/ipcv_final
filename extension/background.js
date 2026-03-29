const DEFAULT_API_BASE = "https://ipcv-final.onrender.com";

async function getApiBase() {
  const settings = await chrome.storage.sync.get(["backendUrl"]);
  const value = settings.backendUrl || DEFAULT_API_BASE;
  return value.replace(/\/$/, "");
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["backendUrl"], (settings) => {
    if (!settings.backendUrl) {
      chrome.storage.sync.set({ backendUrl: DEFAULT_API_BASE });
    }
  });

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
  const apiBase = await getApiBase();
  const file = await fetchAsFile(srcUrl);
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${apiBase}/analyze?policy_profile=social`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Backend request failed (${res.status}). Check extension backend URL in Options.`);
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
      payload: { message: err.message || "Analysis failed. Open extension options and verify backend URL." },
    });
  }
});
