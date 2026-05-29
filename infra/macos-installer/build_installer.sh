#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${XAI_INSTALLER_OUTPUT_DIR:-$ROOT_DIR/dist/installers}"
PACKAGE_NAME="${XAI_INSTALLER_PACKAGE_NAME:-EvidenceXAI-mac-arm64-online}"
PACKAGE_DIR="$OUTPUT_DIR/$PACKAGE_NAME"
ZIP_PATH="$OUTPUT_DIR/$PACKAGE_NAME.zip"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

print_step() {
  printf '\n==> %s\n' "$1"
}

print_step "Подготовка папки сборки"
rm -rf "$PACKAGE_DIR" "$ZIP_PATH"
mkdir -p "$PACKAGE_DIR/project" "$OUTPUT_DIR"

EXCLUDES_FILE="$TMP_DIR/rsync-excludes.txt"
cat >"$EXCLUDES_FILE" <<'EOF'
.git/
.venv/
.venv-train/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
node_modules/
dist/
build/
.DS_Store
* 2.*
.env
.env.*
*.sqlite3
*.db
data/reports/
data/uploads/
data/models/
data/raw/
data/processed/
data/*.log
backend/.venv/
backend/.pytest_cache/
backend/htmlcov/
backend/.coverage
backend/storage/
backend/*.egg-info/
frontend/node_modules/
frontend/dist/
frontend/test-results/
frontend/playwright-report/
infra/logs/
storage/
test-results/
.tmp/
EOF

print_step "Копирование текущей рабочей версии проекта"
rsync -a --exclude-from "$EXCLUDES_FILE" "$ROOT_DIR/" "$PACKAGE_DIR/project/"

print_step "Копирование команд установщика"
ditto "$ROOT_DIR/infra/macos-installer/package" "$PACKAGE_DIR"
cp "$ROOT_DIR/INSTALL_RU.md" "$PACKAGE_DIR/INSTALL_RU.md"
find "$PACKAGE_DIR" -type f \( -name "*.sh" -o -name "*.command" \) -exec chmod +x {} +

print_step "Создание ZIP"
(
  cd "$OUTPUT_DIR"
  if command -v ditto >/dev/null 2>&1; then
    ditto -c -k --sequesterRsrc --keepParent "$PACKAGE_NAME" "$ZIP_PATH"
  else
    zip -qr "$ZIP_PATH" "$PACKAGE_NAME"
  fi
)

print_step "Готово"
echo "Папка пакета: $PACKAGE_DIR"
echo "ZIP: $ZIP_PATH"
