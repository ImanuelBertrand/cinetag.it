# CineTagIt

A self-hosted web app for tracking and sharing movie preferences with friends.

Connect your watchlist with friends, discover movies you both want to see, and get push notifications before upcoming releases.

## Features

- **Movie decisions** — mark movies as Approve, Maybe, or Disapprove
- **Friends** — add friends via friend codes and see movies you both approved
- **Release notifications** — push notifications days before a movie releases in your region
- **TMDB integration** — movie metadata, posters, and release dates via The Movie Database API
- **Infinite scroll** — fast paginated movie browsing with filtering

## Tech Stack

- **Backend:** Python 3.14, Flask, SQLAlchemy, PostgreSQL, Redis
- **Auth:** JWT (cookie + header), bcrypt
- **Frontend:** Vanilla JS, Jinja2 templates
- **Infrastructure:** Docker Compose, Nginx, Gunicorn, Squid proxy
- **CI/CD:** GitHub Actions (lint, test, Docker publish)

## Getting Started

### Prerequisites

- Docker and Docker Compose
- A [TMDB API key](https://www.themoviedb.org/settings/api) (free)

### Setup

```bash
# Clone the repo
git clone https://github.com/ImanuelBertrand/cinetag.it.git
cd cinetag.it

# Create your environment file
cp .env.sample .env
# Edit .env and fill in SECRET_KEY, JWT_SECRET_KEY, and TMDB_API_KEY

# Start all services
make up

# Run database migrations
make migrate
```

The app will be available at `http://localhost:8001`.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session secret (use a long random string) |
| `JWT_SECRET_KEY` | Yes | JWT signing secret (use a long random string) |
| `TMDB_API_KEY` | Yes | The Movie Database API key |
| `FLASK_ENV` | No | `development` / `production` (default: `development`) |
| `POSTGRES_PASSWORD` | No | Database password (default: `CHANGE_ME`) |
| `MAIL_SERVER` | No | SMTP server for email (optional) |

See `.env.sample` for the full list.

### Development Commands

```bash
make up       # Start all services
make down     # Stop all services
make migrate  # Run database migrations
make test     # Run test suite
make lint     # Run linter (ruff)
make fix      # Auto-fix lint issues
make shell    # Open a shell in the web container
make logs     # Follow service logs
```

## Running Tests

```bash
make test
# or with arguments:
make test args="-k test_auth -v"
```

## License

MIT — see [LICENSE](LICENSE).
