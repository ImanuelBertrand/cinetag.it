"use strict";

/**
 * CineTagIt - Main namespace for the CineTagIt application
 */
window.CineTagIt = window.CineTagIt || {};

/**
 * Object to store module initialization functions
 * @type {Object}
 */
CineTagIt.modules = new Proxy(CineTagIt.modules || {}, {
  set: function (target, property, value) {
    // Set the value on the target object
    target[property] = value;

    // If CineTagIt is already initialized, initialize this module immediately
    if (CineTagIt.initialized && typeof value === "function") {
      try {
        value();
      } catch (error) {
        console.error(`Error initializing late-loaded module '${property}':`, error);
      }
    }

    // Return true to indicate success
    return true;
  },
});

/**
 * Flag to track if CineTagIt has been initialized
 * @type {boolean}
 */
CineTagIt.initialized = false;

/**
 * Utility functions
 */
CineTagIt.Utils = {
  /**
   * Get CSRF token from cookies
   * @returns {string} CSRF token
   */
  getCsrfToken: function () {
    return CineTagIt.Utils._readCookie("csrf_access_token");
  },

  /**
   * Get refresh CSRF token from cookies (used when access token has expired
   * and the request must auth via the refresh path).
   * @returns {string} CSRF token
   */
  getRefreshCsrfToken: function () {
    return CineTagIt.Utils._readCookie("csrf_refresh_token");
  },

  _readCookie: function (name) {
    const cookies = document.cookie.split("; ");
    const prefix = name + "=";
    for (let i = 0; i < cookies.length; i++) {
      if (cookies[i].startsWith(prefix)) {
        return cookies[i].substring(prefix.length);
      }
    }
    return "";
  },

  /**
   * De-obfuscate an email address
   * @param {string} obfuscatedEmail - The obfuscated email
   * @returns {string} The decoded email
   */
  deobfuscateEmail: function (obfuscatedEmail) {
    const reversed = obfuscatedEmail.split("").reverse().join("");
    return atob(reversed);
  },
};

/**
 * UI-related functionality
 */
CineTagIt.UI = {
  /**
   * Display a message in the flash messages container
   * @param {string} message - The message to display
   * @param {string} category - The category of the message (info, success, warning, danger)
   */
  displayMessage: function (message, category = "info") {
    const container = document.getElementById("flash-messages-container");
    if (!container) {
      console.error("Error: Message container #flash-messages-container not found.");
      return;
    }

    // Create the message element
    const messageElement = document.createElement("div");
    messageElement.className = `alert ${category}`;
    messageElement.textContent = message;

    // Add a close button
    const closeButton = document.createElement("button");
    closeButton.textContent = "×";
    closeButton.className = "alert-close-btn";
    closeButton.setAttribute("aria-label", "Close");
    closeButton.onclick = () => {
      messageElement.remove();
    };
    messageElement.appendChild(closeButton);

    // Append the message to the container
    container.appendChild(messageElement);

    // Optional: Auto-dismiss after a few seconds
    // setTimeout(() => {
    //    messageElement.remove();
    // }, 5000);
  },

  /**
   * Initialize mobile menu functionality
   */
  initMobileMenu: function () {
    const mobileMenuToggle = document.querySelector(".mobile-menu-toggle");
    const nav = document.querySelector("nav");

    if (!mobileMenuToggle || !nav) return;

    mobileMenuToggle.addEventListener("click", () => nav.classList.toggle("open"));

    document.addEventListener("click", (evt) => {
      if (!nav.contains(evt.target) && !mobileMenuToggle.contains(evt.target)) {
        nav.classList.remove("open");
      }
    });
  },

  /**
   * Initialize hover with touch support
   */
  initHoverWithTouchSupport: function () {
    const hoverClass = "hovered";
    const scrollThreshold = 10;
    let touchStartX = 0;
    let touchStartY = 0;

    // Mouse hover events
    document.addEventListener("mouseover", (event) => {
      const element = event.target.closest(".hoverable");
      if (element) element.classList.add(hoverClass);
    });

    document.addEventListener("mouseout", (event) => {
      const element = event.target.closest(".hoverable");
      if (element) element.classList.remove(hoverClass);
    });

    // Touch events
    document.addEventListener("touchstart", (event) => {
      const element = event.target.closest(".hoverable");
      if (!element) return;

      touchStartX = event.touches[0].clientX;
      touchStartY = event.touches[0].clientY;
      element.dataset.touching = "true";
    });

    document.addEventListener("touchend", (event) => {
      const element = event.target.closest(".hoverable");
      if (!element) return;

      const touchEndX = event.changedTouches[0].clientX;
      const touchEndY = event.changedTouches[0].clientY;
      const diffX = Math.abs(touchEndX - touchStartX);
      const diffY = Math.abs(touchEndY - touchStartY);
      const isScroll = diffX > scrollThreshold || diffY > scrollThreshold;

      if (isScroll) {
        element.dataset.touching = "false";
        return;
      }

      if (!element.classList.contains(hoverClass)) {
        event.preventDefault();
        element.classList.add(hoverClass);
      }
    });

    // Remove hover class when tapping outside
    document.addEventListener("touchend", (event) => {
      document.querySelectorAll(".hoverable").forEach((element) => {
        if (!element.contains(event.target)) {
          element.classList.remove(hoverClass);
        }
      });
    });
  },
};

