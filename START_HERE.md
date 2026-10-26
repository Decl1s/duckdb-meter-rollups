# Как я разбираю и меняю проект

Я открываю duckdb-meter-rollups.code-workspace в VS Code или совместимом редакторе.
Собственная .venv ставится командами README. Tasks «Я запускаю проверки» и «Я смотрю
демонстрацию» запускают только явные команды после моего выбора; auto-run нет.
Наличие конфигурации не означает проверку окна IDE.

| Файл | Что я там объясняю | Где я меняю поведение |
| --- | --- | --- |
| meter_rollups/__main__.py | Аргументы и безопасный JSON/error code | Новый CLI параметр, не формулы |
| meter_rollups/store.py | Frozen bytes, identity, транзакция, report/export | Границы загрузки и публикации |
| meter_rollups/validate.sql | Явные ID/time/integer predicates | Допустимые значения, затем тесты |
| meter_rollups/schema.sql | Canonical tables и view | Grain, GROUP BY и window frame |
| meter_rollups/synthetic.py | Три фиксированных CSV | Новая задача для самостоятельного опыта |
| tests/test_rollups.py | Предметные инварианты и регрессии | Контроль изменения, не копия SQL |
| scripts/smoke.py | Полная CLI история в temp folder | Демонстрация без мусора |
| scripts/package_release.py | Явный allowlist, privacy scan, ZIP/sha | Разрешённые исходники |
| NOTES/CONCEPT/TECHNOLOGIES/VALIDATION | Смысл, решения, стек, факты | Я обновляю контракт вместе с кодом |

## Зачем я передаю аргументы

--db выбирает свой DuckDB файл; --input — явный локальный CSV, пути из данных
не исполняю. --output у generate — новый каталог, у export — новый файл в уже
существующем каталоге. Параметризую SQL path/value вместо строковой подстановки.
Ошибку возвращаю кодом и exit2, success — JSON и exit0; traceback/CSV строки
обычной командой не раскрываю. Не удаляю чужую БД для «починки» identity.

## Первая осмысленная правка

Я начинаю с пяти заданий NOTES. Для новой метрики сначала называю зерно и единицу,
затем меняю schema.sql и golden ожидание fixture. Существующая schema1 БД не получает
новый view автоматически: первую версию я изучаю на новом disposable db файле.
Настоящий upgrade потребует отдельной schema version/migration, а не ручного UPDATE
app_meta. Перед публикацией повторяю tests/smoke/package. Рабочие CSV/БД/Parquet
оставляю вне PUBLIC_FILES.
