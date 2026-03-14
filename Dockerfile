# 1. Use the official uv image for the build stage
FROM ghcr.io/astral-sh/uv:0.10.10-python3.14-trixie AS builder

# 2. Set the working directory
WORKDIR /app

# Install build dependencies for libsass and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*


# 3. Enable bytecode compilation for faster startups
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# 4. Copy only the lock and project files first
COPY uv.lock pyproject.toml package.json package-lock.json* ./

# 5. Install dependencies (without the app itself)
# --frozen ensures uv.lock is respected exactly
RUN uv sync --frozen --no-install-project --no-dev
RUN npm install

# 6. Copy the rest of the app
COPY . .

# 7. Sync the project (installs your app into the venv)
RUN uv sync --frozen --no-dev

# 8. Precompile assets
# Use TestingConfig to avoid needing a real DB/Redis during build
ENV FLASK_APP="app.create_app:create_app('testing')"
RUN .venv/bin/python -m flask build-assets

# Copy fullcalendar files to static directory
RUN mkdir -p app/static/vendor/fullcalendar && \
    cp node_modules/fullcalendar/index.global.min.js app/static/vendor/fullcalendar/ && \
    cp -r node_modules/@fullcalendar/core/locales app/static/vendor/fullcalendar/

# --- Final Runtime Stage ---
FROM python:3.14-slim

LABEL org.opencontainers.image.title="CineTagIt"
LABEL org.opencontainers.image.description="Never miss a movie again!"
LABEL org.opencontainers.image.authors="Imanuel Bertrand"
LABEL org.opencontainers.image.url="https://github.com/ImanuelBertrand/cinetag.it"

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy your application code
COPY . .

# Copy precompiled assets from the builder stage
# (This ensures we get the compiled dist/style.css)
COPY --from=builder /app/app/static/dist /app/app/static/dist
COPY --from=builder /app/app/static/vendor /app/app/static/vendor

# Place the virtual env on the PATH so 'python' and 'gunicorn' work automatically
ENV PATH="/app/.venv/bin:$PATH"

# Copy the entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Use the script to start the container
ENTRYPOINT ["./entrypoint.sh"]
