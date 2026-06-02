# Установка EvidenceXAI на чистый Mac

Этот пакет рассчитан на Mac с Apple Silicon (M1/M2/M3/M4) и macOS 14 Sonoma или новее.
Git, Python, Node.js и Homebrew на компьютере заранее не нужны.

## Что установщик делает сам

- копирует проект в `~/EvidenceXAI`;
- устанавливает или запускает Docker Desktop;
- устанавливает или запускает Ollama;
- скачивает локальные AI-модели `all-minilm` и `gemma3:270m`;
- собирает и запускает контейнеры PostgreSQL, Redis, backend, worker и frontend;
- проверяет backend, frontend, локальный AI runtime и OCR;
- открывает web-интерфейс EvidenceXAI.

## Быстрый запуск

1. Распакуйте `EvidenceXAI-mac-arm64-online.zip`.
2. Откройте папку `EvidenceXAI-mac-arm64-online`.
3. Дважды нажмите `1 Установить EvidenceXAI.command`.
4. Если macOS спросит разрешение на запуск, откройте файл через правый клик -> `Открыть`.
5. Если Docker Desktop попросит пароль администратора, введите пароль пользователя Mac.
6. Дождитесь сообщения `Установка завершена`.
7. Откройте `http://localhost:5173/login`, если браузер не открылся автоматически.

Логин:

```text
admin@example.com
```

Пароль:

```text
ChangeMe123!
```

Первый запуск обычно занимает дольше обычного: Docker скачивает образы и собирает контейнеры, Ollama скачивает модели.

## Команды в папке пакета

- `1 Установить EvidenceXAI.command` - установка, скачивание зависимостей и первый запуск.
- `2 Запустить EvidenceXAI.command` - повторный запуск уже установленного проекта.
- `3 Остановить EvidenceXAI.command` - остановка контейнеров.
- `4 Открыть EvidenceXAI.command` - открыть web-интерфейс в браузере.
- `5 Проверить установку.command` - диагностика Docker, Ollama, моделей, backend, frontend, OCR и live smoke-сценария.

## Адреса

- Frontend: `http://localhost:5173/login`
- Backend Swagger: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/api/system/health`

## Где лежит проект и логи

После установки проект находится в:

```text
~/EvidenceXAI
```

Логи установки, запуска и проверки находятся в:

```text
~/EvidenceXAI/install-logs
```

## Проверка после установки

Запустите:

```text
5 Проверить установку.command
```

Успешная проверка подтверждает:

- Docker daemon доступен;
- Ollama API отвечает;
- модели `all-minilm` и `gemma3:270m` скачаны;
- backend health возвращает `ok`;
- AI status работает в режиме Ollama model;
- Tesseract OCR доступен внутри backend-контейнера;
- frontend login page отвечает;
- live smoke создает организацию, загружает 4 документа, обрабатывает их, запускает анализ, генерирует 9 разделов и проверяет экспорты.

## Если macOS блокирует `.command`

Вариант 1:

1. Нажмите правой кнопкой по `.command`.
2. Выберите `Открыть`.
3. Подтвердите запуск.

Вариант 2 через Terminal:

```bash
xattr -dr com.apple.quarantine "/path/to/EvidenceXAI-mac-arm64-online"
```

## Перезапуск

Остановить:

```text
3 Остановить EvidenceXAI.command
```

Запустить снова:

```text
2 Запустить EvidenceXAI.command
```

## Запуск на других портах

Если стандартные порты заняты, можно запустить из Terminal:

```bash
cd ~/EvidenceXAI
XAI_BACKEND_PORT=18000 \
XAI_FRONTEND_PORT=15173 \
XAI_POSTGRES_PORT=15432 \
XAI_REDIS_PORT=16379 \
XAI_INCLUDE_FRONTEND=1 \
bash infra/start_full_stack.sh
```

После этого frontend будет доступен по адресу:

```text
http://localhost:15173/login
```

## AI-профили

По умолчанию используется быстрый профиль `baseline`.

Запуск с профилем `quality`:

```bash
cd ~/EvidenceXAI
XAI_APP_AI_RUNTIME_PROFILE=quality XAI_INCLUDE_FRONTEND=1 bash infra/start_full_stack.sh
```

Запуск с профилем `quality_plus`:

```bash
cd ~/EvidenceXAI
XAI_APP_AI_RUNTIME_PROFILE=quality_plus XAI_INCLUDE_FRONTEND=1 bash infra/start_full_stack.sh
```

Эти профили могут скачать дополнительные модели Ollama и требуют больше памяти.

## Типовые проблемы

### Docker Desktop долго запускается

Откройте Docker Desktop вручную из Applications и дождитесь статуса `Docker Desktop is running`, затем повторите запуск.

### Не скачивается модель Ollama

Проверьте интернет и повторите:

```bash
/Applications/Ollama.app/Contents/Resources/ollama pull all-minilm
/Applications/Ollama.app/Contents/Resources/ollama pull gemma3:270m
```

Если Ollama установлена через Homebrew, можно использовать просто:

```bash
ollama pull all-minilm
ollama pull gemma3:270m
```

### Порты заняты

Используйте пример из раздела `Запуск на других портах`.

### Ошибка `apt-get update` или `exit code: 100` при сборке Docker image

Это ошибка сетевого доступа Docker к Debian package mirror во время сборки backend/worker image. Обычно помогает:

1. Проверьте интернет.
2. Откройте Docker Desktop и убедитесь, что он полностью запущен.
3. Запустите установку ещё раз.

В обновлённом установщике этот шаг автоматически повторяется несколько раз. Если ошибка остаётся, выполните в Terminal:

```bash
docker run --rm python:3.12-slim sh -lc "apt-get update"
```

Если эта команда тоже падает, проблема не в EvidenceXAI, а в сети/DNS/proxy внутри Docker Desktop.

### Нужно полностью остановить проект

```bash
cd ~/EvidenceXAI
COMPOSE_PROJECT_NAME=evidencxai docker compose -f infra/docker-compose.yml down
```

Данные PostgreSQL и загруженные документы хранятся в Docker volumes и не удаляются обычной остановкой.
