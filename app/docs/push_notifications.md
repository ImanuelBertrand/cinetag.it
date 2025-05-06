# Push Notifications in CineTagIt

## Overview

CineTagIt's push notification system allows users to receive timely alerts about upcoming movie releases directly in their browser, even when they're not actively using the application. This feature complements the existing email notification system, giving users more flexibility in how they stay informed about their anticipated movies.

## Components

The push notification system consists of several components:

1. **Service Worker (sw.js)**: Handles incoming push messages and displays notifications to the user.
2. **Client-side JavaScript (profile_notifications.js)**: Manages push notification subscriptions in the user profile.
3. **Base Application (base.js)**: Registers the service worker during application initialization.
4. **Server-side Models**: Store notification preferences and subscription information.
5. **Server-side Utilities**: Schedule and send notifications.
6. **API Endpoints**: Handle subscription management.

## User Flow

1. User visits their notification settings page.
2. User enables push notifications and selects preferences (days before release, whether to include "maybe" movies).
3. Browser requests permission to show notifications.
4. If granted, a subscription is created and sent to the server.
5. The server stores the subscription and schedules notifications based on user preferences.
6. When a notification is due, the server sends a push message to the user's browser.
7. The service worker receives the push message and displays a notification.
8. When the user clicks the notification, they are taken to the relevant movie page.

## Technical Implementation

### Service Worker (sw.js)

The service worker handles two main events:

1. **push**: Receives push messages from the server, parses the data, and displays a notification.
2. **notificationclick**: Handles notification clicks by closing the notification and opening the URL provided in the notification data.

```javascript
self.addEventListener("push", function (event) {
    if (event.data) {
        const notificationData = event.data.json();

        event.waitUntil(
            self.registration.showNotification(notificationData.title, {
                body: notificationData.body,
                icon: notificationData.icon || "/static/icon.png",
                badge: "/static/badge.png",
                data: notificationData.url
            })
        );
    }
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();

    if (event.notification.data) {
        event.waitUntil(
            clients.openWindow(event.notification.data)
        );
    }
});
```

### Client-side Subscription Management (profile_notifications.js)

The profile_notifications.js file handles:

1. **Checking existing subscriptions**: Verifies if the user already has a push subscription.
2. **Creating new subscriptions**: Requests notification permission and creates a push subscription.
3. **Sending subscriptions to the server**: Sends the subscription details to the server for storage.
4. **Canceling subscriptions**: Allows users to unsubscribe from push notifications.

```javascript
// Check for existing subscription
const subscription = await registration.pushManager.getSubscription();
if (subscription) {
    // Verify with server
    const response = await fetch("/check-push-subscription", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({endpoint: subscription.endpoint}),
    });
}

// Create new subscription
const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: "YOUR_PUBLIC_VAPID_KEY_HERE"
});

// Send to server
await fetch("/subscribe", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(subscription),
});

// Cancel subscription
await fetch("/unsubscribe", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({endpoint: subscription.endpoint}),
});
await subscription.unsubscribe();
```

### Service Worker Registration (base.js)

The base.js file registers the service worker during application initialization:

```javascript
navigator.serviceWorker.register("/sw.js")
.catch(error => {
    console.error("Service Worker registration failed:", error);
});
```

### Server-side Models

Two main models are used for notifications:

1. **NotificationChannel**: Stores user preferences for notifications.
   - `user_id`: The user who owns this channel
   - `enabled`: Whether the channel is enabled
   - `days_in_advance`: Days before release to send notifications
   - `mode`: Type of notification ("email" or "push")
   - `notification_data`: Push subscription details
   - `include_maybe_movies`: Whether to include "maybe" movies

2. **Notification**: Represents a specific notification to be sent.
   - `user_id`: The user to notify
   - `channel_id`: The notification channel to use
   - `movie_id`: The movie the notification is about
   - `days_in_advance`: How many days before release
   - `is_sent`: Whether the notification has been sent
   - `scheduled_at`: When to send the notification
   - `sent_at`: When the notification was sent

### Server-side Utilities

The notification system uses several utility functions:

1. **cron_setup_notifications()**: Sets up notifications for all channels.
2. **setup_notifications()**: Creates notification records for upcoming movie releases.
3. **cron_send_notifications()**: Sends all scheduled notifications that are due.
4. **send_notification()**: Dispatches a notification to the appropriate sending method.
5. **send_push_notification()**: Sends push notifications to the user's browser.

### API Endpoints

Four API endpoints are used for push notifications:

1. **/check-push-subscription**: Verifies if a subscription exists on the server.
2. **/subscribe**: Stores a new push subscription.
3. **/update-push-settings**: Updates notification preferences for an existing subscription.
4. **/unsubscribe**: Removes a push subscription.

## User Interface

The notification settings page allows users to:

1. Enable/disable push notifications
2. Specify how many days before release to receive notifications
3. Choose whether to include "maybe" movies in notifications

## Security Considerations

1. **VAPID Keys**: Web Push requires VAPID (Voluntary Application Server Identification) keys for authentication.
2. **User Consent**: Push notifications require explicit user permission.
3. **Data Protection**: Subscription endpoints should be treated as sensitive user data.

## Future Enhancements

1. **Rich Notifications**: Add images and action buttons to notifications.
2. **Notification Grouping**: Group multiple notifications about the same movie.
3. **Custom Notification Sounds**: Allow users to select custom sounds.
4. **Notification Preferences**: More granular control over notification content and frequency.

## Implementation Status

The push notification feature is fully implemented and includes the following components:

- Service worker for handling push messages and notification clicks
- Client-side JavaScript for managing subscriptions
- Service worker registration in the base application
- Server-side models for storing notification preferences
- API endpoints for subscription management
- Server-side functionality for sending push notifications
- Integration with the existing notification scheduling system
