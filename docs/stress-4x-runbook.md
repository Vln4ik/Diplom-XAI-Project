# Stress 4x Runbook

## 1. Назначение

Этот сценарий добирает следующий load/stress шаг roadmap:

- `4` параллельных пользовательских прогона;
- hybrid resource profile;
- измерение не только Docker-контейнеров, но и внешнего host `Ollama`.

Главная цель — увидеть, как ведёт себя система под более агрессивной конкуренцией, когда bottleneck начинает смещаться в сторону локального AI runtime.

## 2. Что измеряется

Профиль включает:

- `backend`
- `worker`
- `postgres`
- `redis`
- `host_ollama`

`host_ollama` собирается через `ps` на хосте по substring match `ollama`.

## 3. Предпосылки

До запуска должны быть доступны:

- backend API на `http://localhost:8000`;
- worker и broker;
- host `Ollama` service;
- модели `all-minilm` и `gemma3:270m`.

Если стек поднимается нашим launch script:

```bash
XAI_INCLUDE_FRONTEND=0 bash infra/start_backend_stack.sh
```

## 4. Команда запуска

Короткий вариант через preset:

```bash
./.venv/bin/python backend/scripts/run_benchmark_profile.py stress-4x
```

Эквивалентная полная команда:

```bash
./.venv/bin/python backend/scripts/benchmark_live_api.py \
  --runs 4 \
  --concurrency 4 \
  --resource-profile hybrid \
  --resource-interval 1.0 \
  --host-process-match ollama \
  --host-resource-alias host_ollama \
  --output docs/stress-4x-baseline.json
```

## 5. Артефакты

Результат сохраняется в:

- `docs/stress-4x-baseline.json`

Если нужно зафиксировать human-readable summary, после запуска имеет смысл оформить рядом:

- `docs/stress-4x-baseline.md`

## 6. Что смотреть в результате

Ключевые поля:

- `total_wall_time_seconds`
- `throughput_runs_per_minute`
- `summary.generate.mean`
- `summary.generate.p95`
- `resource_profile.summary.worker.memory_mib`
- `resource_profile.summary.host_ollama.cpu_percent`
- `resource_profile.summary.host_ollama.memory_mib`

## 7. Практический смысл

Этот профиль нужен не ради цифр самих по себе, а чтобы ответить на инженерные вопросы:

- упираемся ли мы в `worker`, `backend` или внешний `Ollama`;
- насколько резко деградирует `generate` при `4x` concurrency;
- нужно ли масштабировать AI runtime отдельно от API/worker слоя;
- достаточно ли текущего local demo-stack для защиты и live demo.
