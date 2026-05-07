#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export XAI_INCLUDE_FRONTEND=1

bash "$ROOT_DIR/infra/start_backend_stack.sh"
