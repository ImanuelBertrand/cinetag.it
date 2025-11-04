"use strict";

// Reuse CineTagIt namespace
window.CineTagIt = window.CineTagIt || {};

CineTagIt.MovieDetails = {
    init: function () {
        // Initialize UI based on existing decided class
        document.querySelectorAll('.movie-item[id^="movie-"]').forEach(el => {
            const idMatch = el.id.match(/^movie-(\d+)$/);
            if (!idMatch) return;
            const movieId = idMatch[1];
            let status = null;
            if (el.classList.contains('decided-approve')) status = 'approve';
            else if (el.classList.contains('decided-maybe')) status = 'maybe';
            else if (el.classList.contains('decided-disapprove')) status = 'disapprove';
            this.updateDecisionUI(el, movieId, status);
        });

        // Delegate click events on decision controls (works even if re-rendered)
        document.addEventListener('click', (event) => {
            const target = event.target;
            if (target && target.closest('.decide > div') && target.getAttribute('data-movie-id')) {
                this.handleDecision(target);
            }
        });

        // Keyboard support: Enter/Space for decision buttons
        document.addEventListener('keydown', (event) => {
            const target = event.target;
            if (!target || !target.matches('.decide > div')) return;
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.handleDecision(target);
            }
        });
    },

    getDecision: function (target) {
        const movieId = target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        let decision = target.getAttribute('data-decision');
        if (movieElement.classList.contains('decided-' + decision)) {
            return 'remove';
        }
        return decision;
    },

    updateDecisionUI: function (movieElement, movieId, status) {
        // Update aria-pressed on buttons
        const container = movieElement.querySelector('.decide');
        if (container) {
            container.querySelectorAll('[data-decision]').forEach(btn => {
                const d = btn.getAttribute('data-decision');
                btn.setAttribute('aria-pressed', String(status === d));
            });
        }
        // Update visible label
        const label = document.getElementById(`decision-current-${movieId}`);
        if (label) {
            if (status === 'approve') {
                label.textContent = 'You tagged this as: 👍 Approve';
            } else if (status === 'maybe') {
                label.textContent = 'You tagged this as: 🤷 Maybe';
            } else if (status === 'disapprove') {
                label.textContent = 'You tagged this as: 👎 Disapprove';
            } else {
                label.textContent = 'You have not tagged this movie yet.';
            }
        }
    },

    handleDecision: function (target) {
        const movieId = target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        const decision = this.getDecision(target);

        const csrfToken = window.CineTagIt.Utils.getCsrfToken();

        fetch(`/api/user/movies/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrfToken
            },
            body: JSON.stringify({
                movie_id: movieId,
                decision: decision,
                csrf_token: csrfToken
            })
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
                    this.updateDecisionUI(movieElement, movieId, data["decision_status"] || null);
                } else if (data.error) {
                    window.CineTagIt.UI.displayMessage(data.error, 'danger');
                } else if (data.message) {
                    window.CineTagIt.UI.displayMessage(data.message, data.message_category || 'info');
                } else {
                    window.CineTagIt.UI.displayMessage('An error occurred. Please try again later.', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                window.CineTagIt.UI.displayMessage(`Error: ${error.message || 'Unknown error'}`, 'danger');
            });
    }
};

// Register module to initialize on base.js startup
CineTagIt.modules = CineTagIt.modules || {};
CineTagIt.modules.MovieDetails = function () {
    CineTagIt.MovieDetails.init();
};
