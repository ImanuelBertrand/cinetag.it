"use strict";

/**
 * CineTagIt - Main namespace for the CineTagIt application
 */
window.CineTagIt = window.CineTagIt || {};

/**
 * Movies functionality
 */
CineTagIt.Movies = {
  // State for each container
  containerState: new Map(),

  /**
   * Initialize the movies functionality
   */
  init: function () {
    const movieContainers = document.querySelectorAll(".movie-container");

    if (movieContainers.length === 0) {
      return;
    }

    // Get filters from the URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const friendId = urlParams.get("friend_id");
    const nameParam = urlParams.get("name") || "";
    const sort = urlParams.get("sort") === "popularity" ? "popularity" : "release";
    const genres = urlParams.get("genres") || "";

    // Fetch movies for each container
    movieContainers.forEach((container) => {
      // Initialize state for this container
      this.containerState.set(container, {
        nextReleaseDate: null,
        nextMovieId: null,
        nextPopularity: null,
        hasMore: false,
        isLoading: false,
        movies: [],
        filters: {
          name: nameParam,
          friendId: friendId,
          sort: sort,
          genres: genres,
        },
      });

      this.fetchMovies(container);
    });

    // Genre and sort controls (multi-select genre chips + sort toggle)
    this.initBrowseControls();

    // Add scroll event listener for infinite scrolling
    window.addEventListener("scroll", this.handleScroll.bind(this));

    // Add event listener for decision buttons
    document.addEventListener("click", (event) => {
      if (event.target.matches(".decide > div")) {
        this.handleDecision(event);
      }
    });

    // Add event listeners for filters
    const nameFilter = document.getElementById("name-filter");

    if (nameFilter) {
      // Reflect a ?name= URL parameter in the input, so applyFilters (which
      // reads the input) doesn't silently drop it on genre/sort changes.
      if (nameParam) {
        nameFilter.value = nameParam;
      }

      // Update URL with name filter
      nameFilter.addEventListener("input", (event) => {
        const nameFilterValue = event.target.value;
        const url = new URL(window.location.href);

        if (nameFilterValue) {
          url.searchParams.set("name", nameFilterValue);
        } else {
          url.searchParams.delete("name");
        }

        // We use history.replaceState to update the URL without reloading
        window.history.replaceState({}, "", url.toString());

        // Debounce function to delay filtering while typing
        if (this.nameFilterTimeout) {
          clearTimeout(this.nameFilterTimeout);
        }
        this.nameFilterTimeout = setTimeout(() => {
          this.applyFilters();
        }, 500); // 500ms delay
      });
    }

    const friendFilterSelect = document.getElementById("friend-filter-select");
    if (friendFilterSelect) {
      if (friendId) {
        friendFilterSelect.value = friendId;
      }

      friendFilterSelect.addEventListener("change", (event) => {
        const selectedFriendId = event.target.value;
        const url = new URL(window.location.href);

        if (selectedFriendId) {
          url.searchParams.set("friend_id", selectedFriendId);
        } else {
          url.searchParams.delete("friend_id");
        }

        // Also keep name filter if it's there
        const nameFilterValue = document.getElementById("name-filter")?.value;
        if (nameFilterValue) {
          url.searchParams.set("name", nameFilterValue);
        }

        window.location.href = url.toString();
      });
    }
  },

  /**
   * Wire up the genre-chip multi-select and the sort toggle. Both update the
   * URL query string and re-fetch, mirroring the name-filter pattern.
   */
  initBrowseControls: function () {
    const genreChips = document.getElementById("genre-chips");
    if (genreChips) {
      genreChips.addEventListener("click", (event) => {
        const chip = event.target.closest(".genre-chip");
        if (!chip) return;

        chip.classList.toggle("active");
        const selected = Array.from(genreChips.querySelectorAll(".genre-chip.active")).map((el) =>
          el.getAttribute("data-genre-id"),
        );

        const url = new URL(window.location.href);
        if (selected.length) {
          url.searchParams.set("genres", selected.join(","));
        } else {
          url.searchParams.delete("genres");
        }
        window.history.replaceState({}, "", url.toString());
        this.applyFilters();
      });
    }

    const sortToggle = document.getElementById("sort-toggle");
    if (sortToggle) {
      sortToggle.addEventListener("click", (event) => {
        const chip = event.target.closest(".sort-chip");
        if (!chip) return;

        const sort = chip.getAttribute("data-sort");
        sortToggle.querySelectorAll(".sort-chip").forEach((el) => {
          el.classList.toggle("active", el === chip);
        });

        const url = new URL(window.location.href);
        if (sort === "popularity") {
          url.searchParams.set("sort", "popularity");
        } else {
          url.searchParams.delete("sort");
        }
        window.history.replaceState({}, "", url.toString());
        this.applyFilters();
      });
    }
  },

  /**
   * Handle scroll event for infinite scrolling
   */
  handleScroll: function () {
    // Check if we're near the bottom of the page
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000) {
      // Load more movies for each container that has more to load
      document.querySelectorAll(".movie-container").forEach((container) => {
        const state = this.containerState.get(container);
        if (state && state.hasMore && !state.isLoading) {
          this.loadMoreMovies(container);
        }
      });
    }
  },

  /**
   * Fetch movies from the API
   * @param {HTMLElement} movieContainer - The container to render movies in
   * @param {string|null} minReleaseDate - The minimum release date for pagination
   * @param {number|null} minMovieId - The minimum movie ID for pagination
   */
  fetchMovies: async function (
    movieContainer,
    minReleaseDate = null,
    minMovieId = null,
    minPopularity = null,
  ) {
    try {
      const state = this.containerState.get(movieContainer);

      // If already loading, don't start another request
      if (state.isLoading) {
        return;
      }

      state.isLoading = true;

      // min_movie_id is the tiebreaker present on every paginated request, so
      // its absence marks the first page.
      const isInitialLoad = !minMovieId;

      // load filterMode from data-filter-mode in movieContainer
      const filterMode = movieContainer.getAttribute("data-filter-mode");

      // Optional fixed limit (e.g. the home page poster wall);
      // containers with a limit don't paginate
      const limit = movieContainer.getAttribute("data-limit");

      // Build URL with pagination parameters
      let url = `/api/movies/${filterMode}`;
      const params = new URLSearchParams();

      if (limit) {
        params.append("limit", limit);
      }

      if (minReleaseDate) {
        params.append("min_release_date", minReleaseDate);
      }

      if (minMovieId) {
        params.append("min_movie_id", minMovieId);
      }

      if (minPopularity !== null && minPopularity !== undefined) {
        params.append("min_popularity", minPopularity);
      }

      // Add filter parameters
      const filters = state.filters || { name: "", friendId: null };

      if (filters.name) {
        params.append("name", filters.name);
      }

      if (filters.friendId) {
        params.append("friend_id", filters.friendId);
      }

      if (filters.sort === "popularity") {
        params.append("sort", "popularity");
      }

      if (filters.genres) {
        params.append("genres", filters.genres);
      }

      // Add params to URL if any exist
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const response = await fetch(url);
      const data = await response.json();

      if (data.success) {
        // Update state with new pagination data
        state.nextReleaseDate = data.next_release_date;
        state.nextMovieId = data.next_movie_id;
        state.nextPopularity = data.next_popularity;
        state.hasMore = limit ? false : data.has_more;

        // Update friend filter UI if friend info is available
        if (data.friend && state.filters.friendId) {
          // Look for the friend filter span in the filter bar first, then anywhere in the document
          const filterBar = document.querySelector(".movie-filters");
          let friendFilterSpan = filterBar ? filterBar.querySelector(".friend-filter span") : null;
          if (!friendFilterSpan) {
            friendFilterSpan = document.querySelector(".friend-filter span");
          }

          if (friendFilterSpan) {
            const filterMode = movieContainer.getAttribute("data-filter-mode");
            friendFilterSpan.textContent =
              filterMode === "approved"
                ? `Movies you and ${data.friend.name} both want to see`
                : `Upcoming movies ${data.friend.name} approved`;
          }
        }

        // If this is the first load, replace the container content
        // Otherwise, append the new movies
        if (isInitialLoad) {
          state.movies = data.movies;
          this.renderMovies(movieContainer, data.movies, false);
        } else {
          // Add new movies to the state
          state.movies = [...state.movies, ...data.movies];
          this.renderMovies(movieContainer, data.movies, true);
        }
      } else {
        if (isInitialLoad) {
          // Only show error on initial load
          // Create an error message element instead of using innerHTML
          const errorMessage = document.createElement("p");
          errorMessage.textContent = data.error || "Error fetching movies.";

          // Clear the container first
          movieContainer.innerHTML = "";

          // Add the error message
          movieContainer.appendChild(errorMessage);

          // Log the error for debugging
          console.error("API returned error:", data.error);
        }
      }

      state.isLoading = false;
    } catch (error) {
      console.error("Error fetching movies:", error);
      if (!minMovieId) {
        // Only show error on initial load
        // Create an error message element instead of using innerHTML
        const errorMessage = document.createElement("p");
        errorMessage.textContent = "Error fetching movies. Please try again later.";

        // Clear the container first
        movieContainer.innerHTML = "";

        // Add the error message
        movieContainer.appendChild(errorMessage);

        // Log the detailed error for debugging
        console.error("Fetch error details:", error);
      }

      const state = this.containerState.get(movieContainer);
      state.isLoading = false;
    }
  },

  /**
   * Load more movies when the user scrolls or clicks a button
   * @param {HTMLElement} movieContainer - The container to load more movies in
   */
  loadMoreMovies: function (movieContainer) {
    const state = this.containerState.get(movieContainer);
    if (state.hasMore && !state.isLoading) {
      // Show loading indicator
      const loadingIndicator = document.createElement("div");
      loadingIndicator.className = "loading-indicator";
      loadingIndicator.innerHTML = "<span>Loading more movies...</span>";
      movieContainer.appendChild(loadingIndicator);

      this.fetchMovies(
        movieContainer,
        state.nextReleaseDate,
        state.nextMovieId,
        state.nextPopularity,
      ).finally(() => {
        // Remove loading indicator when done
        const indicator = movieContainer.querySelector(".loading-indicator");
        if (indicator) {
          indicator.remove();
        }
      });
    }
  },

  /**
   * Render movies in the container
   * @param {HTMLElement} movieContainer - The container to render movies in
   * @param {Array} movies - The movies to render
   * @param {boolean} append - Whether to append or replace the content
   */
  renderMovies: function (movieContainer, movies, append = false) {
    // Check if we need to display a friend filter
    let state = this.containerState.get(movieContainer);

    if (state && state.filters.friendId && !append) {
      // Check if we already have friend info from the API response
      const friendFilterDiv = document.querySelector(".friend-filter");

      if (!friendFilterDiv) {
        // Create friend filter UI
        const friendFilterContainer = document.createElement("div");
        friendFilterContainer.className = "friend-filter";

        // We'll update this with the friend's name when we get the API response
        const placeholder =
          movieContainer.getAttribute("data-filter-mode") === "approved"
            ? "Movies you both want to see"
            : "Upcoming movies your friend approved";
        friendFilterContainer.innerHTML = `
                    <span>${placeholder}</span>
                    <button class="remove-friend-filter">×</button>
                `;

        // Add click handler to remove filter
        friendFilterContainer
          .querySelector(".remove-friend-filter")
          .addEventListener("click", () => {
            // Remove friend_id from URL and reload
            const url = new URL(window.location);
            url.searchParams.delete("friend_id");
            window.location.href = url.toString();
          });

        // Insert into the filter bar
        const filterBar = document.querySelector(".movie-filters");

        if (filterBar) {
          // Create a filter group for the friend filter
          const filterGroup = document.createElement("div");
          filterGroup.className = "filter-group";
          filterGroup.appendChild(friendFilterContainer);
          filterBar.appendChild(filterGroup);
        } else {
          // Fallback: insert before the movie container
          movieContainer.parentNode.insertBefore(friendFilterContainer, movieContainer);
        }
      }
    }
    const moviesHtml = movies
      .map((movie) => {
        const decisionClass = movie.decision ? `decided decided-${movie.decision}` : "";
        const posterClass = movie.poster_url ? "" : "has-no-poster";
        const poster = movie.poster_url
          ? `<img src="${movie.poster_url}" alt="${movie.title}" class="movie-poster" loading="lazy"/>`
          : `<span class="no-poster">${movie.title}</span>`;

        const release_dates =
          movie.all_release_dates && movie.all_release_dates.length > 0
            ? this.renderReleaseDates(movie.all_release_dates)
            : movie.release_date_pretty;

        return `
                <div class="movie-item hoverable ${decisionClass} ${posterClass}" id="movie-${movie.id}">
                    <div class="decision-icon"></div>
                    ${poster}
                    <div class="overlay">
                        <a class="details-link" href="/movie/${movie.id}">${movie.title}</a>
                        <div class="decide">
                            <div data-decision="approve" data-movie-id="${movie.id}">👍️</div>
                            <div data-decision="maybe" data-movie-id="${movie.id}">🤷</div>
                            <div data-decision="disapprove" data-movie-id="${movie.id}">👎</div>
                        </div>
                        <a class="details-link" href="/movie/${movie.id}">
                            <div class="release-dates">${release_dates}</div>
                        </a>
                    </div>
                </div>`;
      })
      .join("");

    if (append) {
      // Append new movies instead of replacing
      movieContainer.insertAdjacentHTML("beforeend", moviesHtml);
    } else {
      // Replace existing content
      movieContainer.innerHTML = moviesHtml;
    }

    // Add a "Load More" button if there are more movies to load
    state = this.containerState.get(movieContainer);

    // Remove any existing loading indicators
    const existingIndicator = movieContainer.querySelector(".loading-indicator");
    if (existingIndicator) {
      existingIndicator.remove();
    }

    if (state.hasMore) {
      // Check if we already have a load more button
      let loadMoreBtn = movieContainer.querySelector(".load-more-btn");

      if (!loadMoreBtn) {
        // Create and append the button
        loadMoreBtn = document.createElement("button");
        loadMoreBtn.className = "load-more-btn";
        loadMoreBtn.textContent = "Load More Movies";
        loadMoreBtn.style.order = "1000";
        loadMoreBtn.addEventListener("click", () => this.loadMoreMovies(movieContainer));
        movieContainer.appendChild(loadMoreBtn);
      }
    } else {
      // Remove the load more button if it exists
      const loadMoreBtn = movieContainer.querySelector(".load-more-btn");
      if (loadMoreBtn) {
        loadMoreBtn.remove();
      }

      // If no movies were found, show a message
      if (state.movies.length === 0) {
        // Create a message element instead of using innerHTML to avoid overwriting the friend filter
        const noMoviesMessage = document.createElement("p");
        noMoviesMessage.textContent = "No movies found.";

        // Clear the container first
        movieContainer.innerHTML = "";

        // Add the message
        movieContainer.appendChild(noMoviesMessage);
      }
    }
  },

  /**
   * Render release dates for a movie
   * @param {Array} releaseDates - The release dates to render
   * @returns {string} The HTML for the release dates
   */
  renderReleaseDates: function (releaseDates) {
    return releaseDates
      .map(
        (date) => `<div title="${date.region_info.english_name}">
                ${date.flag ? `<span class="flag-icon">${date.flag}</span>` : `<span>${date.region}</span>`}
                <span>${date.date_pretty}</span>
            </div>`,
      )
      .join("");
  },

  /**
   * Get the decision for a movie
   * @param {HTMLElement} target - The element that was clicked
   * @returns {string} The decision (approve, maybe, disapprove, or remove)
   */
  getDecision: function (target) {
    const movieId = target.getAttribute("data-movie-id");
    const movieElement = document.getElementById(`movie-${movieId}`);
    let decision = target.getAttribute("data-decision");
    if (movieElement.classList.contains("decided-" + decision)) {
      return "remove";
    }
    return decision;
  },

  /**
   * Apply filters to all movie containers
   */
  applyFilters: function () {
    // Get filter values
    const nameFilter = document.getElementById("name-filter")?.value || "";

    // Get friend_id / sort / genres from the URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const friendId = urlParams.get("friend_id");
    const sort = urlParams.get("sort") === "popularity" ? "popularity" : "release";
    const genres = urlParams.get("genres") || "";

    // Update all containers with new filters
    document.querySelectorAll(".movie-container").forEach((container) => {
      const state = this.containerState.get(container);
      if (state) {
        // Update filter state
        state.filters = {
          name: nameFilter,
          friendId: friendId,
          sort: sort,
          genres: genres,
        };

        // Reset pagination
        state.nextReleaseDate = null;
        state.nextMovieId = null;
        state.nextPopularity = null;
        state.hasMore = false;
        state.isLoading = false;

        // Fetch movies with new filters
        this.fetchMovies(container);
      }
    });
  },

  handleDecision: function (event) {
    const movieId = event.target.getAttribute("data-movie-id");
    const movieElement = document.getElementById(`movie-${movieId}`);
    const decision = this.getDecision(event.target);

    const csrfToken = window.CineTagIt.Utils.getCsrfToken();

    fetch(`/api/user/movies/review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": csrfToken,
      },
      body: JSON.stringify({
        movie_id: movieId,
        decision: decision,
        csrf_token: csrfToken,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          const classes_to_remove = ["decided-approve", "decided-disapprove", "decided-maybe"];
          classes_to_remove.forEach((class_name) => movieElement.classList.remove(class_name));
          if (data["decision_status"] === decision) {
            movieElement.classList.add("decided", "decided-" + data["decision_status"]);
          } else {
            movieElement.classList.remove("decided");
          }
          movieElement.classList.remove("hovered");
        } else if (data.error) {
          window.CineTagIt.UI.displayMessage(data.error, "danger");
        } else if (data.message) {
          window.CineTagIt.UI.displayMessage(data.message, data.message_category || "info");
        } else {
          window.CineTagIt.UI.displayMessage(
            "An error occurred. Please try again later.",
            "danger",
          );
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        window.CineTagIt.UI.displayMessage(`Error: ${error.message || "Unknown error"}`, "danger");
      });
  },
};

// Register the module's initialization function
CineTagIt.modules = CineTagIt.modules || {};
CineTagIt.modules.Movies = function () {
  CineTagIt.Movies.init();
};

// If CineTagIt is already initialized, call the module init directly
if (window.CineTagIt && window.CineTagIt.initialized) {
  CineTagIt.Movies.init();
}
