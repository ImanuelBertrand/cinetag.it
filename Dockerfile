# 1. Use the official uv image for the build stage
FROM ghcr.io/astral-sh/uv:0.10.4-python3.10-trixie AS builder

# 2. Set the working directory
WORKDIR /app

# 3. Enable bytecode compilation for faster startups
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# 4. Copy only the lock and project files first
COPY uv.lock pyproject.toml ./

# 5. Install dependencies (without the app itself)
# --frozen ensures uv.lock is respected exactly
RUN uv sync --frozen --no-install-project --no-dev

# 6. Copy the rest of the app
COPY . .

# 7. Sync the project (installs your app into the venv)
RUN uv sync --frozen --no-dev

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

# Place the virtual env on the PATH so 'python' and 'gunicorn' work automatically
ENV PATH="/app/.venv/bin:$PATH"

# Copy the entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Use the script to start the container
ENTRYPOINT ["./entrypoint.sh"]
