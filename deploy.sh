#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
PROJECT_DIR="/var/www/cinetag.it"
VENV_PATH="${PROJECT_DIR}/venv" # IMPORTANT: Change this to your virtual environment path
GIT_USER="cinetag"
APACHE_SERVICE="apache2"
CONFIRMATION_URL="https://cinetag.it/" # URL to check after deployment
MAX_RETRIES=10
RETRY_DELAY=1
UV_BIN="/home/imanuel/.local/bin/uv"

uv_cmd() {
    sudo -u "${GIT_USER}" \
    UV_PROJECT_ENVIRONMENT="${VENV_PATH}" \
    UV_CACHE_DIR="${PROJECT_DIR}/.uv_cache" \
    "${UV_BIN}" "$@"
}

# --- Functions for logging and error handling ---
log_info() {
    echo "[INFO] $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo "[ERROR] $(date +'%Y-%m-%d %H:%M:%S') - $1" >&2
}

log_warning() {
    echo "[WARNING] $(date +'%Y-%m-%d %H:%M:%S') - $1"
}

handle_exit() {
    local exit_code=$?
    if [ ${exit_code} -ne 0 ]; then
        log_error "Deployment script failed with exit code ${exit_code} at line ${BASH_LINENO[0]}."
        log_error "Check the logs above for specific error messages."
        log_error "For assistance, contact the system administrator or development team."
        log_error "You may need to manually restore the previous state if partial deployment occurred."
    else
        log_info "Deployment script completed successfully."
    fi
}

# Register the exit handler
trap handle_exit EXIT

# --- Main Script ---

log_info "Starting Cinetag deployment script..."

# Refresh sudo timestamp upfront to avoid delays later
log_info "Requesting sudo privileges upfront..."
if sudo -v; then
    log_info "Sudo privileges confirmed."
else
    log_error "Failed to obtain sudo privileges. Please run the script again."
    exit 1
fi

# Navigate to the project directory
log_info "Changing directory to ${PROJECT_DIR}..."
if cd "${PROJECT_DIR}"; then
    log_info "Successfully changed directory to ${PROJECT_DIR}."
else
    log_error "Failed to change directory to ${PROJECT_DIR}. Please check the path."
    exit 1
fi

# Pull the latest code
log_info "Pulling latest code from git repository as user ${GIT_USER}..."
if sudo -u "${GIT_USER}" git pull; then
    log_info "Git pull successful."
else
    log_error "Git pull failed."
    exit 1
fi


log_info "Syncing dependencies with uv..."
# 'uv sync' automatically creates/updates the .venv to match uv.lock
if uv_cmd sync --frozen; then
    log_info "Dependencies synced successfully using uv.lock."
else
    log_error "uv sync failed. Check pyproject.toml and uv.lock consistency."
    exit 1
fi

# Run database migrations using 'uv run'
# This automatically uses the correct virtual environment
log_info "Running database migrations..."
if uv_cmd run flask db upgrade; then
    log_info "Database migrations completed successfully."
else
    log_error "Failed to run database migrations."
    log_error "Try running 'uv run flask db stamp head' if the DB is already up-to-date."
    exit 1
fi

# Reload Apache
log_info "Reloading Apache service (${APACHE_SERVICE})..."
if sudo service "${APACHE_SERVICE}" reload; then
    log_info "Apache reloaded successfully."
else
    log_error "Failed to reload Apache. This could be due to:"
    log_error "  - Syntax errors in Apache configuration files"
    log_error "  - Apache service not running"
    log_error "  - Insufficient permissions"
    log_error "Troubleshooting steps:"
    log_error "  1. Check Apache configuration: sudo apache2ctl configtest"
    log_error "  2. Check Apache status: sudo systemctl status ${APACHE_SERVICE}"
    log_error "  3. Check Apache error logs: sudo tail -n 50 /var/log/apache2/error.log"
    log_error "  4. Try restarting Apache instead: sudo service ${APACHE_SERVICE} restart"
    exit 1
fi


# Confirmation check
log_info "Attempting to confirm application status at ${CONFIRMATION_URL}"
attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    if [ -n "$BASIC_AUTH_USER" ] && [ -n "$BASIC_AUTH_PASSWORD" ]; then
        http_status_code=$(curl --silent --output /dev/null --write-out "%{http_code}" -u "${BASIC_AUTH_USER}:${BASIC_AUTH_PASSWORD}" "${CONFIRMATION_URL}")
    else
        http_status_code=$(curl --silent --output /dev/null --write-out "%{http_code}" "${CONFIRMATION_URL}")
    fi
    if [ "${http_status_code}" -eq 200 ]; then
        log_info "Confirmation successful: Received HTTP 200 from ${CONFIRMATION_URL} on attempt ${attempt}."
        break
    else
        log_warning "Attempt ${attempt}/${MAX_RETRIES} failed: Received HTTP ${http_status_code}."
        log_info "Waiting ${RETRY_DELAY} second(s) before retrying..."
        if [ $attempt -eq $MAX_RETRIES ]; then
            log_error "Confirmation failed after ${MAX_RETRIES} attempts. Final HTTP status: ${http_status_code}."
            log_error "This indicates the application is not responding correctly after deployment."
            log_error "Possible issues and solutions:"
            log_error "  - Application error: Check application logs at ${PROJECT_DIR}/app/logs/"
            log_error "  - Database connection issues: Verify database connectivity and credentials"
            log_error "  - Apache configuration: Check if the site is properly configured in Apache"
            log_error "  - Permissions: Ensure file permissions are correct for web server access"
            log_error "  - Firewall/Network: Verify the URL is accessible from this server"
            log_error ""
            log_error "Troubleshooting steps:"
            log_error "  1. Check Apache error logs: sudo tail -n 50 /var/log/apache2/error.log"
            log_error "  2. Check application logs: tail -n 50 ${PROJECT_DIR}/app/logs/*"
            log_error "  3. Verify Apache is running: sudo systemctl status ${APACHE_SERVICE}"
            log_error "  4. Try manually accessing the site from the server: curl -v ${CONFIRMATION_URL}"
            log_error "  5. Consider rolling back to the previous version if needed"
            exit 1
        fi
        attempt=$((attempt + 1))
        sleep $RETRY_DELAY
    fi
done


log_info "Cinetag deployment script finished."

# Exit with 0 explicitly if all went well (trap will catch this)
exit 0


