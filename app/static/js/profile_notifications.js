"use strict";

document.addEventListener("DOMContentLoaded", async function () {
    const addPushButton = document.getElementById("addPush");
    const cancelPushButton = document.getElementById("cancelPush");
    const pushSettingsDiv = document.getElementById("pushSettings");
    const pushDaysInput = document.getElementById("pushDays");
    const pushWithMaybeCheckbox = document.getElementById("pushWithMaybe");
    const savePushSettingsButton = document.getElementById("savePushSettings");

    cancelPushButton.disabled = true;
    let currentSubscription = null;

    // Function to parse days input
    function parseDaysInput(input) {
        if (!input || input.trim() === "") {
            return [1, 3, 7]; // Default values
        }
        return input.split(",").map(day => parseInt(day.trim())).filter(day => !isNaN(day));
    }

    // Function to fetch and display current push settings
    async function fetchPushSettings(endpoint) {
        try {
            const response = await fetch("/api/check-push-subscription", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({endpoint: endpoint}),
            });

            const result = await response.json();
            if (result.exists && result.settings) {
                pushDaysInput.value = result.settings.days_in_advance.join(", ");
                pushWithMaybeCheckbox.checked = result.settings.include_maybe_movies;
            } else {
                // Use default values
                pushDaysInput.value = "1, 3, 7";
                pushWithMaybeCheckbox.checked = true;
            }

            // Show settings UI
            pushSettingsDiv.style.display = "block";
        } catch (error) {
            console.error("Error fetching push settings:", error);
        }
    }

    if ("serviceWorker" in navigator && "PushManager" in window) {
        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();

            if (subscription) {
                currentSubscription = subscription;

                // Verify with the server
                const response = await fetch("/api/check-push-subscription", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({endpoint: subscription.endpoint}),
                });

                const result = await response.json();
                if (result.exists) {
                    addPushButton.disabled = true;
                    cancelPushButton.disabled = false;

                    // Fetch and display current settings
                    await fetchPushSettings(subscription.endpoint);
                } else {
                    addPushButton.disabled = false;
                    cancelPushButton.disabled = true;
                    pushSettingsDiv.style.display = "none";
                }
            } else {
                addPushButton.disabled = false;
                cancelPushButton.disabled = true;
                pushSettingsDiv.style.display = "none";
            }
        } catch (error) {
            console.error("Error checking push subscription:", error);
        }
    }

    addPushButton.addEventListener("click", async function () {
        if (Notification.permission === "granted") {
        } else if (Notification.permission === "denied") {
            alert("Push notifications are blocked. Please enable them in your browser settings.");
            return;
        } else {
            try {
                const permission = await Notification.requestPermission();
                if (permission !== "granted") {
                    console.warn("User denied push notifications.");
                    return;
                }
            } catch (error) {
                console.error("Error requesting notification permission:", error);
                return;
            }
        }

        try {
            const registration = await navigator.serviceWorker.ready;
            // Fetch the VAPID public key from the server
            const vapidResponse = await fetch("/api/vapid-public-key");
            const vapidData = await vapidResponse.json();

            if (!vapidData.success) {
                console.error("Error fetching VAPID public key:", vapidData.error);
                return;
            }

            const applicationServerKey = vapidData.publicKey;

            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            currentSubscription = subscription;

            // Get settings from UI
            const days = parseDaysInput(pushDaysInput.value);
            const includeMaybe = pushWithMaybeCheckbox.checked;

            // Create subscription data with settings
            const subscriptionData = {
                ...JSON.parse(JSON.stringify(subscription)),
                days_in_advance: days,
                include_maybe_movies: includeMaybe
            };

            const response = await fetch("/api/subscribe", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(subscriptionData),
            });

            const result = await response.json();

            addPushButton.disabled = true;
            cancelPushButton.disabled = false;

            // Update UI with returned settings
            if (result.success && result.settings) {
                pushDaysInput.value = result.settings.days_in_advance.join(", ");
                pushWithMaybeCheckbox.checked = result.settings.include_maybe_movies;
            }

            // Show settings UI
            pushSettingsDiv.style.display = "block";
        } catch (error) {
            console.error("Error subscribing to push notifications:", error);
        }
    });

    cancelPushButton.addEventListener("click", async function () {
        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();

            if (subscription) {
                await fetch("/api/unsubscribe", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({endpoint: subscription.endpoint}),
                });

                await subscription.unsubscribe();
                currentSubscription = null;
            }
        } catch (error) {
            console.error("Error canceling push subscription:", error);
        }

        addPushButton.disabled = false;
        cancelPushButton.disabled = true;
        pushSettingsDiv.style.display = "none";
    });

    savePushSettingsButton.addEventListener("click", async function() {
        if (!currentSubscription) {
            console.error("No active subscription found");
            return;
        }

        try {
            const days = parseDaysInput(pushDaysInput.value);
            const includeMaybe = pushWithMaybeCheckbox.checked;

            const response = await fetch("/api/update-push-settings", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    endpoint: currentSubscription.endpoint,
                    days_in_advance: days,
                    include_maybe_movies: includeMaybe
                }),
            });

            const result = await response.json();

            if (result.success) {
                alert("Push notification settings saved successfully!");

                // Update UI with returned settings
                if (result.settings) {
                    pushDaysInput.value = result.settings.days_in_advance.join(", ");
                    pushWithMaybeCheckbox.checked = result.settings.include_maybe_movies;
                }
            } else {
                console.error("Error updating push settings:", result.error);
                alert("Error saving settings: " + result.error);
            }
        } catch (error) {
            console.error("Error saving push notification settings:", error);
            alert("Error saving settings. Please try again.");
        }
    });
});
