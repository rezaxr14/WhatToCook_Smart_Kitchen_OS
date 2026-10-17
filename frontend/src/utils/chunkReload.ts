/**
 * Recover from a stale tab after a deploy.
 *
 * Route chunks are content-hashed, so a tab opened before a deploy asks for chunk names that no longer exist and
 * the lazy import rejects (Vite fires `vite:preloadError`). Reload once to pick up the new index.html. A
 * sessionStorage timestamp stops a reload loop when the chunk is genuinely unreachable (offline, blocked); if
 * sessionStorage itself is unavailable we never reload.
 */
const KEY = 'wtc:chunk-reload-at';
const COOLDOWN_MS = 10_000;

export function reloadOnceOnChunkError(win: Window = window): void {
  win.addEventListener('vite:preloadError', (event) => {
    let last: number;
    try {
      last = Number(win.sessionStorage.getItem(KEY)) || 0;
      if (Date.now() - last < COOLDOWN_MS) return; // we just reloaded; let the error surface instead of looping
      win.sessionStorage.setItem(KEY, String(Date.now()));
    } catch {
      // Storage is blocked, so we could not remember having reloaded: a persistently unreachable chunk would
      // reload forever. Prefer the visible error over a possible loop.
      return;
    }
    event.preventDefault();
    win.location.reload();
  });
}
