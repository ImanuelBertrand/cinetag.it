"use strict";

/**
 * CineTagIt - Main namespace for the CineTagIt application
 */
window.CineTagIt = window.CineTagIt || {};

/**
 * Profile Notifications functionality
 */
CineTagIt.ProfileNotifications = {
  currentSubscription: null,

  /**
   * Parse days input string into array of integers
   * @param {string} input - Comma-separated list of days
   * @returns {Array} Array of integers
   */
  parseDaysInput: function (input) {
    if (!input || input.trim() === "") {
      return [0, 1, 3, 7]; // Default values
    }
    return input
      .split(",")
      .map((day) => parseInt(day.trim()))
      .filter((day) => !isNaN(day));
  },

  /**
   * Fetch and display current push settings
   * @param {string} endpoint - The subscription endpoint
   */
  fetchPushSettings: async function (endpoint) {
    try {
      const pushDaysInput = document.getElementById("pushDays");
      const pushWithMaybeCheckbox = document.getElementById("pushWithMaybe");
      const pushSettingsDiv = document.getElementById("pushSettings");

      const response = await fetch("/api/check-push-subscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: endpoint }),
      });

      const result = await response.json();
      if (result.exists && result.settings) {
        pushDaysInput.value = result.settings.days_in_advance.join(", ");
        pushWithMaybeCheckbox.checked = result.settings.include_maybe_movies;
      } else {
        // Use default values
        pushDaysInput.value = "0, 1, 3, 7";
        pushWithMaybeCheckbox.checked = true;
      }

      // Show settings UI
      pushSettingsDiv.style.display = "block";
    } catch (error) {
      console.error("Error fetching push settings:", error);
    }
  },

  /**
   * Initialize push notification functionality
   */
  init: async function () {
    const addPushButton = document.getElementById("addPush");
    const cancelPushButton = document.getElementById("cancelPush");
    const pushSettingsDiv = document.getElementById("pushSettings");
    const pushDaysInput = document.getElementById("pushDays");
    const pushWithMaybeCheckbox = document.getElementById("pushWithMaybe");
    const savePushSettingsButton = document.getElementById("savePushSettings");

    if (
      !addPushButton ||
      !cancelPushButton ||
      !pushSettingsDiv ||
      !pushDaysInput ||
      !pushWithMaybeCheckbox ||
      !savePushSettingsButton
    ) {
      console.warn("Push notification elements not found in the DOM");
      return;
    }

    cancelPushButton.disabled = true;

    if ("serviceWorker" in navigator && "PushManager" in window) {
      try {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();

        if (subscription) {
          this.currentSubscription = subscription;

          // Verify with the server
          const response = await fetch("/api/check-push-subscription", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ endpoint: subscription.endpoint }),
          });

          const result = await response.json();
          if (result.exists) {
            addPushButton.disabled = true;
            cancelPushButton.disabled = false;

            // Fetch and display current settings
            await this.fetchPushSettings(subscription.endpoint);
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

    // Add event listeners
    this.addEventListeners(addPushButton, cancelPushButton, savePushSettingsButton);

    // Render the unified list of every channel the user owns
    await this.loadChannels();
  },

  /**
   * Load and render every notification channel the user owns.
   */
  loadChannels: async function () {
    const container = document.getElementById("notificationChannels");
    if (!container) {
      return;
    }

    try {
      const endpoint = this.currentSubscription ? this.currentSubscription.endpoint : null;
      const url = endpoint
        ? `/api/notification-channels?endpoint=${encodeURIComponent(endpoint)}`
        : "/api/notification-channels";
      const response = await fetch(url);
      const result = await response.json();

      if (!result.success) {
        container.textContent = "Could not load your notification channels.";
        return;
      }

      this.renderChannels(container, result.channels);
    } catch (error) {
      console.error("Error loading notification channels:", error);
      container.textContent = "Could not load your notification channels.";
    }
  },

  /**
   * Render the channel rows into the container.
   */
  renderChannels: function (container, channels) {
    container.textContent = "";

    if (!channels.length) {
      container.textContent = "No notification channels yet.";
      return;
    }

    channels.forEach((channel) => {
      const row = document.createElement("div");
      row.className = "channel-row";
      row.dataset.channelId = channel.id;

      const name =
        channel.mode === "email"
          ? "Email"
          : channel.device_label + (channel.is_current_device ? " (this device)" : "");

      const title = document.createElement("div");
      title.className = "channel-title";
      title.textContent = name;
      row.appendChild(title);

      if (channel.disabled_reason === "expired") {
        const warning = document.createElement("div");
        warning.className = "channel-warning";
        warning.textContent =
          "This device stopped receiving notifications — re-enable notifications on that device.";
        row.appendChild(warning);
      }

      const controls = document.createElement("div");
      controls.className = "channel-controls";

      // Enabled toggle
      const enabledLabel = document.createElement("label");
      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.className = "channel-enabled";
      enabled.checked = channel.enabled;
      enabledLabel.appendChild(enabled);
      enabledLabel.appendChild(document.createTextNode(" Enabled"));
      controls.appendChild(enabledLabel);

      // Days-in-advance field
      const daysLabel = document.createElement("label");
      daysLabel.appendChild(document.createTextNode("When: "));
      const days = document.createElement("input");
      days.type = "text";
      days.className = "channel-days";
      days.value = (channel.days_in_advance || []).join(", ");
      days.placeholder = "0, 1, 3, 7";
      daysLabel.appendChild(days);
      controls.appendChild(daysLabel);

      // Include-maybe checkbox
      const maybeLabel = document.createElement("label");
      const maybe = document.createElement("input");
      maybe.type = "checkbox";
      maybe.className = "channel-maybe";
      maybe.checked = channel.include_maybe_movies;
      maybeLabel.appendChild(maybe);
      maybeLabel.appendChild(document.createTextNode(" Include 'Maybe'"));
      controls.appendChild(maybeLabel);

      const save = document.createElement("button");
      save.type = "button";
      save.className = "channel-save";
      save.textContent = "Save";
      save.addEventListener("click", () => this.saveChannel(row));
      controls.appendChild(save);

      row.appendChild(controls);
      container.appendChild(row);
    });
  },

  /**
   * Persist a single channel row via the channel API.
   */
  saveChannel: async function (row) {
    const channelId = row.dataset.channelId;
    const enabled = row.querySelector(".channel-enabled").checked;
    const includeMaybe = row.querySelector(".channel-maybe").checked;
    const days = this.parseDaysInput(row.querySelector(".channel-days").value);

    try {
      const response = await fetch(`/api/notification-channels/${channelId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
        },
        body: JSON.stringify({
          enabled: enabled,
          days_in_advance: days,
          include_maybe_movies: includeMaybe,
        }),
      });

      const result = await response.json();
      if (result.success) {
        CineTagIt.UI.displayMessage("Channel updated.", "success");
        // Refresh so re-enabled channels drop their expiry warning
        await this.loadChannels();
      } else {
        CineTagIt.UI.displayMessage(result.error || "Error updating channel.", "danger");
      }
    } catch (error) {
      console.error("Error updating channel:", error);
      CineTagIt.UI.displayMessage("Error updating channel.", "danger");
    }
  },

  /**
   * Add event listeners to buttons
   */
  addEventListeners: function (addPushButton, cancelPushButton, savePushSettingsButton) {
    addPushButton.addEventListener("click", this.handleAddPush.bind(this));
    cancelPushButton.addEventListener("click", this.handleCancelPush.bind(this));
    savePushSettingsButton.addEventListener("click", this.handleSaveSettings.bind(this));
  },

  /**
   * Handle add push button click
   */
  handleAddPush: async function () {
    const pushDaysInput = document.getElementById("pushDays");
    const pushWithMaybeCheckbox = document.getElementById("pushWithMaybe");
    const pushSettingsDiv = document.getElementById("pushSettings");
    const addPushButton = document.getElementById("addPush");
    const cancelPushButton = document.getElementById("cancelPush");

    if (Notification.permission === "granted") {
    } else if (Notification.permission === "denied") {
      CineTagIt.UI.displayMessage(
        "Push notifications are blocked. Please enable them in your browser settings.",
        "warning",
      );
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
        applicationServerKey: applicationServerKey,
      });

      this.currentSubscription = subscription;

      // Get settings from UI
      const days = this.parseDaysInput(pushDaysInput.value);
      const includeMaybe = pushWithMaybeCheckbox.checked;

      // Create subscription data with settings
      const subscriptionData = {
        ...JSON.parse(JSON.stringify(subscription)),
        days_in_advance: days,
        include_maybe_movies: includeMaybe,
      };

      const response = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
  },

  /**
   * Handle cancel push button click
   */
  handleCancelPush: async function () {
    const addPushButton = document.getElementById("addPush");
    const cancelPushButton = document.getElementById("cancelPush");
    const pushSettingsDiv = document.getElementById("pushSettings");

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await fetch("/api/unsubscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });

        await subscription.unsubscribe();
        this.currentSubscription = null;
      }
    } catch (error) {
      console.error("Error canceling push subscription:", error);
    }

    addPushButton.disabled = false;
    cancelPushButton.disabled = true;
    pushSettingsDiv.style.display = "none";
  },

  /**
   * Handle save settings button click
   */
  handleSaveSettings: async function () {
    const pushDaysInput = document.getElementById("pushDays");
    const pushWithMaybeCheckbox = document.getElementById("pushWithMaybe");

    if (!this.currentSubscription) {
      console.error("No active subscription found");
      return;
    }

    try {
      const days = this.parseDaysInput(pushDaysInput.value);
      const includeMaybe = pushWithMaybeCheckbox.checked;

      const response = await fetch("/api/update-push-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint: this.currentSubscription.endpoint,
          days_in_advance: days,
          include_maybe_movies: includeMaybe,
        }),
      });

      const result = await response.json();

      if (result.success) {
        CineTagIt.UI.displayMessage("Push notification settings saved successfully!", "success");

        // Update UI with returned settings
        if (result.settings) {
          pushDaysInput.value = result.settings.days_in_advance.join(", ");
          pushWithMaybeCheckbox.checked = result.settings.include_maybe_movies;
        }
      } else {
        console.error("Error updating push settings:", result.error);
        CineTagIt.UI.displayMessage("Error saving settings: " + result.error, "danger");
      }
    } catch (error) {
      console.error("Error saving push notification settings:", error);
      CineTagIt.UI.displayMessage("Error saving settings. Please try again.", "danger");
    }
  },
};

// Register the module's initialization function
CineTagIt.modules = CineTagIt.modules || {};
CineTagIt.modules.ProfileNotifications = function () {
  CineTagIt.ProfileNotifications.init();
};
