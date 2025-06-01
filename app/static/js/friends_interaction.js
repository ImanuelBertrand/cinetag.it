"use strict";

/**
 * Friends Interaction module for CineTagIt
 * Handles the integration of friends data with movie lists
 */
CineTagIt.modules.friendsInteraction = function () {
  // Initialize friends filter on movie lists
  initFriendsFilter();
};

function initFriendsFilter() {
  const movieListContainer = document.querySelector(".movie-list-container");
  if (!movieListContainer) return;

  // Add friends filter UI
  addFriendsFilterUI();

  // Load friends for the filter
  loadFriendsForFilter();

  // Set up event handlers for filter changes
  setupFilterEventHandlers();
}

function addFriendsFilterUI() {
  const filterContainer = document.querySelector(".filter-container");
  if (!filterContainer) return;

  const friendsFilterHtml = `
        <div class="filter-section">
            <label for="friends-filter">Filter by Friends:</label>
            <select id="friends-filter" multiple class="friends-filter-select">
                <!-- Will be populated dynamically -->
            </select>
        </div>
        <div class="filter-option">
            <input type="checkbox" id="show-unrated" checked>
            <label for="show-unrated">Include movies not rated by friends</label>
        </div>
    `;

  filterContainer.insertAdjacentHTML("beforeend", friendsFilterHtml);
}

async function loadFriendsForFilter() {
  try {
    const response = await fetch("/api/friends/list");
    const data = await response.json();

    const friendsFilter = document.getElementById("friends-filter");
    if (!friendsFilter) return;

    if (data.success && data.friends.length > 0) {
      const friendsOptions = data.friends
        .map((friend) => `<option value="${friend.id}">${friend.display_name || "User"}</option>`)
        .join("");

      friendsFilter.innerHTML = friendsOptions;

      // Initialize the select element (you might want to use a library like select2 here)
      // For now, we'll just use the native select
    } else {
      friendsFilter.innerHTML = "<option disabled>No friends found</option>";
    }
  } catch (error) {
    console.error("Error loading friends for filter:", error);
    const friendsFilter = document.getElementById("friends-filter");
    if (friendsFilter) {
      friendsFilter.innerHTML = "<option disabled>Error loading friends</option>";
    }
  }
}

function setupFilterEventHandlers() {
  const friendsFilter = document.getElementById("friends-filter");
  const showUnratedCheckbox = document.getElementById("show-unrated");

  if (!friendsFilter || !showUnratedCheckbox) return;

  // Add change event listeners
  friendsFilter.addEventListener("change", applyFilters);
  showUnratedCheckbox.addEventListener("change", applyFilters);

  // Restore filter state from localStorage if available
  const savedFilter = JSON.parse(localStorage.getItem("friendFilter") || "{}");
  if (savedFilter.friendIds) {
    // Set selected options
    Array.from(friendsFilter.options).forEach((option) => {
      option.selected = savedFilter.friendIds.includes(option.value);
    });
  }

  if (savedFilter.includeUnrated !== undefined) {
    showUnratedCheckbox.checked = savedFilter.includeUnrated;
  }
}

function applyFilters() {
  const friendsFilter = document.getElementById("friends-filter");
  const showUnratedCheckbox = document.getElementById("show-unrated");

  if (!friendsFilter || !showUnratedCheckbox) return;

  // Get selected friend IDs
  const selectedFriends = Array.from(friendsFilter.selectedOptions).map((option) => option.value);
  const includeUnrated = showUnratedCheckbox.checked;

  // Store filter state in localStorage
  localStorage.setItem(
    "friendFilter",
    JSON.stringify({
      friendIds: selectedFriends,
      includeUnrated: includeUnrated,
    }),
  );

  // Apply the filter by reloading the movies
  const movieContainers = document.querySelectorAll(".movie-container");
  movieContainers.forEach((container) => {
    const filterMode = container.getAttribute("data-filter-mode");
    fetchMoviesWithFilters(container, filterMode, selectedFriends, includeUnrated);
  });
}

async function fetchMoviesWithFilters(container, filterMode, friendIds, includeUnrated) {
  try {
    let url = `/api/movies/${filterMode}`;

    // Add query parameters if filters are applied
    if (friendIds && friendIds.length > 0) {
      const params = new URLSearchParams();
      params.append("friend_ids", friendIds.join(","));
      params.append("include_unrated", includeUnrated);
      url += `?${params.toString()}`;
    }

    container.innerHTML = "<p>Loading movies...</p>";

    const response = await fetch(url);
    const data = await response.json();

    if (data.success) {
      renderMoviesWithFriendData(container, data.movies);
    } else {
      container.innerHTML = `<p>${data.error || "Error fetching movies."}</p>`;
    }
  } catch (error) {
    console.error("Error fetching movies with filters:", error);
    container.innerHTML = "<p>Error loading movies. Please try again later.</p>";
  }
}

function renderMoviesWithFriendData(container, movies) {
  if (movies.length === 0) {
    container.innerHTML = "<p>No movies found matching the selected filters.</p>";
    return;
  }

  const moviesHtml = movies
    .map((movie) => {
      const decisionClass = movie.decision ? `decided decided-${movie.decision}` : "";
      const posterClass = movie.poster_url ? "" : "has-no-poster";

      // Add friend rating indicators if available
      let friendRatingHtml = "";
      if (movie.friend_ratings) {
        const ratings = movie.friend_ratings;
        const approveCount = ratings.approve_count;
        const maybeCount = ratings.maybe_count;
        const totalRated = approveCount + maybeCount;

        if (totalRated > 0) {
          const ratingClass =
            approveCount > 0 ? (maybeCount > 0 ? "mixed-rating" : "all-approve") : "all-maybe";

          friendRatingHtml = `
                    <div class="friend-rating ${ratingClass}">
                        <span class="rating-icon"></span>
                        <span class="rating-count">${totalRated}/${ratings.total_friends}</span>
                    </div>
                `;
        }
      }

      // Create poster element
      let poster;
      if (movie.poster_url) {
        poster = `<img class="movie-poster" src="${movie.poster_url}" alt="${movie.title} poster">`;
      } else {
        poster = `<div class="no-poster"><div class="movie-title">${movie.title}</div></div>`;
      }

      return `
            <div class="movie-item hoverable ${decisionClass} ${posterClass}" id="movie-${movie.id}">
                <div class="decision-icon"></div>
                ${friendRatingHtml}
                ${poster}
                <div class="overlay">
                    <a href="/movie/${movie.id}">${movie.title}</a>
                    <div class="decide">
                        <div class="approve" data-movie-id="${movie.id}" data-decision="approve">👍</div>
                        <div class="maybe" data-movie-id="${movie.id}" data-decision="maybe">🤷</div>
                        <div class="disapprove" data-movie-id="${movie.id}" data-decision="disapprove">👎</div>
                    </div>
                </div>
            </div>
        `;
    })
    .join("");

  container.innerHTML = `<div class="movie-grid">${moviesHtml}</div>`;

  // Add event listeners for movie decisions
  container.querySelectorAll(".decide > div").forEach((element) => {
    element.addEventListener("click", handleMovieDecision);
  });
}

function handleMovieDecision(event) {
  // This function would be defined in movies.js
  // We're just referencing it here for completeness
  if (typeof window.handleMovieDecision === "function") {
    window.handleMovieDecision(event);
  }
}
