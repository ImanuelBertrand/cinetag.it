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
    const scroll_threshold = 10;
    document.querySelectorAll('.hoverable').forEach(function (element) {
        let touchStartX = 0;
        let touchStartY = 0;

        element.addEventListener('mouseover', () => element.classList.add(hover_class));
        element.addEventListener('mouseout', () => element.classList.remove(hover_class));

        element.addEventListener('touchstart', e => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        element.addEventListener('touchend', e => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;

            const diffX = Math.abs(touchEndX - touchStartX);
            const diffY = Math.abs(touchEndY - touchStartY);

            const is_scroll = diffX > scroll_threshold || diffY > scroll_threshold;
            if (is_scroll) {
                return;
            }

            if (!element.classList.contains(hover_class)) {
                e.preventDefault(); // Prevent the click event
                element.classList.add(hover_class);
            }
        });
        document.addEventListener('touchend', evt => {
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

    // de-obfuscate email addresses
    document.querySelectorAll('.obfuscated-email').forEach(function (element) {
        const obfuscatedEmail = element.getAttribute('data-email');
        const reversed = obfuscatedEmail.split("").reverse().join("");
        const decoded = atob(reversed);
        element.innerHTML = `<a href="mailto:${decoded}">${decoded}</a>`;
    });
});
