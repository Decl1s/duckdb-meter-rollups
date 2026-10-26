# DuckDB Meter Rollups

Я строю небольшую почасовую витрину энергопотребления площадок. На входе — CSV
с измерениями, на выходе — SQL-отчёт и отдельный Parquet snapshot. Повторная
доставка не удваивает сумму, поздний факт меняет нужный час, конфликт ID отклоняет
весь пакет. Это учебный проект на полностью синтетических данных.

Основной инструмент — **DuckDB 2.0.0**, оболочка — Python 3.12.15. Облачных сервисов
и серверной установки нет. Я изучаю GROUP BY, DISTINCT, транзакции, оконный
накопительный итог и Parquet. С предыдущим Go-проектом основной инструмент различается.

## Быстрый запуск

Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python scripts/smoke.py
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/Scripts/python.exe scripts/smoke.py
```

Smoke сам проходит генерацию, два приёма, повтор, конфликт и Parquet в временном
каталоге, затем удаляет свои файлы. Ожидаю 6 событий, 910 Wh, 2 принятых пакета и
3 часовые строки. Локальный факт и CI я фиксирую отдельно в VALIDATION.

## Как я изучаю сохранённый результат за 5–10 минут

Ниже `python` означает интерпретатор созданной .venv; я активирую её либо заменяю
команду полным относительным путём из примера выше.

```bash
python -m meter_rollups generate --output workspace
python -m meter_rollups ingest --db workspace/energy.duckdb --input workspace/initial.csv
python -m meter_rollups report --db workspace/energy.duckdb
python -m meter_rollups ingest --db workspace/energy.duckdb --input workspace/initial.csv
python -m meter_rollups ingest --db workspace/energy.duckdb --input workspace/late.csv
python -m meter_rollups report --db workspace/energy.duckdb
python -m meter_rollups export --db workspace/energy.duckdb --output workspace/hours.parquet
python -m meter_rollups ingest --db workspace/energy.duckdb --input workspace/conflict.csv
```

До late.csv сумма 840 Wh; после — 910. У SITE_A час 10:00 меняется с 350 на 420,
накопительный итог в 11:00 — с 440 на 510. Повтор initial.csv даёт duplicate_batch,
новых событий 0. Последняя команда возвращает EVENT_CONFLICT и exit code 2:
новый E007 из этого же пакета тоже не сохраняется. Ранее экспортированный Parquet
остаётся прежним snapshot. Экспорт и генератор не заменяют существующий output.

## Проверки и материалы

```bash
python -m unittest discover -s tests -v
python scripts/smoke.py
python scripts/package_release.py
```

Я подготовил 15 тестов с проверкой повторов, целостности, UTC day boundary,
некорректных данных, защиты чужой БД и Parquet round-trip. ZIP содержит только
PUBLIC_FILES.txt, рядом сохраняю SHA256SUMS. Реальный статус — [VALIDATION](VALIDATION.md).

- [START_HERE](START_HERE.md) — карта кода, аргументы и место для первой правки.
- [NOTES](NOTES.md) — подробный конспект, примеры, вопросы и пять упражнений.
- [CONCEPT](CONCEPT.md) — контракт, границы и критерии.
- [TECHNOLOGIES](TECHNOLOGIES.md) — версии, все зависимости и официальные источники.

Я публикую исходники в [Decl1s/duckdb-meter-rollups](https://github.com/Decl1s/duckdb-meter-rollups).
[Релиз v0.1.0](https://github.com/Decl1s/duckdb-meter-rollups/releases/tag/v0.1.0),
[ZIP](https://github.com/Decl1s/duckdb-meter-rollups/releases/download/v0.1.0/duckdb-meter-rollups-0.1.0.zip),
[SHA256SUMS](https://github.com/Decl1s/duckdb-meter-rollups/releases/download/v0.1.0/SHA256SUMS)
проверяю после публикации; наличие ссылки само по себе не означает готовый релиз.

Я не подключаю реальные приборы, не читаю персональные данные, не считаю тарифы,
не исправляю факт по тому же event_id. Максимум одного CSV — 10 MiB/100000 строк,
timestamp только UTC в секундах, годы 2000…2099. Витрина не доказывает полноту
телеметрии: пропущенный час не равен нулевому потреблению. Я поддерживаю одного
писателя, не обещаю broker semantics, power-loss гарантии и неограниченный объём.
