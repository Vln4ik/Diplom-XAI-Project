#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XAI_BACKEND_PORT="${XAI_BACKEND_PORT:-8000}"
XAI_FRONTEND_PORT="${XAI_FRONTEND_PORT:-5173}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${XAI_FRONTEND_PORT}/login}"
API_DOCS_URL="${API_DOCS_URL:-http://localhost:${XAI_BACKEND_PORT}/docs}"

cd "$ROOT_DIR"

echo
echo "EvidenceXAI"
echo "Запуск полного стека..."
echo

bash "$ROOT_DIR/infra/start_full_stack.sh"

echo
echo "Полный стек запущен."
echo "Frontend: $FRONTEND_URL"
echo "Swagger:  $API_DOCS_URL"
echo

if command -v open >/dev/null 2>&1; then
  open "$FRONTEND_URL" >/dev/null 2>&1 || true
fi

read -r -p "Нажми Enter, чтобы закрыть это окно..." _
