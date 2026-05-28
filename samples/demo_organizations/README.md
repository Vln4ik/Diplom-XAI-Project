# Демо-набор организаций

Этот каталог содержит пакет из `10` демонстрационных образовательных организаций для локального тестирования `XAI Report Builder`.

Что здесь публичное:
- наименование организации;
- краткое наименование;
- официальный сайт;
- ссылка на официальный публичный источник.

Что здесь синтетическое:
- ИНН, КПП, ОГРН, телефоны, email, адреса, ФИО ответственных;
- текстовые, табличные и JSON-файлы;
- лицензии, реестры программ, кадровые таблицы и локальные акты.

Важно:
- это не официальный реестр организаций;
- это демонстрационный seed-pack для UI, document pipeline, retrieval, XAI и benchmark-подобных сценариев;
- синтетические поля нужны, чтобы не смешивать реальную публичную организацию с недостоверными контактами и реквизитами.

Структура:
- [manifest.json](/Users/vinchik/Desktop/Diplom/samples/demo_organizations/manifest.json) — описание 10 организаций и их демо-профилей;
- `generated/<slug>/` — автоматически сгенерированные файлы по каждой организации;
- [backend/scripts/generate_demo_organizations.py](/Users/vinchik/Desktop/Diplom/backend/scripts/generate_demo_organizations.py) — генератор файлов;
- [backend/scripts/import_demo_organizations.py](/Users/vinchik/Desktop/Diplom/backend/scripts/import_demo_organizations.py) — импорт в текущую БД приложения.
