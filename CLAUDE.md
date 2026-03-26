# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CineTagIt** is a self-hosted Flask web app for tracking and sharing movie preferences. Users rate movies (Approve/Maybe/Disapprove), connect with friends, receive push notifications for upcoming releases, and export iCal feeds. Movie data is synced from The Movie Database (TMDB) API.

## Environment

Claude runs **inside the web container**. Docker commands (`make up`, `make build`, `docker compose ...`) are not available. If a change requires a container rebuild or restart (e.g. changes to `Dockerfile`, `docker-compose.yml`, environment variables, or installed packages), stop, tell the user what is needed, and wait for them to do it.

Python dependencies are managed with **`uv`**. To add or update packages, edit `pyproject.toml` and run `uv sync` — do not use `pip` directly.

## Common Commands

Tests and other in-container commands can be run directly with `uv run`:

```bash
uv run pytest                                               # Run full test suite
uv run pytest tests/services/test_user_service.py -v       # Run specific test file
uv run pytest -k test_name                                  # Run matching test(s)

uv run ruff check .          # Lint (read-only)
uv run ruff format --check . # Format validation (read-only)
uv run ruff check --fix .    # Lint + autofix
uv run ruff format .         # Autoformat

uv run ty check              # Type checking
```

The `make` targets (e.g. `make test`, `make lint`) are wrappers around these commands and require Docker — use the `uv run` equivalents directly.

## Architecture

### Request Flow

```
HTTP → Nginx (port 8001) → Gunicorn (port 8000) → Flask App
```

The Flask app is created by `app/create_app.py` (factory pattern). Extensions are initialized in `app/extensions.py` (SQLAlchemy, Redis, JWT, Bcrypt, APScheduler, Flask-Mail). Three blueprints handle routing: `html` (server-rendered pages + auth), `api` (JSON REST), `friend_api` (friend operations).

### Layer Structure

- **`app/models/`** — SQLAlchemy ORM models (18 files). Core models: `User`, `Movie`, `UserMovie` (the approve/maybe/disapprove decision), `Friendship`, `MovieLanguageInfo`, `MovieRegionInfo`, `NotificationChannel`.
- **`app/routes/`** — Flask blueprints. `html.py` handles server-rendered pages and auth forms; `api.py` handles JSON REST endpoints for movies and events; `friend_api.py` handles friend operations.
- **`app/services/`** — Business logic. `UserService` (auth, events), `TmdbService` (TMDB sync), `FriendService`, `ImageService` (poster caching), `MaintenanceService` (cleanup), `MovieService`.
- **`app/utils/`** — Cross-cutting concerns: `auth.py` (JWT), `email.py` (async queue), `notifications.py` + `webpush.py` (Web Push/VAPID), `tmdb.py` (TMDB client), `ics.py` (iCal).
- **`app/scheduler.py`** — APScheduler jobs: every 1h (upcoming movies, push notifications), every 15min (stale movie refresh), every 24h (TMDB sync, cleanup), every 15s (email queue drain).

### Authentication

JWT tokens stored in cookies. `app/utils/auth.py` handles token generation. `@before_request` hook authenticates each request; `@after_request` hook refreshes tokens. Temporary guest users exist for unauthenticated browsing.

### Database

PostgreSQL with Alembic migrations (`migrations/`). The test suite uses a dedicated `*_test` database — never the dev/prod DB. Tests use session-scoped app fixture; tables are row-deleted (not DDL-dropped) between tests via `clean_test_db` autouse fixture.

### External Services

- **TMDB API** — accessed through `app/utils/tmdb.py`, cached via Squid proxy (see `docker/squid/`)
- **Redis** — caching layer
- **SMTP/MailHog** — email, async queue in DB drained by scheduler
- **Web Push** — VAPID keys in `app/utils/webpush.py`

### Frontend

Jinja2 templates + vanilla JS + SCSS (compiled by LibSass via Flask-Assets). FullCalendar for event display. Service Worker (`app/static/js/sw.js`) for PWA capabilities. No JS framework.

## Configuration

`app/config.py` loads environment variables. Key env vars: `DATABASE_URL`, `REDIS_URL`, `TMDB_API_KEY`, `SECRET_KEY`, `VAPID_PRIVATE_KEY`. The config class includes a safety assertion that prevents tests from accidentally running against a non-test database.

## Code Style

- **Python**: Ruff (line length 88). Run `make fix` before committing.
- **JS/HTML**: Prettier with `prettier-plugin-jinja-template`.
- **Type checking**: `ty` (not mypy).
- CI runs ruff → prettier → pylint → ty → pytest in sequence.
