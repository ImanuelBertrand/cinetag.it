FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy lockfile and project metadata
COPY pyproject.toml uv.lock ./

# Sync dependencies (without installing the project itself)
RUN uv sync --frozen --no-install-project

COPY . .

# Create necessary directories
RUN mkdir -p /app/app/logs /app/storage/posters

# Set environment variables
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=development
ENV CONFIG_FILE=/app/devenv/docker-config.yaml
# Ensure uv-installed packages are on the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application using uv
CMD ["uv", "run", "wsgi.py"]
