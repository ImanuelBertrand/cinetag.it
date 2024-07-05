"use strict";

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('.decide > div').forEach(function (element) {
        element.addEventListener('click', handleDecision);
    });

    function get_decision(target) {
        const movieId = event.target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        let decision = event.target.getAttribute('data-decision');
        if (movieElement.classList.contains('decided-' + decision)) {
            return 'remove';
        }
        return decision;
    }

    function handleDecision(event) {
        const movieId = event.target.getAttribute('data-movie-id');
        const movieElement = document.getElementById(`movie-${movieId}`);
        const decision = get_decision(event.target);

        function get_csrf_token() {
            const cookies = document.cookie.split('; ');
            if (!cookies) return '';
            for (let i = 0; i < cookies.length; i++) {
                if (cookies[i].startsWith('csrf_access_token')) {
                    return cookies[i].split('=')[1];
                }
            }
            return '';
        }

        fetch(`/api/user/movies/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': get_csrf_token()
            },
            body: JSON.stringify({movie_id: movieId, decision: decision, csrf_token: get_csrf_token()})
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
                    alert(data.error);
                } else if (data.message) {
                    alert(data.message);
                } else {
                    alert('An error occurred. Please try again later.');
                }
            })
            .catch(error => console.error('Error:', error));
    }
});
