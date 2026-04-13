# XAI Report Builder (MVP)

Прототип реализован по модели из диплома: `D -> F -> N -> R -> E`.

- `D` — входные документы
- `F` — извлеченные факты (`ExtractedFacts`)
- `N` — нормативные ссылки (`NormReference`)
- `R` — черновик отчета (`ReportDraft`)
- `E` — карта доказательств (`EvidenceMap`)

Сервис покрывает ключевые требования из ВКР:
- маршруты `create/extract/generate/explain/validate`;
- контроль обязательных полей и `Score_complete`;
- расчет `Score_conf = 0.4*S_source + 0.35*S_consistency + 0.25*S_norm`;
- запрет на генерацию непроверенных числовых значений (пустые значения маркируются как `ОТСУТСТВУЕТ`);
- human-in-the-loop через endpoint верификации;
- журнал аудита действий.

## Что реализовано

- ChatGPT-подобный веб-интерфейс в формате диалога (`/ui`) с историей чатов.
- Переключение модели в чате (`pipeline-basic`, `general-assistant`, `lora-rewriter`, `full-analyst`).
- Прикрепление файлов через кнопку-скрепку и запуск pipeline прямо из чата.
- Автозапуск полного цикла при отправке только файла: `upload -> extract -> generate -> analyze`.
- Детерминированная проверка соответствия профилю для пустого запроса и запросов про комплаенс/надзор:
  вердикт (`pass/partial/fail`), обязательные поля, проблемные разделы `requires_review`, список доработок.
- Извлечение данных из `.txt`, `.md`, `.csv`, `.json`, `.log`, `.docx`, `.pdf`, `.xlsx`, `.xlsm`.
- Улучшенные паттерны извлечения для профилей Рособрнадзор/Роспотребнадзор, включая табличный формат
  `Показатель | Значение`.
- Корректная обработка числовых значений, включая `0` (например, `Количество инцидентов | 0`).
- Очистка кодовых вставок в сообщениях ассистента и раскрываемое объяснение “почему получен ответ”.
- Тесты `pytest` на чат-флоу, e2e-сценарии и кейсы извлечения (включая table-like документы).

## Структура

- `app/main.py` — REST API
- `app/services/profiles.py` — профили отчетности и шаблоны
- `app/services/extraction.py` — извлечение фактов
- `app/services/normative.py` — привязка к нормативной базе
- `app/services/generation.py` — генерация черновика и `EvidenceMap`
- `app/storage.py` — файловое JSON-хранилище
- `tests/test_pipeline.py` — e2e тест сценария

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API будет доступен на `http://127.0.0.1:8000`, Swagger: `http://127.0.0.1:8000/docs`.
Веб-интерфейс запуска: `http://127.0.0.1:8000/ui` (ChatGPT-подобный чатовый режим).

### Подключение локальной LLM (base + LoRA)

По умолчанию LLM-слой выключен. Для включения:

```bash
export DIPLOM_LLM_ENABLED=1
export DIPLOM_LLM_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
export DIPLOM_LLM_ADAPTER=data/models/sft-qwen05b-mixv3/adapter
# опционально для оффлайн-режима:
export DIPLOM_LLM_LOCAL_FILES_ONLY=1
# усиление качества:
export DIPLOM_LLM_NUM_CANDIDATES=3
export DIPLOM_LLM_MIN_CYRILLIC_RATIO=0.45
```

`POST /reports/{report_id}/generate` возвращает `generation_meta` со статусом:
- `llm_mode=applied` — LLM применена хотя бы к части секций;
- `llm_mode=fallback` — генерация откатилась к шаблонному тексту;
- `llm_mode=disabled` — LLM выключена.

Для повышения качества в LLM-слое используется:
- генерация нескольких кандидатов и выбор лучшего;
- фильтр на сохранность критичных токенов (числа, URL, `ОТСУТСТВУЕТ`);
- фильтр на сохранность приоритетных фактов секции;
- фильтр на языковую долю кириллицы и защиту от чрезмерного сжатия.

Принудительное переключение режима на запрос:
- `POST /reports/{report_id}/generate?use_llm=true`
- `POST /reports/{report_id}/generate?use_llm=false`

### Чатовый режим и выбор модели

Чат работает через серверный endpoint `POST /chat/message` (текст + опциональные файлы).
Модели для чата доступны через `GET /chat/models`.
В ответах чата кодовые вставки автоматически удаляются; объяснение «почему получен ответ» раскрывается по клику на сообщение ассистента.
Если отправить только файл (без текста), автоматически запускается полный цикл: `upload -> extract -> generate -> analyze`.
На шаге `analyze` для пустого сообщения и запросов по соответствию (`проверка/соответствие/надзор`) ответ формируется детерминированно как комплаенс-сводка по обязательным полям и секциям `requires_review`.

Доступные режимы:
- `pipeline-basic` — детерминированный pipeline (без LLM-переписывания секций);
- `general-assistant` — стандартная языковая модель для базовых текстовых вопросов;
- `lora-rewriter` — base+LoRA режим (использует текущий адаптер);
- `full-analyst` — полная локальная модель для аналитического ответа в чате.

