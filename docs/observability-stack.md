# Observability Stack

## 1. Назначение

Этот контур переводит runtime-метрики из уровня "endpoint доступен" в уровень "система наблюдаема":

- `Prometheus` регулярно скрейпит backend metrics endpoint;
- `Grafana` поднимается с уже подключённым datasource и готовым dashboard;
- alert rules фиксируют основные деградации без ручного анализа сырых метрик.

Контур работает поверх существующих endpoint-ов:

- `GET /api/system/metrics`
- `GET /api/system/metrics/prometheus`

## 2. Что входит

- `infra/docker-compose.yml`
  - service `prometheus`
  - service `grafana`
- `infra/observability/prometheus/prometheus.yml`
- `infra/observability/prometheus/alerts/xai-report-builder.rules.yml`
- `infra/observability/grafana/provisioning/*`
- `infra/observability/grafana/dashboards/xai-report-builder-overview.json`

## 3. Запуск

Только observability-профиль:

```bash
COMPOSE_PROFILES=observability \
docker compose -f infra/docker-compose.yml up --build
```

Локальный AI + observability:

```bash
COMPOSE_PROFILES=local-ai,observability \
XAI_APP_EMBEDDING_PROVIDER=ollama \
XAI_APP_LLM_PROVIDER=ollama \
docker compose -f infra/docker-compose.yml up --build
```

Автоматический launch script тоже поддерживает этот режим:

```bash
XAI_INCLUDE_OBSERVABILITY=1 bash infra/start_backend_stack.sh
XAI_INCLUDE_FRONTEND=1 XAI_INCLUDE_OBSERVABILITY=1 bash infra/start_backend_stack.sh
```

## 4. Адреса

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Grafana default credentials:

- user: `admin`
- password: `ChangeMe123!`

## 5. Что видно в Grafana

Provisioned dashboard `XAI Report Builder Overview` показывает:

- backend availability;
- число task failures за последние `10m`;
- текущий объём queued tasks;
- максимальную среднюю API latency;
- HTTP request rate по `method/status`;
- HTTP average latency по `path`;
- Celery task event rate по `task/status`;
- среднюю длительность фоновых задач;
- срез recent task states по `task/status`.

## 6. Что алертится

Текущий набор правил:

- `XAIBackendDown`
  - backend metrics endpoint недоступен более `2m`
- `XAIBackgroundTaskFailures`
  - есть новые failed task events за `10m`
- `XAIHighRequestLatency`
  - average latency держится выше `2s` не менее `10m`
- `XAIQueuedTasksGrowing`
  - более `10` recent tasks остаются в `queued` не менее `10m`

## 7. Ограничения текущего шага

Сейчас это observability baseline, а не полный production monitoring stack.

Ещё не реализовано:

- `Alertmanager` и реальная доставка уведомлений;
- долговременное хранение метрик за пределами retention внутри контейнера `prometheus`;
- отдельные exporter-ы для `PostgreSQL`, `Redis`, host OS и Docker daemon;
- трассировка запросов и distributed tracing;
- correlation между business entity id и task alert routing.
