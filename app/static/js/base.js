"use strict";

document.addEventListener("DOMContentLoaded", function () {

    // CSRF token
    const csrf_token = document.cookie.split('; ').find(row => row.startsWith('csrf_access_token')).split('=')[1];
    document.querySelectorAll('input[name="csrf_token"]').forEach(function (element) {
        element.value = csrf_token;
    });

    function displayMessage(message, category = 'info') {
        const container = document.getElementById('flash-messages-container');
        if (!container) {
            console.error('Error: Message container #flash-messages-container not found.');
            return;
        }

        // Create the message element (e.g., a div)
        const messageElement = document.createElement('div');
        messageElement.className = `alert ${category}`; // Apply classes
        messageElement.textContent = message; // Set the text content

        // Optional: Add a close button ('×')
        const closeButton = document.createElement('button');
        closeButton.textContent = '×';
        closeButton.className = 'alert-close-btn'; // Add a class for styling/selection
        closeButton.setAttribute('aria-label', 'Close'); // Accessibility
        closeButton.onclick = () => {
            messageElement.remove(); // Remove the message element when clicked
        };
        messageElement.appendChild(closeButton);

        // Append the new message to the container
        container.appendChild(messageElement);

        // Optional: Auto-dismiss after a few seconds (e.g., 5 seconds)
        // setTimeout(() => {
        //    messageElement.remove();
        // }, 5000);
    }

    if (typeof window.cinetagit.initialFlashedMessages !== 'undefined'
        && Array.isArray(window.cinetagit.initialFlashedMessages)) {
        window.cinetagit.initialFlashedMessages.forEach(([category, message]) => {
            displayMessage(message, category);
        });
    }

    // Confirmations
    document.querySelectorAll('button.needs-confirmation:not(.post-button)').forEach(function (element) {
        const msg = element.getAttribute('data-confirmation-message');
        element.addEventListener('click', event => {
            if (!confirm(msg)) {
                event.preventDefault();
            }
        });
    });

    // Generic buttons to execute POST calls and receive a response with a message
    document.querySelectorAll('.post-button').forEach(element => {
        const url = element.getAttribute('data-url');

        // Basic check if URL exists
        if (!url) {
            console.warn('Button found without a data-url attribute:', element);
            return; // Skip this button if it has no URL
        }

        element.addEventListener('click', event => {
            event.preventDefault(); // Prevent default button behavior (like form submission)

            // If this is also a confirmation button, check confirmation first
            if (element.classList.contains('needs-confirmation')) {
                const msg = element.getAttribute('data-confirmation-message');
                if (!confirm(msg)) {
                    return; // Don't proceed with the POST if user cancels
                }
            }

            // Optional: Clear previous messages before making a new request
            // clearMessages();

            fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf_token},
            })
                .then(response => {
                    // Check for non-OK HTTP responses (like 404, 500, etc.)
                    if (!response.ok) {
                        // Try to get error message from response body if possible, otherwise use status text
                        return response.json().catch(() => null).then(errorData => {
                            // Prefer server's JSON error message if available
                            const errorMessage = errorData?.message
                                || errorData?.error
                                || `Request failed with status: ${response.status} ${response.statusText}`;
                            throw new Error(errorMessage); // Throw an error to be caught below
                        });
                    }
                    // If response is OK, parse the JSON body
                    return response.json();
                })
                .then(data => {
                    // --- Process the successful JSON response ---
                    if (data.message) {
                        // Use category from data if present, otherwise default (e.g., 'success' or 'info')
                        const category = data.message_category || (data.success ? 'success' : 'info');
                        displayMessage(data.message, category);
                    } else if (data.error) {
                        // Handle responses that specifically indicate an error
                        const category = data.message_category || 'danger';
                        displayMessage(data.error, category);
                    } else {
                        // Fallback if the response structure is unexpected but valid JSON
                        console.log('Received data:', data);
                        // Optionally display a generic success message if data.success is true but no message provided
                        if (data.success === true) {
                            displayMessage('Operation successful.', 'success');
                        }
                    }
                })
                .catch(error => {
                    // --- Handle fetch errors (network issues, parsing errors, thrown errors) ---
                    console.error('Fetch operation failed:', error);
                    // Display a user-friendly error message
                    displayMessage(`Error: ${error.message || 'Could not connect to the server.'}`, 'danger');
                });
        });
    });


    // Hover with touch support
    const hover_class = "hovered";
    const scroll_threshold = 10; // Adjust as needed

    let touchStartX = 0;
    let touchStartY = 0;

    // Mouse hover events (added via event delegation)
    document.addEventListener("mouseover", event => {
        const element = event.target.closest(".hoverable");
        if (element) element.classList.add(hover_class);
    });

    document.addEventListener("mouseout", event => {
        const element = event.target.closest(".hoverable");
        if (element) element.classList.remove(hover_class);
    });

    // Touch events (added via event delegation)
    document.addEventListener("touchstart", event => {
        const element = event.target.closest(".hoverable");
        if (!element) return;

        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;

        element.dataset.touching = "true"; // Mark element as being touched
    });

    document.addEventListener("touchend", event => {
        const element = event.target.closest(".hoverable");
        if (!element) return;

        const touchEndX = event.changedTouches[0].clientX;
        const touchEndY = event.changedTouches[0].clientY;

        const diffX = Math.abs(touchEndX - touchStartX);
        const diffY = Math.abs(touchEndY - touchStartY);

        const is_scroll = diffX > scroll_threshold || diffY > scroll_threshold;
        if (is_scroll) {
            element.dataset.touching = "false";
            return;
        }

        if (!element.classList.contains(hover_class)) {
            event.preventDefault(); // Prevent accidental clicks
            element.classList.add(hover_class);
        }
    });

    // Remove hover class when tapping outside
    document.addEventListener("touchend", event => {
        document.querySelectorAll(".hoverable").forEach(element => {
            if (!element.contains(event.target)) {
                element.classList.remove(hover_class);
            }
        });
    });

    // mobile menu
    const mobile_menu_toggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('nav');
    mobile_menu_toggle.addEventListener('click', () => nav.classList.toggle('open'));
    document.addEventListener('click', evt => {
        if (!nav.contains(evt.target) && !mobile_menu_toggle.contains(evt.target)) {
            nav.classList.remove('open');
        }
    });

    // de-obfuscate email addresses
    document.querySelectorAll('.obfuscated-email').forEach(function (element) {
        const obfuscatedEmail = element.getAttribute('data-email');
        const reversed = obfuscatedEmail.split("").reverse().join("");
        const decoded = atob(reversed);
        element.innerHTML = `<a href="mailto:${decoded}">${decoded}</a>`;
    });

    // Copy to clipboard functionality
    document.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', async () => { // Make the handler async
            const targetSelector = button.getAttribute('data-clipboard-target');
            const targetElement = document.querySelector(targetSelector);

            if (!targetElement) {
                console.error(`Clipboard target element not found: ${targetSelector}`);
                // Optional: Add user feedback here if the target is missing
                return; // Exit if target doesn't exist
            }

            // Get text: Use value for inputs/textareas, otherwise textContent
            // Using nullish coalescing operator (??) is slightly safer than ||
            // as it only proceeds if `value` is null or undefined, not just falsy (like an empty string).
            const textToCopy = targetElement.value ?? targetElement.textContent;

            if (textToCopy === null || textToCopy === undefined || textToCopy.trim() === '') {
                console.warn(`No text found to copy in target: ${targetSelector}`);
                // Optional: Add user feedback here if the target is empty
                return; // Exit if there's nothing to copy
            }

            // Check if Clipboard API is available (recommended)
            if (!navigator.clipboard) {
                console.error('Clipboard API not available in this browser or context (requires HTTPS or localhost).');
                // Optionally, you could try a fallback here using the old method,
                // but it's generally better to inform the user or just fail gracefully.
                alert('Sorry, clipboard access is not available.'); // Simple user feedback
                return;
            }

            const originalButtonText = button.textContent; // Store original text

            try {
                await navigator.clipboard.writeText(textToCopy.trim());

                // --- Success Feedback ---
                button.textContent = 'Copied!';
                button.disabled = true; // Temporarily disable to prevent rapid clicks

                // Reset button text after a delay
                setTimeout(() => {
                    button.textContent = originalButtonText;
                    button.disabled = false; // Re-enable button
                }, 2000); // 2 seconds

            } catch (err) {
                // --- Error Handling ---
                console.error('Failed to copy text to clipboard: ', err);
                button.textContent = 'Error!';
                button.disabled = true; // Keep disabled on error briefly

                // Reset button text after a delay (maybe longer for error)
                setTimeout(() => {
                    button.textContent = originalButtonText;
                    button.disabled = false; // Re-enable
                }, 3000); // 3 seconds

                // Optional: More specific user feedback
                // alert('Could not copy text. Please try copying manually.');
            }
        });
    });

});
