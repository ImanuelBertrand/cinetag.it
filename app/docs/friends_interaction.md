# Friends Interaction Feature: Common Movie Interests

## Overview
This document outlines the implementation of the friends interaction feature for CineTagIt, focusing on showing common movie interests between users. The feature extends the existing release display modes (list/calendar) with a friends filter to help users discover movies based on their friends' preferences.

## Feature Requirements
- Extend existing release display modes (list/calendar) with a friends filter
- Implement a multiselect filter to choose which friends to include
- Define filtering logic for showing/hiding movies based on friends' preferences
- Maintain privacy by not allowing direct access to friends' movie lists

## Filter Logic

### Basic Rules
1. **Hide movies marked as "NO"**: Movies that ANY selected friend has marked with "NO" (disapprove) will be hidden from the display.

### Additional Filter Options
When designing the filter logic, we need to consider several scenarios:

#### Scenario 1: Movies marked as "YES" by at least one friend
- **Include**: Show movies that at least one selected friend has marked as "YES" (approve)
- **Rationale**: This helps discover movies that friends are interested in

#### Scenario 2: Movies marked as "MAYBE" by friends
- **Include**: Show movies that friends have marked as "MAYBE"
- **Rationale**: These are movies friends are considering and might be worth discussing

#### Scenario 3: Movies with mixed responses
- If one friend has marked a movie as "YES" and another hasn't rated it at all:
  - **Include**: Show the movie with an indicator that not all friends have rated it
  - **Rationale**: This encourages discussion and sharing of opinions

#### Scenario 4: Movies with no ratings from friends
- **Optional Include**: Provide a toggle to show/hide movies that none of the selected friends have rated
- **Rationale**: This allows users to discover new movies that friends haven't considered yet

### Recommended Implementation
Based on the considerations above, we recommend implementing the following filter logic:

1. **Base Filter**: Hide all movies ANY selected friend has marked as "NO"
2. **Primary Filter**: Show movies that AT LEAST ONE selected friend has marked as "YES" or "MAYBE"
3. **Optional Toggle**: Include an option to show movies that none of the selected friends have rated

This approach balances discovery with respect for friends' negative opinions.

## Privacy Considerations
- Users cannot directly view a friend's complete movie list
- The filter only shows aggregate information (e.g., "2 of 3 friends liked this movie")
- Individual friend ratings are not displayed
- The system only reveals information about movies that appear in the user's own release list

## Technical Implementation

### Database Changes

#### Friendship Model
As defined in the friends_feature.md document, we'll use the Friendship model to determine which users are friends:

```python
class Friendship(db.Model):
    """
    Represents a bidirectional friendship between two users.

    This model stores connections between users. A single record represents
    a mutual friendship between two users. The relationship is not directional,
    so the order of user1_id and user2_id doesn't matter semantically.

    To maintain consistency and prevent duplicate records, we enforce that
    user1_id is always the lower ID value and user2_id is the higher ID value.
    """

    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    # Always the lower user ID of the two friends
    user1_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Always the higher user ID of the two friends
    user2_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships to the User model
    user1 = db.relationship(
        "User",
        foreign_keys=[user1_id],
        backref=db.backref("friendships_as_user1", lazy="dynamic"),
    )
    user2 = db.relationship(
        "User",
        foreign_keys=[user2_id],
        backref=db.backref("friendships_as_user2", lazy="dynamic"),
    )

    __table_args__ = (
        # Ensure uniqueness of the friendship pair
        db.Index("friendship_idx", "user1_id", "user2_id", unique=True),
        # Enforce user1_id < user2_id
        db.CheckConstraint("user1_id < user2_id", name="check_user_order"),
    )
```

The Friendship model includes several helper methods:

1. `create_friendship(user_a_id, user_b_id)`: Creates a new friendship ensuring the correct order of user IDs
2. `get_friendship(user_a_id, user_b_id)`: Retrieves a friendship between two users with defensive programming
3. `get_friends_of_user(user_id)`: Gets all friends of a user
4. `get_friends_with_details(user_id)`: Gets all friends with their details in an optimized query

### Backend Implementation

#### Extending the Movie List Query
We'll modify the `get_movie_list_query` function to support friend filtering:

