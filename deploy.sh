#!/bin/bash
set -euo pipefail

cd /srv/docker/cinetagit

# --- Configuration ---
APP_IMAGE="ghcr.io/imanuelbertrand/cinetag.it:latest"
NGINX_IMAGE="ghcr.io/imanuelbertrand/cinetag.it-nginx:latest"
LOG_FILE="/srv/docker/cinetagit/deploy.log"
STATE_FILE="/srv/docker/cinetagit/.deploy_pending"
STALE_THRESHOLD=900  # 15 minutes in seconds

# --- Logging ---
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2" | tee -a "$LOG_FILE"
}

# --- 1. Get local digests ---
LOCAL_APP_DIGEST=$(docker image inspect "$APP_IMAGE" --format='{{index .RepoDigests 0}}' 2>/dev/null | cut -d'@' -f2 || echo "")
LOCAL_NGINX_DIGEST=$(docker image inspect "$NGINX_IMAGE" --format='{{index .RepoDigests 0}}' 2>/dev/null | cut -d'@' -f2 || echo "")

# --- 2. Get remote digests via crane ---
REMOTE_APP_DIGEST=$(/home/imanuel/bin/crane digest "$APP_IMAGE" 2>>"$LOG_FILE") || {
    log "ERROR" "Failed to fetch remote app digest"
    exit 1
}
REMOTE_NGINX_DIGEST=$(/home/imanuel/bin/crane digest "$NGINX_IMAGE" 2>>"$LOG_FILE") || {
    log "ERROR" "Failed to fetch remote nginx digest"
    exit 1
}

# --- 3. Determine what changed ---
APP_CHANGED=false
NGINX_CHANGED=false

if [ "$LOCAL_APP_DIGEST" != "$REMOTE_APP_DIGEST" ] && [ -n "$REMOTE_APP_DIGEST" ]; then
    APP_CHANGED=true
fi
if [ "$LOCAL_NGINX_DIGEST" != "$REMOTE_NGINX_DIGEST" ] && [ -n "$REMOTE_NGINX_DIGEST" ]; then
    NGINX_CHANGED=true
fi

# --- 4. Deploy logic ---
if [ "$APP_CHANGED" = true ] && [ "$NGINX_CHANGED" = true ]; then
    # All changed — deploy immediately
    log "INFO" "All images changed. Deploying immediately."
    rm -f "$STATE_FILE"

elif [ "$APP_CHANGED" = true ] || [ "$NGINX_CHANGED" = true ]; then
    # Only some changed — check if we've been waiting long enough
    CHANGED_NAMES=""
    WAITING_NAMES=""
    [ "$APP_CHANGED" = true ]   && CHANGED_NAMES="${CHANGED_NAMES:+$CHANGED_NAMES, }App"   || WAITING_NAMES="${WAITING_NAMES:+$WAITING_NAMES, }App"
    [ "$NGINX_CHANGED" = true ] && CHANGED_NAMES="${CHANGED_NAMES:+$CHANGED_NAMES, }Nginx" || WAITING_NAMES="${WAITING_NAMES:+$WAITING_NAMES, }Nginx"

    if [ -f "$STATE_FILE" ]; then
        PENDING_SINCE=$(cat "$STATE_FILE")
        ELAPSED=$(( $(date +%s) - PENDING_SINCE ))

        if [ "$ELAPSED" -ge "$STALE_THRESHOLD" ]; then
            log "WARN" "${CHANGED_NAMES} changed but ${WAITING_NAMES} still stale after ${ELAPSED}s. Deploying anyway to self-correct."
            rm -f "$STATE_FILE"
        else
            log "INFO" "${CHANGED_NAMES} changed, waiting for ${WAITING_NAMES} (${ELAPSED}s / ${STALE_THRESHOLD}s elapsed)."
            exit 0
        fi
    else
        # First time seeing a partial change — record timestamp and wait
        date +%s > "$STATE_FILE"
        log "INFO" "${CHANGED_NAMES} changed, ${WAITING_NAMES} not yet. Starting wait timer."
        exit 0
    fi

else
    # Nothing changed
    # Clean up stale state file if images have converged
    if [ -f "$STATE_FILE" ]; then
        log "INFO" "No changes detected. Clearing stale pending state."
        rm -f "$STATE_FILE"
    fi
    exit 0
fi

# --- 5. Deploy ---
log "INFO" "Pulling images..."
if docker compose pull 2>>"$LOG_FILE"; then
    log "INFO" "Pull successful. Starting containers..."
    if docker compose up -d 2>>"$LOG_FILE"; then
        log "INFO" "Deploy complete. App: ${REMOTE_APP_DIGEST:0:16}... Nginx: ${REMOTE_NGINX_DIGEST:0:16}..."
    else
        log "ERROR" "docker compose up -d failed!"
        exit 1
    fi
else
    log "ERROR" "docker compose pull failed!"
    exit 1
fi