Для `general-assistant` включена стабилизация базовых факт-вопросов (и детерминированная генерация без сэмплинга), чтобы уменьшить случайные ошибки.

Для `full-analyst` укажите путь до полной модели:

```bash
export DIPLOM_FULL_MODEL=data/models/full-qwen05b-report
# опционально: отдельная стандартная модель для базовых вопросов в чате
export DIPLOM_CHAT_GENERAL_MODEL=Qwen/Qwen2.5-0.5B-Instruct
# опционально: только локальные файлы для загрузки модели
export DIPLOM_CHAT_LOCAL_FILES_ONLY=1
```

Чтобы `full-analyst` и `lora-rewriter` реально работали в API, в runtime окружении должны быть LLM-зависимости (`torch/transformers/peft`). Самый простой путь:

```bash
pip install -r requirements-train.txt
```

## Основные endpoint-ы

- `GET /profiles` — доступные профили
- `GET /ui` — веб-интерфейс запуска пайплайна
- `GET /chat/models` — список моделей для чат-интерфейса
- `POST /chat/message` — чатовая точка интеграции (pipeline + анализ через выбранную модель)
- `POST /reports/create` — создать задачу
- `POST /reports/{report_id}/documents` — загрузить документы
- `POST /reports/{report_id}/extract` — извлечь факты
- `POST /reports/{report_id}/generate` — сгенерировать черновик и карту доказательств
- `GET /reports/{report_id}/draft` — получить черновик
- `GET /reports/{report_id}/explain` — получить `EvidenceMap`
- `POST /reports/{report_id}/validate` — экспертное решение по разделу

## Пример сценария

1. Создать отчет:
```bash
curl -X POST http://127.0.0.1:8000/reports/create \
  -H "Content-Type: application/json" \
  -d '{"title":"Отчет апрель","profile_id":"rosobrnadzor"}'
```

2. Загрузить файл:
```bash
curl -X POST http://127.0.0.1:8000/reports/<REPORT_ID>/documents \
  -F "files=@sample.txt"
```

3. Запустить извлечение и генерацию:
```bash
curl -X POST http://127.0.0.1:8000/reports/<REPORT_ID>/extract
curl -X POST http://127.0.0.1:8000/reports/<REPORT_ID>/generate
curl http://127.0.0.1:8000/reports/<REPORT_ID>/explain
```

## Тестирование

```bash
pytest -q
```

## Ограничения MVP

- Поддержка извлечения текста: `.txt`, `.md`, `.csv`, `.json`, `.log`, `.docx`, `.pdf`, `.xlsx`, `.xlsm`.
- Нормативная база и шаблоны пока встроены в код.
- БД заменена файловым JSON-хранилищем для ускорения прототипирования.

## Обучение своей модели (SFT)

В проект добавлен минимальный пайплайн для старта обучения собственной модели (LoRA fine-tuning).

### 1) Окружение для обучения

```bash
python3.13 -m venv .venv-train
source .venv-train/bin/activate
pip install -r requirements-train.txt
```

### 2) Источник данных

Вариант A: быстрый smoke-тест на локальном наборе:

```bash
python scripts/prepare_training_data.py \
  --input data/raw/dolly_sample.jsonl \
  --output data/processed/sft_dataset.jsonl
```

Вариант B: Kaggle (нужен API-ключ):

```bash
python scripts/download_kaggle_dataset.py \
  --dataset databricks/databricks-dolly-15k \
  --out data/raw \
  --unzip
```

Вместо `kaggle.json` можно использовать новый токен:

```bash
export KAGGLE_API_TOKEN=<your_token>
```

Пример подготовки смешанного Kaggle набора (Dolly + OpenOrca + UltraChat + OASST):

```bash
python scripts/prepare_kaggle_sft.py \
  --output data/processed/sft_kaggle_mix_v1.jsonl \
  --dolly-limit 3500 \
  --openorca-limit 4000 \
  --ultrachat-limit 3000 \
  --oasst-limit 1500
```

После скачивания подготовить датасет (`.csv` или `.jsonl`):

```bash
python scripts/prepare_training_data.py \
  --input data/raw/<your_dolly_file>.csv \
  --output data/processed/sft_dataset.jsonl \
  --limit 5000
```

Вариант C: Hugging Face (если Kaggle ключ еще не настроен):

```bash
python scripts/prepare_hf_dataset.py \
  --dataset saillab/alpaca-russian-cleaned \
  --split train \
  --instruction-field instruction \
  --context-field input \
  --response-field output \
  --output data/processed/sft_ru_alpaca10k.jsonl \
  --limit 10000 \
  --min-cyrillic-ratio 0.45
```

Вариант C2: новые conversation-датасеты (HF) с автоматической конвертацией в SFT:

```bash
python scripts/prepare_hf_conversations.py \
  --dataset FierceLLM/ru-instruct-10k \
  --split train \
  --output data/processed/sft_ru_fierce10k.jsonl \
  --max-pairs-per-dialog 1 \
  --min-cyrillic-ratio 0.3

python scripts/prepare_hf_conversations.py \
  --dataset ZeroAgency/ru-instruct-conversation-v2-small \
  --split train \
  --output data/processed/sft_ru_zeroagency_v2_small.jsonl \
  --limit-rows 25000 \
  --max-pairs-per-dialog 1 \
  --min-cyrillic-ratio 0.3
```

