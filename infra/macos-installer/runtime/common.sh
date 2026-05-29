#!/usr/bin/env bash
set -euo pipefail

XAI_DOCKER_DMG_URL="${XAI_DOCKER_DMG_URL:-https://desktop.docker.com/mac/main/arm64/Docker.dmg}"
XAI_OLLAMA_ZIP_URL="${XAI_OLLAMA_ZIP_URL:-https://ollama.com/download/Ollama-darwin.zip}"
XAI_REQUIRED_FREE_GB="${XAI_REQUIRED_FREE_GB:-12}"
XAI_RECOMMENDED_MEMORY_GB="${XAI_RECOMMENDED_MEMORY_GB:-8}"
XAI_DOCKER_WAIT_ATTEMPTS="${XAI_DOCKER_WAIT_ATTEMPTS:-180}"
XAI_SERVICE_WAIT_ATTEMPTS="${XAI_SERVICE_WAIT_ATTEMPTS:-180}"
XAI_WAIT_INTERVAL_SECONDS="${XAI_WAIT_INTERVAL_SECONDS:-2}"

xai_step() {
  printf '\n==> %s\n' "$1"
}

xai_warn() {
  printf 'Внимание: %s\n' "$1" >&2
}

xai_die() {
  printf 'Ошибка: %s\n' "$1" >&2
  exit 1
}

xai_wait_for_command() {
  local attempts="$1"
  local command="$2"
  local description="$3"

  for _ in $(seq 1 "$attempts"); do
    if eval "$command" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$XAI_WAIT_INTERVAL_SECONDS"
  done

  echo "Не удалось дождаться: $description" >&2
  return 1
}

xai_installed_project_dir() {
  printf '%s\n' "${XAI_INSTALL_DIR:-$HOME/EvidenceXAI}"
}

xai_log_dir() {
  printf '%s\n' "${XAI_INSTALL_LOG_DIR:-$(xai_installed_project_dir)/install-logs}"
}

xai_start_log() {
  local name="$1"
  local log_dir
  log_dir="$(xai_log_dir)"
  mkdir -p "$log_dir"
  local log_file="$log_dir/${name}-$(date +%Y%m%d-%H%M%S).log"
  printf 'Лог: %s\n' "$log_file"
  exec > >(tee -a "$log_file") 2>&1
}

xai_runtime_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd
}

xai_source_project_dir() {
  local package_root="${XAI_PACKAGE_ROOT:-}"
  if [[ -n "$package_root" && -d "$package_root/project/infra" ]]; then
    cd "$package_root/project" && pwd
    return 0
  fi

  xai_runtime_root
}

xai_resolve_project_dir() {
  local install_dir
  install_dir="$(xai_installed_project_dir)"
  if [[ -d "$install_dir/infra" ]]; then
    cd "$install_dir" && pwd
    return 0
  fi

  local source_dir
  source_dir="$(xai_source_project_dir)"
  if [[ -d "$source_dir/infra" ]]; then
    cd "$source_dir" && pwd
    return 0
  fi

  xai_die "папка проекта не найдена"
}

xai_resolve_ollama_bin() {
  if [[ -x /opt/homebrew/bin/ollama ]]; then
    printf '%s\n' /opt/homebrew/bin/ollama
    return 0
  fi
  if [[ -x /Applications/Ollama.app/Contents/Resources/ollama ]]; then
    printf '%s\n' /Applications/Ollama.app/Contents/Resources/ollama
    return 0
  fi
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi
  return 1
}

xai_has_ollama_model() {
  local ollama_bin="$1"
  local model_name="$2"
  local latest_name="${model_name}:latest"

  "$ollama_bin" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -E -x -q "${model_name}|${latest_name}"
}

xai_pull_ollama_model() {
  local ollama_bin="$1"
  local model_name="$2"

  if xai_has_ollama_model "$ollama_bin" "$model_name"; then
    echo "Модель уже доступна: $model_name"
    return 0
  fi

  echo "Скачиваю модель Ollama: $model_name"
  "$ollama_bin" pull "$model_name"
}

xai_verify_macos_arm64() {
  xai_step "Проверка macOS"
  [[ "$(uname -s)" == "Darwin" ]] || xai_die "установщик рассчитан только на macOS"
  [[ "$(uname -m)" == "arm64" ]] || xai_die "этот пакет рассчитан на Apple Silicon Mac"

  local product_version major_version
  product_version="$(sw_vers -productVersion)"
  major_version="${product_version%%.*}"
  if [[ "$major_version" -lt 14 ]]; then
    xai_die "Ollama требует macOS 14 Sonoma или новее, текущая версия: $product_version"
  fi
  echo "macOS $product_version, Apple Silicon"
}

xai_verify_resources() {
  xai_step "Проверка ресурсов"
  local free_gb memory_gb
  free_gb="$(df -g "$HOME" | awk 'NR==2 {print $4}')"
  memory_gb="$(sysctl -n hw.memsize | awk '{printf "%.0f", $1 / 1024 / 1024 / 1024}')"

  if [[ "$free_gb" -lt "$XAI_REQUIRED_FREE_GB" ]]; then
    xai_die "нужно минимум ${XAI_REQUIRED_FREE_GB} GB свободного места, сейчас примерно ${free_gb} GB"
  fi
  if [[ "$memory_gb" -lt "$XAI_RECOMMENDED_MEMORY_GB" ]]; then
    xai_warn "рекомендуется ${XAI_RECOMMENDED_MEMORY_GB} GB RAM или больше, сейчас примерно ${memory_gb} GB"
  fi

  echo "Свободное место: ${free_gb} GB"
  echo "Память: ${memory_gb} GB"
}

xai_sudo_ditto() {
  local source="$1"
  local target="$2"
  if [[ -w "$(dirname "$target")" ]]; then
    ditto "$source" "$target"
  else
    sudo ditto "$source" "$target"
  fi
}
