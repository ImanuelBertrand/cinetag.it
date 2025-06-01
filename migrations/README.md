# Database Migrations

This directory contains database migrations for the CineTagIt application. Migrations are managed using Flask-Migrate, which is a wrapper around Alembic.

## Running Migrations

To apply migrations to your database, run:

```bash
flask db upgrade
```

This will apply all pending migrations to bring your database schema up to date.

## Creating New Migrations

If you need to make changes to the database schema, you can create a new migration:

```bash
# For auto-generated migrations based on model changes
flask db migrate -m "Description of changes"

# For empty migration file you can fill manually
flask db revision -m "Description of changes"
```

## Migration Files

- `env.py`: Configuration for the migration environment
- `script.py.mako`: Template for generating new migration files
- `alembic.ini`: Alembic configuration file
- `versions/`: Directory containing individual migration scripts

## Migrations

### Initial Migration (`00_create_initial_tables.py`)

The initial migration creates all the core tables for the CineTagIt application:

1. `users` - For user accounts
2. `movies` - For movie information
3. `user_movies` - For user decisions about movies
4. `user_calendars` - For user calendar settings
5. `notification_channels` - For user notification preferences
6. `notifications` - For storing notification records
7. `movie_region_info` - For region-specific movie information (release dates)
8. `movie_language_info` - For language-specific movie information (titles, descriptions)
9. `allowed_refresh_tokens` - For JWT authentication
10. `misc_data` - For storing miscellaneous key-value data
11. `tmdb_languages` - For storing language information from TMDB
12. `tmdb_regions` - For storing region information from TMDB
13. `user_email_queue` - For queuing emails to be sent to users
14. `sent_confirmation_mails` - For tracking sent confirmation emails

### Friends Feature Migration (`01_add_friends_feature.py`)

The second migration adds support for the friends feature:

1. Adds `display_name` and `friend_code` columns to the `users` table
2. Creates the `friend_requests` table for managing friend requests
3. Creates the `friendships` table for storing established friendships
4. Generates friend codes for existing users with email addresses

## Important Notes

- Always back up your database before running migrations in production
- Test migrations in a development environment first
- The `db.create_all()` call has been removed from the application initialization, as tables are now created through migrations
