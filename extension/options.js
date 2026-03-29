const DEFAULT_BACKEND = "https://ipcv-final.onrender.com";

const backendUrl = document.getElementById("backendUrl");
const saveBtn = document.getElementById("saveBtn");
const resetBtn = document.getElementById("resetBtn");
const status = document.getElementById("status");

function setStatus(text, isError = false) {
  status.textContent = text;
  status.style.color = isError ? "#b42318" : "#55585f";
}

function normalizeUrl(url) {
  return url.trim().replace(/\/$/, "");
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get(["backendUrl"]);
  backendUrl.value = settings.backendUrl || DEFAULT_BACKEND;
}

async function saveSettings() {
  const value = normalizeUrl(backendUrl.value);
  if (!value.startsWith("http://") && !value.startsWith("https://")) {
    setStatus("Backend URL must start with http:// or https://", true);
    return;
  }
  await chrome.storage.sync.set({ backendUrl: value });
  setStatus("Saved successfully.");
}

async function resetSettings() {
  await chrome.storage.sync.set({ backendUrl: DEFAULT_BACKEND });
  backendUrl.value = DEFAULT_BACKEND;
  setStatus("Reset to default backend URL.");
}

saveBtn.addEventListener("click", saveSettings);
resetBtn.addEventListener("click", resetSettings);

loadSettings().catch(() => setStatus("Failed to load settings.", true));
