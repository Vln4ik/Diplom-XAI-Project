#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export XAI_PACKAGE_ROOT="$SCRIPT_DIR"

bash "$SCRIPT_DIR/project/infra/macos-installer/runtime/install.sh"
STATUS=$?

echo
if [[ "$STATUS" -eq 0 ]]; then
  echo "Готово. EvidenceXAI установлен и запущен."
else
  echo "Установка завершилась с ошибкой. Проверь текст выше и лог в папке install-logs."
fi
read -r -p "Нажмите Enter, чтобы закрыть окно..." _
exit "$STATUS"
