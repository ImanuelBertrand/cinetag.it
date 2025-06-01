# Friends Feature for CineTagIt

## Overview
The Friends feature allows CineTagIt users to connect with other users, similar to social media platforms. This enables users to share movie preferences, recommendations, and viewing plans with their friends.

## Feature Requirements
- Users should be able to 'link' with other accounts
- Users need display names (non-unique)
- Friends should be addable by private links or private account IDs
- Friendships are only active when both users have added each other (mutual consent)
- Privacy is maintained by requiring mutual connection

## Database Schema Changes

### User Model Updates
The existing User model needs to be updated to include a display name field and friend code:

```python
# Add to existing User model
# User's display name, used throughout the application
display_name = db.Column(db.String(200), nullable=True)
# Unique code for adding friends, only for registered users
friend_code = db.Column(db.String(64), unique=True, nullable=True)
```

Note that friend codes are only generated for registered users (non-temporary users with an email address). This helps prevent unnecessary friend code generation and reduces the risk of collisions.

### New Models

#### FriendRequest Model
```python
class FriendRequest(db.Model):
    __tablename__ = "friend_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], backref=db.backref("sent_friend_requests", lazy="dynamic"))
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref=db.backref("received_friend_requests", lazy="dynamic"))

    __table_args__ = (
        db.Index("friend_request_idx", "requester_id", "recipient_id", unique=True),
    )
```

#### Friendship Model
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

## Friend Code Generation

We implement a word-based hash system for friend codes, similar to the "correct-horse-battery-staple" example. This makes codes more memorable and user-friendly than random strings.

### Word Lists

Word lists are stored in data files to allow for larger vocabularies and easier updates:

- `adjectives.txt`: Contains adjectives like "happy", "brave", "clever", etc.
- `nouns.txt`: Contains nouns like "cat", "dog", "bird", etc.
- `verbs.txt`: Contains verbs like "runs", "jumps", "swims", etc.

```python
# Load word lists from data files
def load_words(filename):
    """
    Load words from a data file
    """
    data_dir = Path(__file__).parent.parent / "data"
    file_path = data_dir / filename

    if not file_path.exists():
        # Fallback to minimal word lists if files don't exist
        if filename == "adjectives.txt":
            return ["happy", "brave", "clever", "kind", "wise"]
        elif filename == "nouns.txt":
            return ["cat", "dog", "bird", "tree", "house"]
        elif filename == "verbs.txt":
            return ["runs", "jumps", "swims", "reads", "writes"]

    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]

# Load word lists
ADJECTIVES = load_words("adjectives.txt")
NOUNS = load_words("nouns.txt")
VERBS = load_words("verbs.txt")
```

### Generating Friend Codes

```python
def generate_friend_code():
    """
    Generate a memorable friend code using common words
    Format: adjective-noun-verb-noun (e.g., "happy-dog-jumps-fence")
    """
    adjective = random.choice(ADJECTIVES)
    noun1 = random.choice(NOUNS)
    verb = random.choice(VERBS)
    noun2 = random.choice(NOUNS)

    # Combine words with hyphens
    return f"{adjective}-{noun1}-{verb}-{noun2}"
```

### Ensuring Uniqueness

To ensure friend codes are unique, we use a try-insert-catch pattern that attempts to insert the code into the database and catches any uniqueness violations:

```python
def _generate_unique_friend_code(self):
    """
    Helper method to generate a unique friend code.
    """
    max_attempts = 10  # Reasonable number of attempts
    old_friend_code = self.friend_code  # Store the old code in case we need to restore it

    for _ in range(max_attempts):
        try:
            # Generate a new code
            self.friend_code = generate_unique_friend_code([])
            db.session.add(self)
            # Try to commit - will fail if code already exists due to unique constraint
            db.session.commit()
            return self.friend_code
        except Exception as e:
            # If commit fails due to duplicate code, rollback and try again
            db.session.rollback()
            # Restore the old friend code if needed
            if old_friend_code:
                self.friend_code = old_friend_code
            if "UNIQUE constraint failed" not in str(e) and "duplicate key" not in str(e):
                # If it's not a uniqueness violation, re-raise the exception
                raise

    # If we've exhausted our attempts, fall back to the old approach
    # This should be extremely rare
    query = User.query.filter(User.friend_code.isnot(None))
    existing_codes = [user.friend_code for user in query.all()]
    self.friend_code = generate_unique_friend_code(existing_codes)
    db.session.add(self)

    return self.friend_code
```

This approach is more scalable than loading all existing codes into memory, as it only falls back to that method if multiple insertion attempts fail.

## API Endpoints

### Friend Management

#### 1. Get Friend Code
```
GET /api/friends/code
```
Returns the user's friend code.

#### 2. Send Friend Request by Code
```
POST /api/friends/request
{
  "friend_code": "happy-dog-jumps-fence"
}
```
Sends a friend request to the user with the specified friend code.

#### 3. Send Friend Request by Link
```
GET /friends/add/{encrypted_user_id}
```
Web route that processes a friend request from a shared link.

#### 4. Get Friend Requests
```
GET /api/friends/requests
```
Returns a list of pending friend requests.

#### 5. Respond to Friend Request
```
POST /api/friends/requests/{request_id}/respond
{
  "action": "accept" | "reject"
}
```
Accept or reject a friend request.

#### 6. Get Friends List
```
GET /api/friends
```
Returns a list of the user's friends.

#### 7. Remove Friend
```
DELETE /api/friends/{friend_id}
```
Removes a friend from the user's friend list.

### Friend Interaction

#### 1. Get Friend's Movie Preferences
```
GET /api/friends/{friend_id}/movies
```
Returns a list of movies that the friend has approved or marked as "maybe".

#### 2. Get Common Movies
```
GET /api/friends/{friend_id}/movies/common
```
Returns a list of movies that both the user and their friend have approved.

## User Interface Considerations

### Profile Settings
- Add a section in user settings for display name
- Show the user's friend code
- Provide a "Copy Link" button to generate a shareable friend link

### Friends Management
- Create a Friends page with tabs for:
  - Friends List
  - Pending Requests
  - Add Friend

### Friend Interaction
- Add a way to view a friend's approved movies
- Show common movie interests
- Potentially add a way to suggest movies to friends

## Privacy and Security Considerations

### Privacy
- Friendship is only established with mutual consent
- Users can remove friends at any time
- Friend requests can be rejected
- No public user search or directory

### Security
- Friend codes should be sufficiently complex to prevent guessing
- Friend links should be encrypted and contain expiration timestamps
- Rate limiting should be implemented for friend requests to prevent abuse
- Validation should be performed on all inputs

## Implementation Phases

### Phase 1: Core Functionality
- Update User model with display_name and friend_code
- Implement FriendRequest and Friendship models
- Create basic API endpoints for friend management
- Implement friend code generation

### Phase 2: User Interface
- Add profile settings for display name
- Create Friends management page
- Implement friend request notifications

### Phase 3: Friend Interaction
- Implement viewing friend's movie preferences
- Add common movie interests feature
- Create movie suggestion functionality

## Future Enhancements
- Group creation for movie clubs
- Shared watchlists
- Movie night planning
- Chat or messaging functionality
- Activity feed showing friends' recent movie ratings
