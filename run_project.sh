#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DEFAULT_FRONTEND_PORT=8080
MAX_FRONTEND_PORT=8999
BACKEND_PORT=8000

log() {
    printf "\n==> %s\n" "$1"
}

info() {
    printf "  %s\n" "$1"
}

error() {
    printf "\nERROR: %s\n" "$1" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

assert_docker_available() {
    if ! command_exists docker; then
        error "Docker is not installed or not available in PATH."
    fi

    unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH

    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running or the current user cannot access Docker.\n\nHint: add your user to the docker group with:\n  sudo usermod -aG docker \"$USER\"\nand then log out and log back in."
    fi
}

detect_compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
    elif command_exists docker-compose; then
        COMPOSE_CMD=(docker-compose)
    else
        error "Docker Compose is not installed."
    fi
}

find_compose_file() {
    if [[ -f "$ROOT_DIR/docker-compose.yml" ]]; then
        COMPOSE_FILE="docker-compose.yml"
    elif [[ -f "$ROOT_DIR/compose.yml" ]]; then
        COMPOSE_FILE="compose.yml"
    elif [[ -f "$ROOT_DIR/compose.yaml" ]]; then
        COMPOSE_FILE="compose.yaml"
    else
        error "No docker-compose.yml, compose.yml, or compose.yaml found."
    fi
}

validate_compose_config() {
    log "Validating Docker Compose configuration..."
    if ! "${COMPOSE_CMD[@]}" config >/dev/null; then
        error "Docker Compose configuration is invalid."
    fi
    info "Compose configuration is valid."
}

port_is_in_use() {
    local port="$1"

    if command_exists python3 || command_exists python; then
        local pycmd=python3
        if ! command_exists python3; then
            pycmd=python
        fi

        if "$pycmd" - <<PYTHON "$port" 2>/dev/null
import socket, sys
port = int(sys.argv[1])
for addr in ['127.0.0.1', '0.0.0.0']:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((addr, port))
    except OSError:
        sys.exit(0)
    finally:
        s.close()
sys.exit(1)
PYTHON
        then
            return 0
        fi
        return 1
    fi

    if command_exists docker; then
        if docker ps --format '{{.Ports}}' 2>/dev/null | grep -qiE "(127\\.0\\.0\\.1|0\\.0\\.0\\.0|\\[::\\]):${port}->"; then
            return 0
        fi
    fi

    if command_exists ss; then
        if ss -ltnH 2>/dev/null | awk -v p=":${port}" '$4 ~ p"$" { exit 0 } END { exit 1 }'; then
            return 0
        fi
        return 1
    fi

    if command_exists lsof; then
        lsof -iTCP:"$port" -sTCP:LISTEN -n >/dev/null 2>&1
        return $?
    fi

    error "Cannot determine port availability because neither Python, docker, ss, nor lsof is installed."
}

select_frontend_port() {
    local try_port="${FRONTEND_PORT:-$DEFAULT_FRONTEND_PORT}"

    while port_is_in_use "$try_port"; do
        info "Port $try_port is already in use."
        try_port=$((try_port + 1))

        if [[ "$try_port" -gt "$MAX_FRONTEND_PORT" ]]; then
            error "Could not find a free frontend port between $DEFAULT_FRONTEND_PORT and $MAX_FRONTEND_PORT."
        fi
    done

    FRONTEND_PORT="$try_port"
    info "Using frontend port: $FRONTEND_PORT"
}

compose_up_with_retries() {
    local attempt=1
    local output

    while true; do
        export FRONTEND_PORT
        log "Attempting to start RL_AGENT with frontend port $FRONTEND_PORT..."

        if output="$("${COMPOSE_CMD[@]}" up -d 2>&1)"; then
            printf '%s\n' "$output"
            return 0
        fi

        if printf '%s\n' "$output" | grep -qiE 'port .* is already allocated|Bind( for)? .* failed|address already in use|failed to set up containernetworking|failed to set up container networking'; then
            info "Port $FRONTEND_PORT remains unavailable. Selecting next available port."
            "${COMPOSE_CMD[@]}" down --remove-orphans >/dev/null 2>&1 || true
            FRONTEND_PORT=$((FRONTEND_PORT + 1))
            while port_is_in_use "$FRONTEND_PORT"; do
                FRONTEND_PORT=$((FRONTEND_PORT + 1))
                if [[ "$FRONTEND_PORT" -gt "$MAX_FRONTEND_PORT" ]]; then
                    error "Could not find a free frontend port between $DEFAULT_FRONTEND_PORT and $MAX_FRONTEND_PORT."
                fi
            done
            info "Retrying with frontend port $FRONTEND_PORT."
            attempt=$((attempt + 1))
            continue
        fi

        error "Docker Compose failed to start RL_AGENT:\n$output"
    done
}

check_container_running() {
    local service="$1"
    local container_id

    container_id="$("${COMPOSE_CMD[@]}" ps -q "$service" 2>/dev/null | tr -d '\n')"
    if [[ -n "$container_id" ]] && docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null | grep -q '^true$'; then
        return 0
    fi
    return 1
}

assert_docker_available

detect_compose_cmd
find_compose_file

log "Project root: $ROOT_DIR"
info "Compose command: ${COMPOSE_CMD[*]}"
info "Compose file: ${COMPOSE_FILE}"

FRONTEND_PORT="${FRONTEND_PORT:-$DEFAULT_FRONTEND_PORT}"
select_frontend_port
export FRONTEND_PORT

validate_compose_config

log "Stopping existing RL_AGENT containers..."
"${COMPOSE_CMD[@]}" down --remove-orphans >/dev/null 2>&1 || true
info "Stopped existing containers."

log "Building Docker images..."
FRONTEND_PORT="$FRONTEND_PORT" "${COMPOSE_CMD[@]}" build
info "Docker images built successfully."

compose_up_with_retries

log "Project containers status:"
"${COMPOSE_CMD[@]}" ps

log "Verifying service status..."
if check_container_running backend; then
    info "Backend container: RUNNING"
else
    info "Backend container: NOT RUNNING"
fi

if check_container_running frontend; then
    info "Frontend container: RUNNING"
else
    info "Frontend container: NOT RUNNING"
fi

printf '\nFrontend:\n  http://127.0.0.1:%s\n\n' "$FRONTEND_PORT"
printf 'Backend:\n  http://127.0.0.1:%s\n\n' "$BACKEND_PORT"
printf 'Useful commands:\n'
printf '  %s logs --tail=100\n' "${COMPOSE_CMD[*]}"
printf '  %s down --remove-orphans\n' "${COMPOSE_CMD[*]}"
printf '  %s ps\n' "${COMPOSE_CMD[*]}"