Вариант D: доменный синтетический набор под задачу отчетности:

```bash
python scripts/generate_domain_sft.py \
  --output data/processed/sft_domain_synth4k.jsonl \
  --rows 4000
```

Смешивание датасетов:

```bash
python scripts/mix_sft_datasets.py \
  --input data/processed/sft_ru_alpaca10k.jsonl:9000 \
  --input data/processed/sft_domain_synth4k.jsonl:1500 \
  --input data/processed/sft_dataset.jsonl \
  --output data/processed/sft_mix_v3_10k5.jsonl \
  --max-total 10500
```

Смешивание нового `v2` набора под full fine-tune:

```bash
python scripts/mix_sft_datasets.py \
  --input data/processed/sft_ru_zeroagency_v2_small.jsonl:5000 \
  --input data/processed/sft_ru_fierce10k.jsonl:3500 \
  --input data/processed/sft_ru_oasst_chains.jsonl:2000 \
  --input data/processed/sft_domain_synth4k.jsonl:2500 \
  --input data/processed/sft_ru_alpaca10k.jsonl:2500 \
  --output data/processed/sft_full_mix_v2_15k5.jsonl \
  --max-total 15500
```

Смешивание `v3` (v2 + Kaggle):

```bash
python scripts/mix_sft_datasets.py \
  --input data/processed/sft_full_mix_v2_15k5.jsonl \
  --input data/processed/sft_kaggle_mix_v1.jsonl:8000 \
  --output data/processed/sft_full_mix_v3_23k5.jsonl \
  --max-total 23500
```

### 3) Старт обучения

```bash
python scripts/train_sft.py \
  --dataset data/processed/sft_mix_v3_10k5.jsonl \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --output data/models/sft-qwen05b-mixv3 \
  --max-steps 120 \
  --learning-rate 2e-5
```

Альтернатива для более легкой модели:

```bash
python scripts/train_sft.py \
  --dataset data/processed/sft_mix_v3_10k5.jsonl \
  --model ai-forever/rugpt3small_based_on_gpt2 \
  --output data/models/sft-rugpt3small-mixv3-continued \
  --init-adapter data/models/sft-rugpt3small-dolly2k-v1/adapter \
  --max-steps 180 \
  --learning-rate 2e-5
```

Полное дообучение (без LoRA, сохраняется вся модель):

```bash
python scripts/train_full_sft.py \
  --dataset data/processed/sft_mix_v3_10k5.jsonl \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --output data/models/full-qwen05b-report \
  --max-steps 120 \
  --learning-rate 2e-5
```

Запуск по готовому full-training конфигу:

```bash
python scripts/run_full_training.py --config training/configs/full_mps_qwen05b.json
```

Профили:
- `training/configs/full_mps_qwen05b.json` — стабильный профиль для Apple Silicon (MPS);
- `training/configs/full_cuda24_qwen05b.json` — профиль для CUDA сервера (~24GB VRAM);
- `training/configs/full_mps_qwen05b_v2_newdata.json` — профиль обучения на новом `v2` mix;
- `training/configs/full_mps_qwen05b_v3_kaggle.json` — профиль обучения на `v3` mix с Kaggle;
- `training/configs/full_smoke_distilgpt2.json` — быстрый smoke-check пайплайна.

### 4) Проверка результата

```bash
python scripts/infer_sft.py \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter data/models/sft-qwen05b-mixv3/adapter \
  --prompt "### Инструкция:\nСформируй краткий отчет.\n\n### Контекст:\nЧисленность: 1200\n\n### Ответ:\n"
```

### 5) Оценка качества (loss/perplexity)

```bash
python scripts/eval_sft.py \
  --dataset data/processed/sft_mix_v3_10k5.jsonl \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --adapter data/models/sft-qwen05b-mixv3/adapter \
  --eval-samples 300 \
  --response-only-loss
```

### Файлы обучения

- `scripts/download_kaggle_dataset.py` — скачивание public Kaggle датасетов.
- `scripts/prepare_training_data.py` — приведение `.csv/.jsonl` к SFT-формату.
- `scripts/prepare_hf_dataset.py` — подготовка SFT из Hugging Face датасетов.
- `scripts/prepare_hf_conversations.py` — конвертация HF conversation-датасетов в SFT jsonl.
- `scripts/prepare_kaggle_sft.py` — конвертация Kaggle conversation/QA датасетов в единый SFT jsonl.
- `scripts/generate_domain_sft.py` — генерация доменного SFT для сценариев отчетности/XAI.
- `scripts/mix_sft_datasets.py` — смешивание и дедупликация наборов.
- `scripts/train_sft.py` — LoRA fine-tune (HF Transformers + PEFT).
- `scripts/train_full_sft.py` — full fine-tune (сохранение полной модели).
- `scripts/infer_sft.py` — инференс с адаптером.
- `scripts/eval_sft.py` — быстрая оценка (loss/perplexity).
