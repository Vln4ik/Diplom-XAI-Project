# GitHub Publication Status

## 1. Назначение документа

Этот документ фиксирует текущее состояние проекта с точки зрения публикации на GitHub:

- что уже подготовлено
- что ещё нужно сделать
- какие есть технические блокеры
- в каком порядке публиковать репозиторий

## 2. Что уже подготовлено к публикации

На момент фиксации подготовлено:

- monorepo со структурой `backend`, `frontend`, `infra`, `docs`, `samples`
- рабочий `README`
- system handbook
- отдельная документация по `LLM/XAI`
- отдельная документация по roadmap
- acceptance, demo, performance и load docs
- локальный AI runtime через `Ollama`
- browser e2e и backend tests

Иными словами, у проекта уже есть не только код, но и полноценный documentation pack.

## 3. Текущие объективные блокеры публикации

На момент фиксации публикация в GitHub ещё не завершена по двум техническим причинам:

- в локальном git-репозитории не настроен `remote`
- локальный `gh` CLI не авторизован

Это означает:

- подготовка репозитория завершена не полностью в организационном смысле
- код и docs готовы локально, но push в удалённый origin пока невозможен

## 4. Текущее состояние рабочего дерева

Рабочее дерево отражает переход от старого прототипа к новому monorepo. Поэтому в git сейчас одновременно видны:

- удалённые tracked-файлы старого прототипа
- новые untracked директории нового monorepo

Это не ошибка проекта как такового, а следствие архитектурной миграции.

Перед публикацией нужно:

- осознанно зафиксировать новый monorepo как основное состояние репозитория
- либо отдельно архивировать старый прототип
- затем уже публиковать итоговую структуру

## 5. Рекомендуемый порядок публикации

1. Настроить GitHub-аутентификацию:
   `gh auth login`
2. Настроить удалённый репозиторий:
   `git remote add origin <repo-url>`
3. Проверить финальный состав файлов для первой публикации.
4. Сделать осознанный initial publication commit нового monorepo.
5. Запушить `main`.
6. При необходимости отдельно оформить `roadmap` и `legacy-prototype`.

## 6. Что желательно приложить к публичному репозиторию

Минимальный публичный набор:

- [README.md](/Users/vinchik/Desktop/Diplom/README.md)
- [docs/system-handbook.md](/Users/vinchik/Desktop/Diplom/docs/system-handbook.md)
- [docs/llm-xai-method.md](/Users/vinchik/Desktop/Diplom/docs/llm-xai-method.md)
- [docs/architecture-decisions.md](/Users/vinchik/Desktop/Diplom/docs/architecture-decisions.md)
- [docs/roadmap-status.md](/Users/vinchik/Desktop/Diplom/docs/roadmap-status.md)
- [docs/demo-scenario.md](/Users/vinchik/Desktop/Diplom/docs/demo-scenario.md)
- [docs/acceptance-checklist.md](/Users/vinchik/Desktop/Diplom/docs/acceptance-checklist.md)
- [docs/performance-baseline.md](/Users/vinchik/Desktop/Diplom/docs/performance-baseline.md)
- [docs/load-baseline.md](/Users/vinchik/Desktop/Diplom/docs/load-baseline.md)

## 7. Что стоит указать в описании репозитория

Рекомендуемая смысловая формулировка:

`Web-first XAI platform for evidence-grounded regulatory reporting with local AI, hybrid retrieval, and human-in-the-loop review.`

Ключевые теги:

- `xai`
- `llm`
- `retrieval`
- `fastapi`
- `react`
- `pgvector`
- `ollama`
- `regtech`
- `document-ai`

## 8. Что стоит подчеркнуть в публичном README

При публикации полезно явно зафиксировать:

- проект находится на стадии `working MVP`
- основной сценарий сейчас: `Рособрнадзор + образовательная организация`
- локальный AI-контур работает через `Ollama`
- часть статистик является инженерной оценкой по demo-сценарию, а не формальным field study

## 9. Что можно оформить после первой публикации

После базового push логично добавить:

- GitHub Issues по следующим этапам
- Milestones под roadmap
- Release notes для MVP
- screenshot pack или короткий demo-gif
- отдельный раздел “Known limitations”

## 10. Итоговый статус

Публикационный пакет по содержанию уже подготовлен.

До фактического размещения на GitHub остаётся:

- настроить `origin`
- выполнить `gh auth login`
- сделать публикационный commit и push

То есть блокер сейчас не в отсутствии документации или кода, а только в настройке GitHub-доступа и финальной фиксации состояния репозитория.
