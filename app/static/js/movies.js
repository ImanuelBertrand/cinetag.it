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

    // Fetch movies for each container
    movieContainers.forEach((container) => {
      // Initialize state for this container
      this.containerState.set(container, {
        nextReleaseDate: null,
        nextMovieId: null,
        hasMore: false,
        isLoading: false,
        movies: [],
        filters: {
          name: "",
        },
      });

      this.fetchMovies(container);
    });

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
      // Debounce function to delay filtering while typing
      let nameFilterTimeout;
      nameFilter.addEventListener("input", () => {
        clearTimeout(nameFilterTimeout);
        nameFilterTimeout = setTimeout(() => {
          this.applyFilters();
        }, 500); // 500ms delay
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
  fetchMovies: async function (movieContainer, minReleaseDate = null, minMovieId = null) {
    try {
      const state = this.containerState.get(movieContainer);

      // If already loading, don't start another request
      if (state.isLoading) {
        return;
      }

      state.isLoading = true;

      // load filterMode from data-filter-mode in movieContainer
      const filterMode = movieContainer.getAttribute("data-filter-mode");

      // Build URL with pagination parameters
      let url = `/api/movies/${filterMode}`;
      const params = new URLSearchParams();

      if (minReleaseDate) {
        params.append("min_release_date", minReleaseDate);
      }

      if (minMovieId) {
        params.append("min_movie_id", minMovieId);
      }

      // Add filter parameters
      const filters = state.filters || { name: "" };

      if (filters.name) {
        params.append("name", filters.name);
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
        state.hasMore = data.has_more;

        // If this is the first load, replace the container content
        // Otherwise, append the new movies
        if (!minReleaseDate && !minMovieId) {
          state.movies = data.movies;
          this.renderMovies(movieContainer, data.movies, false);
        } else {
          // Add new movies to the state
          state.movies = [...state.movies, ...data.movies];
          this.renderMovies(movieContainer, data.movies, true);
        }
      } else {
        if (!minReleaseDate && !minMovieId) {
          // Only show error on initial load
          movieContainer.innerHTML = `<p>${data.error || "Error fetching movies."}</p>`;
        }
      }

      state.isLoading = false;
    } catch (error) {
      console.error("Error fetching movies:", error);
      if (!minReleaseDate && !minMovieId) {
        // Only show error on initial load
        movieContainer.innerHTML = `<p>Error fetching movies. Please try again later.</p>`;
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

      this.fetchMovies(movieContainer, state.nextReleaseDate, state.nextMovieId).finally(() => {
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
    const state = this.containerState.get(movieContainer);

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
        movieContainer.innerHTML = "<p>No movies found.</p>";
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

    // Update all containers with new filters
    document.querySelectorAll(".movie-container").forEach((container) => {
      const state = this.containerState.get(container);
      if (state) {
        // Update filter state
        state.filters = {
          name: nameFilter,
        };

        // Reset pagination
        state.nextReleaseDate = null;
        state.nextMovieId = null;
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
