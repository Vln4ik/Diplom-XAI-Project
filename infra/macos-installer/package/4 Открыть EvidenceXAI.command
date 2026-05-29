#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export XAI_PACKAGE_ROOT="$SCRIPT_DIR"

bash "$SCRIPT_DIR/project/infra/macos-installer/runtime/open.sh"
STATUS=$?

echo
read -r -p "Нажмите Enter, чтобы закрыть окно..." _
exit "$STATUS"
