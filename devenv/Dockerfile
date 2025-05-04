FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p /app/app/logs /app/storage/posters

# Set environment variables
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=development
ENV CONFIG_FILE=/app/devenv/docker-config.yaml

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "wsgi.py"]