```python
def get_movie_list_query(
    region: TmdbRegion,
    need_imdb: bool,
    need_poster: bool,
    user: User = None,
    user_decision: str = None,
    friend_ids: List[int] = None,
    include_unrated: bool = True,
):
    # Start with the existing query
    upcoming_movie_query = Movie.query.join(
        MovieRegionInfo,
        db.and_(
            MovieRegionInfo.region == region, MovieRegionInfo.movie_id == Movie.id
        ),
    ).filter(MovieRegionInfo.release_date > datetime.now().date())

    # Apply existing filters
    if need_imdb:
        upcoming_movie_query = upcoming_movie_query.filter(
            Movie.imdb_id.isnot(None)
        )

    if need_poster:
        poster_subquery = db.exists().where(
            db.and_(
                MovieLangInfo.movie_id == MovieRegionInfo.movie_id,
                MovieLangInfo.poster_path.isnot(None),
            )
        )
        upcoming_movie_query = upcoming_movie_query.filter(poster_subquery)

    # Apply user filters
    if user is not None:
        is_outer = user_decision is None
        upcoming_movie_query = upcoming_movie_query.join(
            UserMovie,
            db.and_(UserMovie.user_id == user.id, UserMovie.movie_id == Movie.id),
            isouter=is_outer,
        )

        if user_decision is None:
            upcoming_movie_query = upcoming_movie_query.filter(
                UserMovie.id.is_(None)
            )
        else:
            upcoming_movie_query = upcoming_movie_query.filter(
                UserMovie.decision == user_decision
            )

    # Apply friend filters if specified
    if friend_ids and len(friend_ids) > 0:
        # Subquery to find movies any friend has disapproved
        disapproved_subquery = db.session.query(UserMovie.movie_id).filter(
            db.and_(
                UserMovie.user_id.in_(friend_ids),
                UserMovie.decision == "disapprove"
            )
        ).subquery()

        # Exclude movies any friend has disapproved
        upcoming_movie_query = upcoming_movie_query.filter(
            ~Movie.id.in_(disapproved_subquery)
        )

        if not include_unrated:
            # Subquery to find movies at least one friend has approved or maybe'd
            approved_subquery = db.session.query(UserMovie.movie_id).filter(
                db.and_(
                    UserMovie.user_id.in_(friend_ids),
                    UserMovie.decision.in_(["approve", "maybe"])
                )
            ).subquery()

            # Only include movies at least one friend has approved or maybe'd
            upcoming_movie_query = upcoming_movie_query.filter(
                Movie.id.in_(approved_subquery)
            )

    return upcoming_movie_query
```

#### New Function to Get Friend Ratings
We'll add a new function to get aggregated friend ratings for movies:

```python
def get_friend_ratings(user: User, movie_ids: List[int], friend_ids: List[int] = None):
    """
    Get aggregated friend ratings for a list of movies.

    Args:
        user: The current user
        movie_ids: List of movie IDs to get ratings for
        friend_ids: Optional list of specific friend IDs to include
                   If None, includes all friends

    Returns:
        Dictionary mapping movie_id to rating counts
    """
    if not friend_ids:
        # Get all friend IDs if not specified
        friend_ids = Friendship.get_friends_of_user(user.id)

    if not friend_ids:
        return {}  # No friends to check

    # Query all relevant user_movies
    friend_ratings = UserMovie.query.filter(
        db.and_(
            UserMovie.user_id.in_(friend_ids),
            UserMovie.movie_id.in_(movie_ids)
        )
    ).all()

    # Organize by movie_id
    result = {}
    for movie_id in movie_ids:
        movie_ratings = [r for r in friend_ratings if r.movie_id == movie_id]
        result[movie_id] = {
            "approve_count": sum(1 for r in movie_ratings if r.decision == "approve"),
            "maybe_count": sum(1 for r in movie_ratings if r.decision == "maybe"),
            "disapprove_count": sum(1 for r in movie_ratings if r.decision == "disapprove"),
            "total_friends": len(friend_ids)
        }

    return result
```

#### Extending the get_movies_based_on_filter Function
We'll modify the `get_movies_based_on_filter` function to include friend ratings:

