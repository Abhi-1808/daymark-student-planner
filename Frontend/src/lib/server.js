export function apiOrigin(location, override) {
  if (override) return override.replace(/\/$/, "");
  // Separate Vite development/preview servers retain the desktop setup.
  // Compiled app + API share one origin in the local/phone launcher.
  return ["5173", "4173", "3000"].includes(location.port)
    ? `${location.protocol}//${location.hostname}:8000` : location.origin;
}

export function isDesktopHost(hostname) {
  return ["localhost", "127.0.0.1", "[::1]", "::1"].includes(hostname);
}
