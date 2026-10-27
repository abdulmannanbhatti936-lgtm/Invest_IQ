// InvestIQ web push service worker (Phase 7). FCM delivers data-only messages; this worker
// shows them with the title and one-line body the API rendered from the app's en/ur templates,
// and a tap opens the screen named in `link` (Design.md §19). It holds no keys or config.

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

const payloadOf = (event) => {
  try {
    const raw = event.data ? event.data.json() : {};
    return raw.data || raw;
  } catch {
    return {};
  }
};

self.addEventListener('push', (event) => {
  const data = payloadOf(event);
  if (!data.title) return;
  event.waitUntil(
    (async () => {
      await self.registration.showNotification(data.title, {
        body: data.body || '',
        tag: data.tag,
        icon: '/favicon.svg',
        data: { link: data.link || '/notifications', receivedAt: Date.now() },
      });
      // Open tabs refresh their bell at once instead of at the next poll
      const tabs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      tabs.forEach((tab) => tab.postMessage({ type: 'investiq-notification' }));
    })(),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || '/notifications';
  const target = new URL(link, self.location.origin).href;
  event.waitUntil(
    (async () => {
      const tabs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const open = tabs.find((tab) => new URL(tab.url).origin === self.location.origin);
      if (open) {
        await open.focus();
        return open.navigate(target);
      }
      return self.clients.openWindow(target);
    })(),
  );
});
