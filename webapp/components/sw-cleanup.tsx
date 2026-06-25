"use client";

import { useEffect } from "react";

/**
 * In development the Serwist service worker is disabled, but a SW registered by a
 * previous production run / deployed session can linger in the browser and serve a
 * stale precached app shell — causing hydration mismatches. This unregisters any such
 * worker (and clears its caches) when not in production. No-op in production, where the
 * SW self-updates via skipWaiting + clientsClaim.
 */
export function SwCleanup() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.getRegistrations().then((regs) => {
      if (regs.length === 0) return;
      regs.forEach((r) => r.unregister());
      if (window.caches) caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
    });
  }, []);
  return null;
}
