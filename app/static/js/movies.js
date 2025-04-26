"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const movieContainers = document.querySelectorAll(".movie-container");

    // Fetch movies for each container
    movieContainers.forEach(fetchMovies);

    async function fetchMovies(movieContainer) {
        try {
            // load filterMode from data-filter-mode in movieContainer
            const filterMode = movieContainer.getAttribute("data-filter-mode");
            const response = await fetch(`/api/movies/${filterMode}`);
            const data = await response.json();

            if (data.success) {
                renderMovies(movieContainer, data.movies);
            } else {
                movieContainer.innerHTML = `<p>${data.error || 'Error fetching movies.'}</p>`;
            }
        } catch (error) {
            console.error('Error fetching movies:', error);
            movieContainer.innerHTML = `<p>Error fetching movies. Please try again later.</p>`;
        }
    }

    function renderMovies(movieContainer, movies) {
        movieContainer.innerHTML = movies.map(movie => {
            const decisionClass = movie.decision ? `decided decided-${movie.decision}` : '';
            const posterClass = movie.poster_url ? '' : 'has-no-poster';
            const poster = movie.poster_url
                ? `<img src="${movie.poster_url}" alt="${movie.title}" class="movie-poster" loading="lazy"/>`
                : `<span class="no-poster">${movie.title}</span>`;

            const release_dates = movie.all_release_dates && movie.all_release_dates.count > 0
                ? renderReleaseDates(movie.all_release_dates)
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
        }).join("");
    }

    function renderReleaseDates(releaseDates) {
        return releaseDates.map(
            date => `<div title="${date.region_info.english_name}">
                ${date.flag ? `<span class="flag-icon">${date.flag}</span>` : `<span>${date.region}</span>`}
                <span>${date.date_pretty}</span>
            </div>`
        ).join("");
    }

    document.addEventListener('click', function (event) {
        if (event.target.matches('.decide > div')) {
            handleDecision(event);
        }
    });

    function get_decision(target) {
        const movieId = target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        let decision = target.getAttribute('data-decision');
        if (movieElement.classList.contains('decided-' + decision)) {
            return 'remove';
        }
        return decision;
    }

    function handleDecision(event) {
        const movieId = event.target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        const decision = get_decision(event.target);

        const csrfToken = window.CineTagIt?.Utils?.getCsrfToken() || '';

        fetch(`/api/user/movies/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrfToken
            },
            body: JSON.stringify({movie_id: movieId, decision: decision, csrf_token: csrfToken})
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const classes_to_remove = ['decided-approve', 'decided-disapprove', 'decided-maybe'];
                    classes_to_remove.forEach(class_name => movieElement.classList.remove(class_name));
                    if (data["decision_status"] === decision) {
                        movieElement.classList.add("decided", "decided-" + data["decision_status"]);
                    } else {
                        movieElement.classList.remove("decided");
                    }
                    movieElement.classList.remove('hovered');
                } else if (data.error) {
                    if (window.CineTagIt?.UI?.displayMessage) {
                        window.CineTagIt.UI.displayMessage(data.error, 'danger');
                    } else {
                        alert(data.error);
                    }
                } else if (data.message) {
                    if (window.CineTagIt?.UI?.displayMessage) {
                        window.CineTagIt.UI.displayMessage(data.message, data.message_category || 'info');
                    } else {
                        alert(data.message);
                    }
                } else {
                    if (window.CineTagIt?.UI?.displayMessage) {
                        window.CineTagIt.UI.displayMessage('An error occurred. Please try again later.', 'danger');
                    } else {
                        alert('An error occurred. Please try again later.');
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                if (window.CineTagIt?.UI?.displayMessage) {
                    window.CineTagIt.UI.displayMessage(`Error: ${error.message || 'Unknown error'}`, 'danger');
                }
            });
    }
});