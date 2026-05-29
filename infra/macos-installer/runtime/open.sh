#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

FRONTEND_URL="${FRONTEND_URL:-http://localhost:${XAI_FRONTEND_PORT:-5173}/login}"
BACKEND_DOCS_URL="${BACKEND_DOCS_URL:-http://localhost:${XAI_BACKEND_PORT:-8000}/docs}"

echo "Открываю EvidenceXAI..."
open "$FRONTEND_URL"
echo "Frontend: $FRONTEND_URL"
echo "Swagger:  $BACKEND_DOCS_URL"
