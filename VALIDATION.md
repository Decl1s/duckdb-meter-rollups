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

Локально Windows/GUI IDE не проверял. CI ниже фиксирую только после реального
завершения. Нагрузку, multi-process writer, аварийный COMMIT, power loss, network FS
и hostile path races не проверял. Источник телеметрии/полноту/тарифы не моделирую.