/**
 * Event handlers and initialization
 */
CineTagIt.Events = {
  /**
   * Initialize confirmation buttons
   */
  initConfirmationButtons: function () {
    document
      .querySelectorAll("button.needs-confirmation:not(.post-button)")
      .forEach(function (element) {
        const msg = element.getAttribute("data-confirmation-message");
        element.addEventListener("click", (event) => {
          if (!confirm(msg)) {
            event.preventDefault();
          }
        });
      });
  },

  /**
   * Initialize POST buttons
   */
  initPostButtons: function () {
    const csrfToken = CineTagIt.Utils.getCsrfToken();

    document.querySelectorAll(".post-button").forEach((element) => {
      const url = element.getAttribute("data-url");

      if (!url) {
        console.warn("Button found without a data-url attribute:", element);
        return;
      }

      element.addEventListener("click", (event) => {
        event.preventDefault();

        if (element.classList.contains("needs-confirmation")) {
          const msg = element.getAttribute("data-confirmation-message");
          if (!confirm(msg)) {
            return;
          }
        }

        fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrfToken,
          },
        })
          .then((response) => {
            if (!response.ok) {
              return response
                .json()
                .catch(() => null)
                .then((errorData) => {
                  const errorMessage =
                    errorData?.message ||
                    errorData?.error ||
                    `Request failed with status: ${response.status} ${response.statusText}`;
                  throw new Error(errorMessage);
                });
            }
            return response.json();
          })
          .then((data) => {
            if (data.message) {
              const category = data.message_category || (data.success ? "success" : "info");
              CineTagIt.UI.displayMessage(data.message, category);
            } else if (data.error) {
              const category = data.message_category || "danger";
              CineTagIt.UI.displayMessage(data.error, category);
            } else {
              if (data.success === true) {
                CineTagIt.UI.displayMessage("Operation successful.", "success");
              }
            }
          })
          .catch((error) => {
            console.error("Fetch operation failed:", error);
            CineTagIt.UI.displayMessage(
              `Error: ${error.message || "Could not connect to the server."}`,
              "danger",
            );
          });
      });
    });
  },

  /**
   * Initialize email deobfuscation
   */
  initEmailDeobfuscation: function () {
    document.querySelectorAll(".obfuscated-email").forEach(function (element) {
      const obfuscatedEmail = element.getAttribute("data-email");
      if (!obfuscatedEmail) return;

      const decodedEmail = CineTagIt.Utils.deobfuscateEmail(obfuscatedEmail);
      element.innerHTML = `<a href="mailto:${decodedEmail}">${decodedEmail}</a>`;
    });
  },

  /**
   * Initialize copy to clipboard functionality
   */
  initCopyToClipboard: function () {
    document.querySelectorAll(".copy-button").forEach((button) => {
      button.addEventListener("click", async () => {
        const targetSelector = button.getAttribute("data-clipboard-target");
        const targetElement = document.querySelector(targetSelector);

        if (!targetElement) {
          console.error(`Clipboard target element not found: ${targetSelector}`);
          return;
        }

        const textToCopy = targetElement.value ?? targetElement.textContent;

        if (textToCopy === null || textToCopy === undefined || textToCopy.trim() === "") {
          console.warn(`No text found to copy in target: ${targetSelector}`);
          return;
        }

        if (!navigator.clipboard) {
          console.error("Clipboard API not available in this browser or context.");
          alert("Sorry, clipboard access is not available.");
          return;
        }

        const originalButtonText = button.textContent;

        try {
          await navigator.clipboard.writeText(textToCopy.trim());
          button.textContent = "Copied!";
          button.disabled = true;

          setTimeout(() => {
            button.textContent = originalButtonText;
            button.disabled = false;
          }, 2000);
        } catch (err) {
          console.error("Failed to copy text to clipboard:", err);
          button.textContent = "Error!";
          button.disabled = true;

          setTimeout(() => {
            button.textContent = originalButtonText;
            button.disabled = false;
          }, 3000);
        }
      });
    });
  },
};

