self.addEventListener("push", function (event) {
  if (event.data) {
    const notificationData = event.data.json(); // Parse the push message data

    event.waitUntil(
      self.registration.showNotification(notificationData.title, {
        body: notificationData.body,
        icon: notificationData.icon || "/static/img/icon.png",
        badge: "/static/img/badge.png",
        data: notificationData.url, // Store URL to open on click
      }),
    );
  }
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close(); // Close the notification

  const targetUrl = event.notification.data;
  if (!targetUrl) {
    return;
  }

  // Focus an already-open tab if we have one, otherwise open a new window.
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if ("focus" in client && "navigate" in client) {
          // navigate() rejects for clients this service worker doesn't
          // control (e.g. a tab opened before the SW activated) — fall back
          // to a new window so the movie page always opens.
          return client
            .navigate(targetUrl)
            .then((navigated) => (navigated || client).focus())
            .catch(() => clients.openWindow(targetUrl));
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
      return undefined;
    }),
  );
});
