#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

PROJECT_DIR="$(xai_resolve_project_dir)"
xai_start_log "check"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-evidencxai}"
export XAI_BACKEND_PORT="${XAI_BACKEND_PORT:-8000}"
export XAI_FRONTEND_PORT="${XAI_FRONTEND_PORT:-5173}"
export XAI_POSTGRES_PORT="${XAI_POSTGRES_PORT:-5432}"
export XAI_REDIS_PORT="${XAI_REDIS_PORT:-6379}"

BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://localhost:${XAI_BACKEND_PORT}}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${XAI_FRONTEND_PORT}/login}"
HEALTH_URL="${BACKEND_BASE_URL}/api/system/health"
AI_STATUS_URL="${BACKEND_BASE_URL}/api/system/ai-status"

xai_step "Проверка Docker"
docker info >/dev/null
docker compose version

xai_step "Проверка Ollama и моделей"
curl -fsS http://localhost:11434/api/tags >/dev/null
OLLAMA_BIN="$(xai_resolve_ollama_bin)" || xai_die "команда Ollama не найдена"
xai_has_ollama_model "$OLLAMA_BIN" "all-minilm" || xai_die "модель all-minilm не найдена"
xai_has_ollama_model "$OLLAMA_BIN" "gemma3:270m" || xai_die "модель gemma3:270m не найдена"
echo "Ollama и baseline-модели доступны."

xai_step "Проверка контейнеров"
cd "$PROJECT_DIR"
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" ps

xai_step "Проверка backend health"
curl -fsS "$HEALTH_URL"
echo

xai_step "Проверка AI/OCR статуса"
curl -fsS "$AI_STATUS_URL" | docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" exec -T backend python -c '
import json
import sys

payload = json.load(sys.stdin)
errors = []
if payload["embeddings"]["provider"] != "ollama" or payload["embeddings"]["mode"] != "model":
    errors.append("embeddings are not running through Ollama model mode")
if payload["llm"]["provider"] != "ollama" or payload["llm"]["mode"] != "model":
    errors.append("LLM is not running through Ollama model mode")
if not payload["ocr"]["available"]:
    errors.append("Tesseract OCR is not available")
if errors:
    raise SystemExit("; ".join(errors))
print(json.dumps({
    "profile": payload["profile"]["profile_id"],
    "embedding_model": payload["embeddings"]["resolved_model"],
    "llm_model": payload["llm"]["resolved_model"],
    "ocr": payload["ocr"]["provider"],
}, ensure_ascii=False))
'

xai_step "Проверка frontend"
curl -fsSI "$FRONTEND_URL"

if [[ "${XAI_SKIP_LIVE_SMOKE:-0}" == "1" ]]; then
  echo
  echo "Live smoke пропущен: XAI_SKIP_LIVE_SMOKE=1"
else
  xai_step "Live smoke: загрузка, обработка, анализ, генерация и экспорт"
  docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" exec -T backend \
    python scripts/benchmark_live_api.py \
      --base-url http://127.0.0.1:8000 \
      --email admin@example.com \
      --password 'ChangeMe123!' \
      --runs 1 \
      --concurrency 1 \
      --resource-profile none \
      --pipeline-timeout 360
fi

echo
echo "Проверка установки завершена успешно."
