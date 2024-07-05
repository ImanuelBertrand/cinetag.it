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
        element.addEventListener('click', event => {
            if (!confirm(msg)) {
                event.preventDefault();
            }
        });
    });

    // Hover with touch support
    const hover_class = 'hovered';
    document.querySelectorAll('.hoverable').forEach(function (element) {
        element.addEventListener('mouseover', () => element.classList.add(hover_class));
        element.addEventListener('mouseout', () => element.classList.remove(hover_class));

        element.addEventListener('touchstart', e => {
            if (!element.classList.contains(hover_class)) {
                e.preventDefault(); // Prevent the click event
                element.classList.add(hover_class);
            }
        });
        document.addEventListener('touchstart', evt => {
            if (!element.contains(evt.target)) {
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
});
