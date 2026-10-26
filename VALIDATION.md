# Что я фактически проверил

26.10.2026, 0.1.0. Локальная среда: Linux x86-64, CPython 3.12.15,
DuckDB 2.0.0, uv 0.13.1. Все данные получены собственным генератором.

| Проверка | Факт |
| --- | --- |
| Установка | Единственная distribution duckdb2.0.0 установлена с проверкой hashes в собственной .venv |
| unittest | 15 tests OK; bad-value subtests включают календарь, timezone, год0000, дробь, leading zero и bounds |
| CLI smoke | generate→ingest→repeat→late→conflict→report→export прошёл |
| Бизнес-итог | 6events,910Wh,2batches,3hourrows; SITE_A10=420,SITE_A cumulative11=510 |
| Повторы/ошибки | Noop equal batch, equal event across packages, whole-package conflict без E007, чужая БД сохранена |
| Parquet | Round-trip читается DuckDB,3rows/840Wh до late; no-overwrite и неизменность старого snapshot после late подтверждены |
| Публичный ZIP/запуск из ZIP | 25 allowlisted UTF-8 файлов, состав и байты ZIP сверены; из распакованного архива tests15 OK и полный smoke прошли |
| GitHub source/CI/release | Публикацию/итог CI/вложения подтвержу отдельно; не считаю ссылки доказательством |

Первый вызов unittest я сделал до завершения скачивания DuckDB: получил
ModuleNotFoundError. Дождался окончания установки и повторил проверки успешно.
При чтении календарного контракта явно ограничил годы2000…2099 и добавил year0000
subtest, чтобы SQL timestamp не породил значение вне Python datetime при выводе.
Остальные перечисленные сценарии прошли без обнаруженных функциональных ошибок.
Не придумываю историю производственного инцидента.

Первые CI runs40306561397/40306564403 не создали jobs: GitHub сообщил Invalid
workflow file на line23. Причиной был YAML plain scalar с --only-binary=:all:
перед пробелом. Я перенёс команду в block scalar >-, без изменения приложения,
и запустил CI новым коммитом. Итог следующего прогона зафиксирую после завершения.

CI40306787814: Ubuntu прошёл tests/smoke/package, Windows остановился на setup-python:
3.12.15 x64 не найден для Windows2025. Я проверил официальный actions/python-versions
manifest и выбрал доступный3.12.10 только для Windows matrix. Linux сохранил3.12.15.
Это ограничение распространения Python, а не ошибка DuckDB; итог после смены matrix
не считаю успешным до фактического завершения.

CI40306973374: Ubuntu снова прошёл, Windows дошёл до tests и обнаружил
UnicodeDecodeError при чтении русских SQL-комментариев через default cp1252.
Я явно задал UTF-8 обоим SQL read_text. Для fsync своего временного Parquet
использую writable r+b handle. Повторные tests/smoke и CI проверяют эти изменения.

Локально Windows/GUI IDE не проверял. CI ниже фиксирую только после реального
завершения. Нагрузку, multi-process writer, аварийный COMMIT, power loss, network FS
и hostile path races не проверял. Источник телеметрии/полноту/тарифы не моделирую.
