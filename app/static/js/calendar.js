"use strict";

document.addEventListener("DOMContentLoaded", function () {
  const calendarEl = document.getElementById("calendar");

  // Skip initialization if calendar element doesn't exist
  if (!calendarEl) return;

  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: "dayGridMonth",
    events: "/api/user/events",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth,dayGridYear,listYear",
    },
    multiMonthMaxColumns: 1,
    locale: window.CineTagIt?.language || "en",
  });

  calendar.render();
});
