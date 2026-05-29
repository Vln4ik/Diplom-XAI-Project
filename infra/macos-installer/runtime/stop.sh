#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

PROJECT_DIR="$(xai_resolve_project_dir)"
xai_start_log "stop"

xai_step "Остановка EvidenceXAI"
cd "$PROJECT_DIR"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-evidencxai}"
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" down

echo
echo "EvidenceXAI остановлен."
