"use strict";

document.addEventListener("DOMContentLoaded", function () {

    // CSRF token
    const csrf_token = document.cookie.split('; ').find(row => row.startsWith('csrf_access_token')).split('=')[1];
    document.querySelectorAll('input[name="csrf_token"]').forEach(function (element) {
        element.value = csrf_token;
    });

    // Confirmations
    document.querySelectorAll('button[type="submit"].needs-confirmation').forEach(function (element) {
        const msg = element.getAttribute('data-confirmation-message');
        element.addEventListener('click', function (event) {
            if (!confirm(msg)) {
                event.preventDefault();
            }
        });
    });
});