```python
def get_movies_based_on_filter(
    user: User, 
    mode: str, 
    need_imdb: bool = False, 
    need_poster: bool = False,
    friend_ids: List[int] = None,
    include_unrated: bool = True
) -> List[Dict[str, str]]:
    # Existing code...

    filtered_movies = get_movie_list_query(
        region, need_imdb, need_poster, filter_user, filter_decision,
        friend_ids, include_unrated
    )
    movie_ids = {m.id for m in filtered_movies}

    # Get friend ratings if friend_ids is provided
    friend_ratings = {}
    if friend_ids and len(friend_ids) > 0:
        friend_ratings = get_friend_ratings(user, list(movie_ids), friend_ids)

    # Rest of existing code...

    # Add friend_ratings to the result
    for movie in filtered_movies:
        # Existing movie processing code...

        movie_data = {
            "id": movie.id,
            "title": lang_info["title"],
            # Other existing fields...
            "decision": movie_decisions.get(movie.id),
            "all_release_dates": all_release_dates,
        }

        # Add friend ratings if available
        if movie.id in friend_ratings:
            movie_data["friend_ratings"] = friend_ratings[movie.id]

        result.append(movie_data)

    return sorted(result, key=lambda x: x["release_date"])
```

### API Changes

#### Modified Endpoint: Get Movies List
Extend the existing endpoint to support friend filtering:

```python
@api.route("/movies/<filter_mode>", methods=["GET"])
def get_movies_api(filter_mode):
    user = get_current_user()

    try:
        need_imdb = True  # TODO toggle in user settings
        need_poster = True  # TODO toggle in user settings

        # Parse friend filter parameters
        friend_ids = request.args.get("friend_ids")
        include_unrated = request.args.get("include_unrated", "true").lower() == "true"

        # Convert friend_ids from comma-separated string to list of integers
        if friend_ids:
            friend_ids = [int(id) for id in friend_ids.split(",")]

        return jsonify(
            {
                "success": True,
                "movies": get_movies_based_on_filter(
                    user, filter_mode, need_imdb, need_poster, 
                    friend_ids, include_unrated
                ),
            }
        )
    except UserFeedbackError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception:
        _logger.exception("Error fetching movies.")
        return jsonify({"success": False, "error": "Error fetching movies."})
```

#### New Endpoint: Get Friends List
Add a new endpoint to get the user's friends list:

```python
@friend_api.route("/list", methods=["GET"])
def get_friends_list():
    """Get the current user's friends list"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Get all friends with their details in a single efficient query
        friends = Friendship.get_friends_with_details(user.id)
        return jsonify({"success": True, "friends": friends})
    except Exception as e:
        _logger.exception(f"Error getting friends list: {e}")
        return (
            jsonify({"success": False, "error": "Error getting friends list."}),
            500,
        )
```

This implementation uses the optimized `get_friends_with_details` method from the Friendship model, which retrieves all friend details in a single query rather than making separate queries for each friendship.

### Frontend Implementation

#### Friends Filter Component
Add the friends filter to the movie list page:

