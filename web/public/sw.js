// Minimal service worker — makes the app installable (PWA) without altering
// network behaviour. The empty fetch handler satisfies the install criteria;
// requests are handled by the browser as normal. Add precaching later if an
// offline shell is wanted.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => { /* pass-through */ });
