"use strict";
document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: '/api/user/events',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,dayGridYear,listYear',
            },
            multiMonthMaxColumns: 1,
            locale: window.cinetag.language,
        });
    calendar.render();
});