```javascript
// Function to load friends list
async function loadFriends() {
    try {
        const response = await fetch('/api/user/friends');
        const data = await response.json();

        if (data.success) {
            const friendsFilter = document.getElementById('friends-filter');
            if (friendsFilter) {
                friendsFilter.innerHTML = data.friends.map(friend => 
                    `<option value="${friend.id}">${friend.display_name}</option>`
                ).join('');

                // Initialize the multiselect plugin
                $(friendsFilter).select2({
                    placeholder: "Select friends to filter by",
                    allowClear: true
                });

                // Add change event listener
                $(friendsFilter).on('change', applyFilters);
            }
        }
    } catch (error) {
        console.error('Error loading friends:', error);
    }
}

// Function to apply all filters
function applyFilters() {
    const movieContainers = document.querySelectorAll(".movie-container");
    const friendIds = $('#friends-filter').val();
    const includeUnrated = $('#show-unrated').is(':checked');

    // Store filter state
    localStorage.setItem('friendFilter', JSON.stringify({
        friendIds: friendIds,
        includeUnrated: includeUnrated
    }));

    // Reload movies with filters
    movieContainers.forEach(container => {
        const filterMode = container.getAttribute("data-filter-mode");
        fetchMoviesWithFilters(container, filterMode, friendIds, includeUnrated);
    });
}

// Modified fetch function to include friend filters
async function fetchMoviesWithFilters(movieContainer, filterMode, friendIds, includeUnrated) {
    try {
        let url = `/api/movies/${filterMode}`;

        // Add query parameters if filters are applied
        const params = new URLSearchParams();
        if (friendIds && friendIds.length > 0) {
            params.append('friend_ids', friendIds.join(','));
            params.append('include_unrated', includeUnrated);
            url += `?${params.toString()}`;
        }

        const response = await fetch(url);
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

// Modified render function to show friend ratings
function renderMovies(movieContainer, movies) {
    movieContainer.innerHTML = movies.map(movie => {
        const decisionClass = movie.decision ? `decided decided-${movie.decision}` : '';
        const posterClass = movie.poster_url ? '' : 'has-no-poster';

        // Add friend rating indicators
        let friendRatingHtml = '';
        if (movie.friend_ratings) {
            const ratings = movie.friend_ratings;
            const approveCount = ratings.approve_count;
            const maybeCount = ratings.maybe_count;
            const totalRated = approveCount + maybeCount;

            if (totalRated > 0) {
                const ratingClass = approveCount > 0 ? 
                    (maybeCount > 0 ? 'mixed-rating' : 'all-approve') : 
                    'all-maybe';

                friendRatingHtml = `
                    <div class="friend-rating ${ratingClass}">
                        <span class="rating-icon"></span>
                        <span class="rating-count">${totalRated}/${ratings.total_friends}</span>
                    </div>
                `;
            }
        }

        // Rest of the rendering code...

        return `
            <div class="movie-item hoverable ${decisionClass} ${posterClass}" id="movie-${movie.id}">
                <div class="decision-icon"></div>
                ${friendRatingHtml}
                ${poster}
                <div class="overlay">
                    <!-- Existing overlay content -->
                </div>
            </div>`;
    }).join("");
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", function() {
    // Add friends filter UI
    const filterContainer = document.querySelector('.filter-container');
    if (filterContainer) {
        const friendsFilterHtml = `
            <div class="filter-section">
                <label for="friends-filter">Filter by Friends:</label>
                <select id="friends-filter" multiple class="form-control">
                    <!-- Will be populated dynamically -->
                </select>
            </div>
            <div class="filter-option">
                <input type="checkbox" id="show-unrated" checked>
                <label for="show-unrated">Include movies not rated by friends</label>
            </div>
        `;

        filterContainer.insertAdjacentHTML('beforeend', friendsFilterHtml);

        // Add event listener for the checkbox
        document.getElementById('show-unrated').addEventListener('change', applyFilters);

        // Load friends list
        loadFriends();

        // Restore filter state from localStorage
        const savedFilter = JSON.parse(localStorage.getItem('friendFilter') || '{}');
        if (savedFilter.friendIds) {
            $('#friends-filter').val(savedFilter.friendIds).trigger('change');
        }
        if (savedFilter.includeUnrated !== undefined) {
            $('#show-unrated').prop('checked', savedFilter.includeUnrated);
        }
    }
});
```

#### CSS for Friend Rating Indicators
Add CSS for the friend rating indicators:

```css
.friend-rating {
    position: absolute;
    top: 5px;
    right: 5px;
    background: rgba(0, 0, 0, 0.7);
    border-radius: 12px;
    padding: 2px 8px;
    display: flex;
    align-items: center;
    z-index: 2;
}

.friend-rating .rating-icon {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 4px;
}

.all-approve .rating-icon {
    background-color: #4CAF50; /* Green */
}

.all-maybe .rating-icon {
    background-color: #FFC107; /* Yellow */
}

.mixed-rating .rating-icon {
    background: linear-gradient(135deg, #4CAF50 50%, #FFC107 50%);
}

.rating-count {
    color: white;
    font-size: 12px;
}
```

## Implementation Phases

### Phase 1: Backend Changes
- Add friend_ids and include_unrated parameters to get_movie_list_query
- Implement get_friend_ratings function
- Modify get_movies_based_on_filter to include friend ratings
- Update API endpoints to support friend filtering

### Phase 2: Frontend Implementation
- Add the friends filter UI components
- Implement the filter logic in JavaScript
- Add visual indicators for friend ratings

### Phase 3: Testing and Refinement
- Test with various friend combinations and movie ratings
- Gather feedback and refine the implementation
- Optimize performance for users with many friends

## Future Enhancements
- Add ability to see which specific friends liked a movie (with privacy controls)
- Implement movie recommendations based on friend preferences
- Add a "suggest to friend" feature for movies
- Create a "movie night" planning feature for friends
