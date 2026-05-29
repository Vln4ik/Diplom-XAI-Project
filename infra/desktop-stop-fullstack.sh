#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-evidencxai}"

cd "$ROOT_DIR"

echo
echo "EvidenceXAI"
echo "Остановка полного стека..."
echo

docker compose -f "$COMPOSE_FILE" down

echo
echo "Стек остановлен."
echo

read -r -p "Нажми Enter, чтобы закрыть это окно..." _
