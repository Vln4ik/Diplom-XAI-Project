#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173/login}"
API_DOCS_URL="${API_DOCS_URL:-http://localhost:8000/docs}"

cd "$ROOT_DIR"

echo
echo "XAI Report Builder"
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
