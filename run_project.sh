#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# RL_AGENT - Docker Compose Project Launcher
# ============================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

DEFAULT_FRONTEND_PORT=8080
BACKEND_PORT=8000

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

log() {
    echo
    echo "==> $1"
}

error() {
    echo
    echo "ERROR: $1" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ------------------------------------------------------------
# Check Docker
# ------------------------------------------------------------

if ! command_exists docker; then
    error "Docker is not installed or not available in PATH."
fi

if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running or your user cannot access it."
fi

# ------------------------------------------------------------
# Force system Docker instead of Podman/user socket
# ------------------------------------------------------------

unset DOCKER_HOST
unset DOCKER_CONTEXT
unset DOCKER_TLS_VERIFY
unset DOCKER_CERT_PATH

# ------------------------------------------------------------
# Detect Docker Compose
# ------------------------------------------------------------

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
elif command_exists docker-compose; then
    COMPOSE_CMD=(docker-compose)
else
    error "Docker Compose is not installed."
fi

log "Project root: $ROOT_DIR"
echo "Compose command: ${COMPOSE_CMD[*]}"

# ------------------------------------------------------------
# Check docker-compose.yml
# ------------------------------------------------------------

if [[ ! -f "$ROOT_DIR/docker-compose.yml" && \
      ! -f "$ROOT_DIR/compose.yml" && \
      ! -f "$ROOT_DIR/compose.yaml" ]]; then

    error "No docker-compose.yml, compose.yml, or compose.yaml found."
fi

# ------------------------------------------------------------
# Validate Compose configuration
# ------------------------------------------------------------

log "Validating Docker Compose configuration..."

if ! "${COMPOSE_CMD[@]}" config >/dev/null; then
    error "docker-compose configuration is invalid."
fi

echo "Compose configuration: OK"

# ------------------------------------------------------------
# Detect obsolete 'version:' field
# ------------------------------------------------------------

if grep -qE '^[[:space:]]*version:[[:space:]]*' docker-compose.yml 2>/dev/null; then
    echo
    echo "WARNING: docker-compose.yml contains the obsolete 'version:' field."
    echo "Docker Compose ignores it."
    echo "You should remove the 'version:' line from docker-compose.yml."
fi

# ------------------------------------------------------------
# Determine frontend port
# ------------------------------------------------------------

FRONTEND_PORT="$DEFAULT_FRONTEND_PORT"

# Try to extract host port mapped to container port 80.
DETECTED_PORT="$(
    "${COMPOSE_CMD[@]}" config 2>/dev/null |
    awk '
        /published:/ {
            published=$2
        }
        /target: 80/ {
            if (published != "") {
                print published
                exit
            }
        }
    ' || true
)"

if [[ -n "$DETECTED_PORT" ]]; then
    FRONTEND_PORT="$DETECTED_PORT"
fi

echo "Frontend port requested: $FRONTEND_PORT"

# ------------------------------------------------------------
# Check whether a host port is available
# ------------------------------------------------------------

port_is_used() {
    local port="$1"

    if command_exists ss; then
        ss -ltnH 2>/dev/null |
            awk -v p=":${port}" '$4 ~ p"$" { found=1 } END { exit !found }'
        return $?
    fi

    if command_exists lsof; then
        lsof -iTCP:"$port" -sTCP:LISTEN -n >/dev/null 2>&1
        return $?
    fi

    return 1
}

# ------------------------------------------------------------
# Automatically find a free frontend port
# ------------------------------------------------------------

if port_is_used "$FRONTEND_PORT"; then

    echo
    echo "Port $FRONTEND_PORT is already in use."

    # Check if one of our own project containers owns it.
    PROJECT_CONTAINERS="$(
        docker ps \
            --filter "label=com.docker.compose.project=rl_agent" \
            --format '{{.Names}}' 2>/dev/null || true
    )"

    if [[ -n "$PROJECT_CONTAINERS" ]]; then
        echo "Existing RL_AGENT containers detected."
    fi

    NEW_PORT=$((FRONTEND_PORT + 1))

    while port_is_used "$NEW_PORT"; do
        NEW_PORT=$((NEW_PORT + 1))

        if [[ "$NEW_PORT" -gt 8999 ]]; then
            error "Could not find a free frontend port."
        fi
    done

    FRONTEND_PORT="$NEW_PORT"

    echo "Using free frontend port: $FRONTEND_PORT"
else
    echo "Port $FRONTEND_PORT is available."
fi

# ------------------------------------------------------------
# Export frontend port for docker-compose.yml
# ------------------------------------------------------------

export FRONTEND_PORT

# ------------------------------------------------------------
# Stop old project containers
# ------------------------------------------------------------

log "Stopping existing RL_AGENT containers..."

"${COMPOSE_CMD[@]}" down --remove-orphans >/dev/null 2>&1 || true

echo "Old containers stopped."

# ------------------------------------------------------------
# Build images
# ------------------------------------------------------------

log "Building Docker images..."

"${COMPOSE_CMD[@]}" build

echo "Docker images built successfully."

# ------------------------------------------------------------
# Start application
# ------------------------------------------------------------

log "Starting RL_AGENT..."

"${COMPOSE_CMD[@]}" up -d

# ------------------------------------------------------------
# Wait for containers
# ------------------------------------------------------------

log "Checking containers..."

sleep 2

"${COMPOSE_CMD[@]}" ps

# ------------------------------------------------------------
# Verify backend
# ------------------------------------------------------------

if docker ps --format '{{.Names}}' | grep -q 'rl_agent-backend'; then
    echo
    echo "Backend container: RUNNING"
else
    echo
    echo "WARNING: Backend container may not be running."
fi

# ------------------------------------------------------------
# Verify frontend
# ------------------------------------------------------------

if docker ps --format '{{.Names}}' | grep -q 'rl_agent-frontend'; then
    echo "Frontend container: RUNNING"
else
    echo "WARNING: Frontend container may not be running."
fi

# ------------------------------------------------------------
# Final information
# ------------------------------------------------------------

echo
echo "============================================================"
echo " RL_AGENT started successfully"
echo "============================================================"
echo
echo "Frontend:"
echo "  http://127.0.0.1:${FRONTEND_PORT}"
echo
echo "Backend:"
echo "  http://127.0.0.1:${BACKEND_PORT}"
echo
echo "Docker status:"
"${COMPOSE_CMD[@]}" ps
echo
echo "To stop the project:"
echo "  ${COMPOSE_CMD[*]} down"
echo
echo "To view logs:"
echo "  ${COMPOSE_CMD[*]} logs -f"
echo
echo "============================================================"