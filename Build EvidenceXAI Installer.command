#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/infra/macos-installer/build_installer.sh"
STATUS=$?

echo
if [[ "$STATUS" -eq 0 ]]; then
  echo "Установщик собран в dist/installers."
else
  echo "Сборка установщика завершилась с ошибкой."
fi
read -r -p "Нажмите Enter, чтобы закрыть окно..." _
exit "$STATUS"
