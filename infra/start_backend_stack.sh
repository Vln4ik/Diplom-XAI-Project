#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
LOG_DIR="$ROOT_DIR/infra/logs"
OLLAMA_LOG_FILE="$LOG_DIR/ollama-serve.log"
HOST_OLLAMA_TAGS_URL="${HOST_OLLAMA_TAGS_URL:-http://localhost:11434/api/tags}"
CONTAINER_OLLAMA_BASE_URL="${XAI_APP_OLLAMA_BASE_URL:-http://host.docker.internal:11434/api}"
BACKEND_AI_STATUS_URL="${BACKEND_AI_STATUS_URL:-http://localhost:8000/api/system/ai-status}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://localhost:8000/api/system/health}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173/login}"
EMBED_MODEL="${XAI_APP_OLLAMA_EMBEDDING_MODEL:-all-minilm}"
LLM_MODEL="${XAI_APP_OLLAMA_LLM_MODEL:-gemma3:270m}"
DOCKER_WAIT_ATTEMPTS="${DOCKER_WAIT_ATTEMPTS:-180}"
SERVICE_WAIT_ATTEMPTS="${SERVICE_WAIT_ATTEMPTS:-120}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-2}"
XAI_INCLUDE_FRONTEND="${XAI_INCLUDE_FRONTEND:-0}"

mkdir -p "$LOG_DIR"

print_step() {
  printf '\n==> %s\n' "$1"
}

wait_for_command() {
  local attempts="$1"
  local command="$2"
  local description="$3"

  for _ in $(seq 1 "$attempts"); do
    if eval "$command" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
  done

  echo "Не удалось дождаться: $description" >&2
  return 1
}

resolve_ollama_bin() {
  if [[ -x /opt/homebrew/bin/ollama ]]; then
    printf '%s\n' /opt/homebrew/bin/ollama
    return 0
  fi
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi
  return 1
}

ensure_docker() {
  print_step "Проверка Docker Desktop"
  if docker info >/dev/null 2>&1; then
    echo "Docker daemon уже доступен."
    return 0
  fi

  echo "Docker daemon недоступен. Запускаю Docker.app..."
  open -a Docker
  wait_for_command "$DOCKER_WAIT_ATTEMPTS" "docker info" "Docker Desktop"
  echo "Docker Desktop готов."
}

ensure_ollama() {
  print_step "Проверка Ollama"
  if curl -fsS "$HOST_OLLAMA_TAGS_URL" >/dev/null 2>&1; then
    echo "Ollama API уже отвечает."
    return 0
  fi

  local ollama_bin
  ollama_bin="$(resolve_ollama_bin)" || {
    echo "Команда ollama не найдена. Установи Ollama на хост или запусти его вручную." >&2
    return 1
  }

  echo "Ollama не отвечает. Запускаю host service..."
  nohup "$ollama_bin" serve >"$OLLAMA_LOG_FILE" 2>&1 &
  wait_for_command "$SERVICE_WAIT_ATTEMPTS" "curl -fsS '$HOST_OLLAMA_TAGS_URL'" "Ollama API"
  echo "Ollama API готов."
}

pull_models() {
  print_step "Проверка локальных моделей Ollama"
  local ollama_bin
  ollama_bin="$(resolve_ollama_bin)" || {
    echo "Команда ollama не найдена." >&2
    return 1
  }

  echo "Проверяю embedding model: $EMBED_MODEL"
  "$ollama_bin" pull "$EMBED_MODEL"

  echo "Проверяю LLM model: $LLM_MODEL"
  "$ollama_bin" pull "$LLM_MODEL"
}

start_backend_services() {
  local services=(postgres redis backend worker)
  local stack_label="backend-стека"

  if [[ "$XAI_INCLUDE_FRONTEND" == "1" ]]; then
    services+=(frontend)
    stack_label="полного стека"
  fi

  print_step "Запуск $stack_label"
  COMPOSE_PROFILES=local-ai \
  XAI_APP_EMBEDDING_PROVIDER=ollama \
  XAI_APP_LLM_PROVIDER=ollama \
  XAI_APP_OLLAMA_BASE_URL="$CONTAINER_OLLAMA_BASE_URL" \
  XAI_APP_OLLAMA_EMBEDDING_MODEL="$EMBED_MODEL" \
  XAI_APP_OLLAMA_LLM_MODEL="$LLM_MODEL" \
  docker compose -f "$COMPOSE_FILE" up -d "${services[@]}"

  wait_for_command "$SERVICE_WAIT_ATTEMPTS" "curl -fsS '$BACKEND_AI_STATUS_URL'" "backend API"
  echo "Backend API готов."

  if [[ "$XAI_INCLUDE_FRONTEND" == "1" ]]; then
    wait_for_command "$SERVICE_WAIT_ATTEMPTS" "curl -fsSI '$FRONTEND_URL'" "frontend UI"
    echo "Frontend UI готов."
  fi
}

print_summary() {
  if [[ "$XAI_INCLUDE_FRONTEND" == "1" ]]; then
    print_step "Текущий статус полного стека"
  else
    print_step "Текущий статус backend-части"
  fi
  docker compose -f "$COMPOSE_FILE" ps

  echo
  echo "AI status:"
  curl -fsS "$BACKEND_AI_STATUS_URL"

  echo
  echo
  echo "Health:"
  curl -fsS "$BACKEND_HEALTH_URL"

  echo
  echo
  echo "Доступные адреса:"
  echo "  API:     http://localhost:8000"
  echo "  Swagger: http://localhost:8000/docs"
  if [[ "$XAI_INCLUDE_FRONTEND" == "1" ]]; then
    echo "  Frontend: http://localhost:5173/login"
  fi
  echo
  echo "Логин:"
  echo "  admin@example.com"
  echo "  ChangeMe123!"
}

main() {
  ensure_docker
  ensure_ollama
  pull_models
  start_backend_services
  print_summary
}

main "$@"