/**
 * Initialize the application
 */
CineTagIt.init = function () {
  // Set CSRF tokens on form inputs. Forms include both fields so submissions
  // still validate when the access token expires and the request falls through
  // to the refresh-token auth path.
  const csrfToken = CineTagIt.Utils.getCsrfToken();
  const refreshCsrfToken = CineTagIt.Utils.getRefreshCsrfToken();
  document.querySelectorAll('input[name="csrf_token"]').forEach(function (element) {
    element.value = csrfToken;
  });
  document.querySelectorAll('input[name="csrf_refresh_token"]').forEach(function (element) {
    element.value = refreshCsrfToken;
  });

  // Handle initial flashed messages
  // Maintain backward compatibility with old namespace
  if (
    typeof window.CineTagIt !== "undefined" &&
    Array.isArray(window.CineTagIt.initialFlashedMessages)
  ) {
    window.CineTagIt.initialFlashedMessages.forEach(([category, message]) => {
      CineTagIt.UI.displayMessage(message, category);
    });
  }

  navigator.serviceWorker.register("/sw.js").catch((error) => {
    console.error("Service Worker registration failed:", error);
  });

  // Setup magic fields
  const magicFields = document.querySelectorAll('input[name="form_state"]');
  for (let i = 0; i < magicFields.length; i++) {
    const field = magicFields[i];
    field.value = "initializing"; // magic value for backend
  }

  // Initialize UI components
  CineTagIt.UI.initMobileMenu();
  CineTagIt.UI.initHoverWithTouchSupport();

  // Initialize event handlers
  CineTagIt.Events.initConfirmationButtons();
  CineTagIt.Events.initPostButtons();
  CineTagIt.Events.initEmailDeobfuscation();
  CineTagIt.Events.initCopyToClipboard();

  // Initialize registered modules
  for (const moduleName in CineTagIt.modules) {
    if (CineTagIt.modules.hasOwnProperty(moduleName)) {
      try {
        CineTagIt.modules[moduleName]();
      } catch (error) {
        console.error(`Error initializing module '${moduleName}':`, error);
      }
    }
  }

  // Set initialized flag to true
  CineTagIt.initialized = true;
};

// Initialize the application when the DOM is loaded
document.addEventListener("DOMContentLoaded", CineTagIt.init);
