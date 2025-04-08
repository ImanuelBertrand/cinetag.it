self.addEventListener("push", function (event) {
    if (event.data) {
        const notificationData = event.data.json(); // Parse the push message data

        event.waitUntil(
            self.registration.showNotification(notificationData.title, {
                body: notificationData.body,
                icon: notificationData.icon || "/static/icon.png",
                badge: "/static/badge.png",
                data: notificationData.url // Store URL to open on click
            })
        );
    }
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close(); // Close the notification

    if (event.notification.data) {
        event.waitUntil(
            clients.openWindow(event.notification.data) // Open link when clicked
        );
    }
});
