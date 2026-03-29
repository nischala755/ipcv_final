export function registerPWA() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", async () => {
      try {
        await navigator.serviceWorker.register("/sw.js");
      } catch (err) {
        console.warn("Service worker registration failed", err);
      }
    });
  }
}
