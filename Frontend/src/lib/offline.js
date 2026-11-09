const DATABASE = "daymark-offline";
const STORE = "snapshots";

async function database() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readSnapshot(apiUrl, kind = "calendar") {
  try {
    const db = await database();
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, "readonly");
      const request = transaction.objectStore(STORE).get(`${new URL(apiUrl).origin}:${kind}`);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
      transaction.onabort = () => { db.close(); reject(transaction.error); };
    });
  } catch { return null; }
}

export async function saveSnapshot(apiUrl, value, kind = "calendar") {
  try {
    const db = await database();
    const saved = { ...value, saved_at: new Date().toISOString() };
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(saved, `${new URL(apiUrl).origin}:${kind}`);
      transaction.oncomplete = () => { db.close(); resolve(); };
      transaction.onerror = transaction.onabort = () => { db.close(); reject(transaction.error); };
    });
    return saved.saved_at;
  } catch { return null; }
}

export async function registerOfflineApp() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" });
    await navigator.serviceWorker.ready;
    // Warm already-loaded application resources after the initial page load.
    // The worker only accepts public frontend assets, never API/auth responses.
    const urls = [location.origin + "/", ...performance.getEntriesByType("resource").map((entry) => entry.name)];
    (navigator.serviceWorker.controller || registration.active)?.postMessage({ type: "CACHE_APP_ASSETS", urls });
  } catch { /* Calendar snapshots still work when browser installation is unavailable. */ }
}
