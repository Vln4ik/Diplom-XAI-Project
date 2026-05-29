#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

PROJECT_DIR="$(xai_resolve_project_dir)"
xai_start_log "start"

xai_step "Запуск EvidenceXAI"
cd "$PROJECT_DIR"
XAI_INCLUDE_FRONTEND=1 bash "$PROJECT_DIR/infra/start_full_stack.sh"

FRONTEND_URL="${FRONTEND_URL:-http://localhost:${XAI_FRONTEND_PORT:-5173}/login}"
open "$FRONTEND_URL" >/dev/null 2>&1 || true

echo
echo "EvidenceXAI запущен: $FRONTEND_URL"
echo "Логин: admin@example.com"
echo "Пароль: ChangeMe123!"
