#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

INSTALL_DIR="$(xai_installed_project_dir)"
SOURCE_PROJECT_DIR="$(xai_source_project_dir)"

copy_project() {
  xai_step "Копирование проекта"
  local source_real install_real backup_dir
  source_real="$(cd "$SOURCE_PROJECT_DIR" && pwd -P)"

  if [[ -d "$INSTALL_DIR" ]]; then
    install_real="$(cd "$INSTALL_DIR" && pwd -P)"
    if [[ "$source_real" == "$install_real" ]]; then
      echo "Проект уже находится в $INSTALL_DIR"
      return 0
    fi

    backup_dir="${INSTALL_DIR}.backup-$(date +%Y%m%d-%H%M%S)"
    echo "Найдена существующая папка $INSTALL_DIR"
    echo "Переношу её в резервную копию: $backup_dir"
    mv "$INSTALL_DIR" "$backup_dir"
  fi

  mkdir -p "$(dirname "$INSTALL_DIR")"
  ditto "$SOURCE_PROJECT_DIR" "$INSTALL_DIR"
  find "$INSTALL_DIR/infra" -type f \( -name "*.sh" -o -name "*.command" \) -exec chmod +x {} +
  echo "Проект установлен в $INSTALL_DIR"
}

ensure_docker_desktop() {
  xai_step "Проверка Docker Desktop"
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker --version
    docker compose version
    return 0
  fi

  if [[ ! -d /Applications/Docker.app ]]; then
    local tmp_dir mount_point installer_path
    tmp_dir="$(mktemp -d)"
    echo "Docker Desktop не найден. Скачиваю официальный Apple Silicon DMG..."
    curl -fL --progress-bar "$XAI_DOCKER_DMG_URL" -o "$tmp_dir/Docker.dmg"

    hdiutil attach "$tmp_dir/Docker.dmg" -nobrowse -quiet
    mount_point="$(find /Volumes -maxdepth 2 -name Docker.app -type d -print -quit | sed 's#/Docker.app$##')"
    installer_path="$(find /Volumes -maxdepth 5 -path "*/Docker.app/Contents/MacOS/install" -type f -print -quit)"
    [[ -n "$installer_path" ]] || xai_die "не найден Docker installer внутри DMG"

    echo "Устанавливаю Docker Desktop. macOS может запросить пароль администратора."
    sudo "$installer_path" --accept-license --user "$USER"

    if [[ -n "$mount_point" ]]; then
      hdiutil detach "$mount_point" -quiet || true
    fi
    rm -rf "$tmp_dir"
  fi

  echo "Запускаю Docker Desktop..."
  open -a Docker
  xai_wait_for_command "$XAI_DOCKER_WAIT_ATTEMPTS" "command -v docker >/dev/null 2>&1 && docker info" "Docker Desktop"
  docker --version
  docker compose version
}

ensure_ollama() {
  xai_step "Проверка Ollama"
  if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama API уже отвечает."
    return 0
  fi

  if ! xai_resolve_ollama_bin >/dev/null 2>&1 && [[ ! -d /Applications/Ollama.app ]]; then
    local tmp_dir app_path
    tmp_dir="$(mktemp -d)"
    echo "Ollama не найден. Скачиваю официальный macOS ZIP..."
    curl -fL --progress-bar "$XAI_OLLAMA_ZIP_URL" -o "$tmp_dir/Ollama.zip"
    ditto -x -k "$tmp_dir/Ollama.zip" "$tmp_dir"
    app_path="$(find "$tmp_dir" -maxdepth 2 -name Ollama.app -type d -print -quit)"
    [[ -n "$app_path" ]] || xai_die "не найден Ollama.app внутри ZIP"
    xai_sudo_ditto "$app_path" /Applications/Ollama.app
    rm -rf "$tmp_dir"
  fi

  echo "Запускаю Ollama..."
  open -a Ollama >/dev/null 2>&1 || true
  if ! xai_wait_for_command 30 "curl -fsS http://localhost:11434/api/tags" "Ollama API"; then
    local ollama_bin
    ollama_bin="$(xai_resolve_ollama_bin)" || xai_die "команда Ollama не найдена после установки"
    nohup "$ollama_bin" serve >"$(xai_log_dir)/ollama-serve.log" 2>&1 &
    xai_wait_for_command "$XAI_SERVICE_WAIT_ATTEMPTS" "curl -fsS http://localhost:11434/api/tags" "Ollama API"
  fi
}

pull_baseline_models() {
  xai_step "Проверка baseline AI-моделей"
  local ollama_bin
  ollama_bin="$(xai_resolve_ollama_bin)" || xai_die "команда Ollama не найдена"
  xai_pull_ollama_model "$ollama_bin" "all-minilm"
  xai_pull_ollama_model "$ollama_bin" "gemma3:270m"
}

start_project() {
  xai_step "Запуск EvidenceXAI"
  cd "$INSTALL_DIR"
  XAI_INCLUDE_FRONTEND=1 bash "$INSTALL_DIR/infra/start_full_stack.sh"

  local frontend_port="${XAI_FRONTEND_PORT:-5173}"
  local frontend_url="${FRONTEND_URL:-http://localhost:${frontend_port}/login}"
  open "$frontend_url" >/dev/null 2>&1 || true
}

main() {
  xai_verify_macos_arm64
  xai_verify_resources
  copy_project
  xai_start_log "install"
  ensure_docker_desktop
  ensure_ollama
  pull_baseline_models
  start_project

  echo
  echo "Установка завершена."
  echo "Папка проекта: $INSTALL_DIR"
  echo "Адрес: http://localhost:${XAI_FRONTEND_PORT:-5173}/login"
  echo "Логин: admin@example.com"
  echo "Пароль: ChangeMe123!"
}

main "$@"
