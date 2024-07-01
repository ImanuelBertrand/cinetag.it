document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('.decide').forEach(function (element) {
        element.addEventListener('click', function () {
            const movieId = this.getAttribute('data-movie-id');
            const decision = this.classList.contains('approve') ? 'approve' : 'disapprove';
            handleDecision(movieId, decision);
        });
    });

    function handleDecision(movieId, decision) {
        fetch(`/api/user/movies/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': window.cinetagit.csrf_token
            },
            body: JSON.stringify({movie_id: movieId, decision: decision, csrf_token: window.cinetagit.csrf_token})
        })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    const movieElement = document.getElementById(`movie-${movieId}`);
                    movieElement.classList.remove('approved', 'disapproved');
                    movieElement.classList.add(decision + 'd');
                } else if (data.error) {
                    alert(data.error);
                }
            })
            .catch(error => console.error('Error:', error));
    }
});