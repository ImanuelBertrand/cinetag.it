# 1. Use the official uv image for the build stage
FROM ghcr.io/astral-sh/uv:0.11.13-python3.14-trixie AS builder

# 2. Set the working directory
WORKDIR /app

# Install build dependencies for libsass and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*


# Build-time version stamp for static asset cache-busting
ARG STATIC_VERSION=dev
ENV STATIC_VERSION=${STATIC_VERSION}

# 3. Enable bytecode compilation for faster startups
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/venv
ENV PATH="/venv/bin:$PATH"

# 4. Copy only the lock and project files first
COPY uv.lock pyproject.toml package.json package-lock.json* ./

# 5. Install dependencies (without the app itself)
# --frozen ensures uv.lock is respected exactly
RUN uv sync --frozen --no-install-project --no-dev
RUN npm install --omit=dev

# 6. Copy the rest of the app
COPY . .

# 7. Sync the project (installs your app into the venv)
RUN uv sync --frozen --no-dev

# 8. Precompile assets
# Use TestingConfig to avoid needing a real DB/Redis during build
ENV FLASK_APP="app.create_app:create_app('testing')"
ENV DATABASE_URI="postgresql://placeholder:placeholder@localhost/placeholder"
RUN python -m flask build-assets

# Copy fullcalendar files to static directory
RUN target_dir="app/static/vendor/fullcalendar" && \
    mkdir -p "$target_dir" && \
    cp node_modules/fullcalendar/index.global.min.js "$target_dir/" && \
    cp -r node_modules/@fullcalendar/core/locales "$target_dir/"

# --- Production Stage ---
FROM python:3.14-slim AS production

LABEL org.opencontainers.image.title="CineTagIt"
LABEL org.opencontainers.image.description="Never miss a movie again!"
LABEL org.opencontainers.image.authors="Imanuel Bertrand"
LABEL org.opencontainers.image.url="https://github.com/ImanuelBertrand/cinetag.it"

# Install postgresql-client-18 from PGDG for scheduled DB backups.
# pg_dump must match the server major version; Debian trixie only ships v17.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /etc/apt/keyrings/postgresql.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/etc/apt/keyrings/postgresql.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /venv /venv

# Copy your application code
COPY . .

# Copy precompiled assets from the builder stage
# (This ensures we get the compiled dist/style.css)
COPY --from=builder /app/app/static/dist /app/app/static/dist
COPY --from=builder /app/app/static/vendor /app/app/static/vendor

# Carry the version stamp into the production image
ARG STATIC_VERSION=dev
ENV STATIC_VERSION=${STATIC_VERSION}

# Place the virtual env on the PATH so 'python' and 'gunicorn' work automatically
ENV UV_PROJECT_ENVIRONMENT=/venv
ENV PATH="/venv/bin:$PATH"

# Copy the entrypoint script
COPY docker/entrypoint.sh docker/entrypoint.sh
RUN chmod +x docker/entrypoint.sh

# Use the script to start the container
ENTRYPOINT ["./docker/entrypoint.sh"]

# --- Nginx Stage ---
FROM nginx:alpine AS nginx

COPY --from=builder /app/app/static/dist    /usr/share/nginx/html/static/dist
COPY --from=builder /app/app/static/vendor  /usr/share/nginx/html/static/vendor
COPY --from=builder /app/app/static/img     /usr/share/nginx/html/static/img
COPY --from=builder /app/app/static/js      /usr/share/nginx/html/static/js
RUN mkdir -p /usr/share/nginx/html/posters
COPY docker/nginx.conf /etc/nginx/nginx.conf

# --- Squid Stage ---
FROM ubuntu/squid:6.13-25.04_beta AS squid
COPY docker/squid/squid-prod.conf /etc/squid/squid.conf

# --- Development Stage ---
FROM production AS development

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN uv sync --frozen


RUN apt-get update && apt-get install -y \
    curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install

# Create group (gid 1001) and user (uid 1000) matching typical host IDs
RUN groupadd -g 1001 appgroup && \
    useradd -u 1000 -g 1001 -m appuser

RUN chown -R appuser:appgroup /venv

RUN mkdir -p /home/appuser/.local && \
    chown -R appuser:appgroup /home/appuser/.local

ENV PATH="/home/appuser/.local/bin:$PATH"
ENV FLASK_ENV=development

USER appuser
