#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-evidencxai}"
AI_PROFILE="${XAI_APP_AI_RUNTIME_PROFILE:-baseline}"
EMBED_MODEL="${XAI_APP_OLLAMA_EMBEDDING_MODEL:-all-minilm}"
LLM_MODEL="${XAI_APP_OLLAMA_LLM_MODEL:-gemma3:270m}"
XAI_BACKEND_PORT="${XAI_BACKEND_PORT:-8000}"
AI_STATUS_URL="${AI_STATUS_URL:-http://localhost:${XAI_BACKEND_PORT}/api/system/ai-status}"
OLLAMA_TAGS_URL="${OLLAMA_TAGS_URL:-http://localhost:11434/api/tags}"

export COMPOSE_PROJECT_NAME XAI_BACKEND_PORT

echo "Starting stack with Ollama profile..."
COMPOSE_PROFILES=local-ai \
XAI_APP_AI_RUNTIME_PROFILE="$AI_PROFILE" \
XAI_APP_EMBEDDING_PROVIDER=ollama \
XAI_APP_LLM_PROVIDER=ollama \
XAI_APP_OLLAMA_EMBEDDING_MODEL="$EMBED_MODEL" \
XAI_APP_OLLAMA_LLM_MODEL="$LLM_MODEL" \
docker compose -f "$COMPOSE_FILE" up -d postgres redis backend worker frontend ollama

echo "AI runtime profile: $AI_PROFILE"

echo "Waiting for Ollama API..."
for _ in $(seq 1 240); do
  if curl -fsS "$OLLAMA_TAGS_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "$OLLAMA_TAGS_URL" >/dev/null 2>&1; then
  echo "Ollama API did not become ready in time: $OLLAMA_TAGS_URL" >&2
  exit 1
fi

echo "Pulling embedding model: $EMBED_MODEL"
docker compose -f "$COMPOSE_FILE" exec -T ollama ollama pull "$EMBED_MODEL"

echo "Pulling LLM model: $LLM_MODEL"
docker compose -f "$COMPOSE_FILE" exec -T ollama ollama pull "$LLM_MODEL"

echo "Waiting for backend API..."
for _ in $(seq 1 120); do
  if curl -fsS "$AI_STATUS_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Current AI runtime status:"
curl -fsS "$AI_STATUS_URL"
echo
