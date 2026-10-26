# Какие технологии я использую

26.10.2026, 0.1.0. Основной инструмент отличается от предыдущего Go quality gate.
Я возвращаюсь к встроенному SQL с новым узким сценарием: поздние измерения,
почасовой GROUP BY, window frame и Parquet snapshot на DuckDB 2.0 LTS.

| Компонент | Версия | Зачем я его выбрал | Официальный источник |
| --- | --- | --- | --- |
| CPython | 3.12.15 | CLI, файловые границы, проверки; без отдельного app framework | [Python 3.12](https://docs.python.org/3.12/) |
| duckdb | 2.0.0 | Единственная Python runtime dependency: встроенный OLAP SQL, CSV/Parquet | [PyPI 2.0.0](https://pypi.org/project/duckdb/2.0.0/), [DuckDB 2.0](https://duckdb.org/docs/2.0/) |
| SQL DuckDB | Вместе с 2.0.0 | VARCHAR staging, TRY_CAST/STRPTIME, DISTINCT, GROUP BY, transaction и window | [CSV](https://duckdb.org/docs/2.0/data/csv/overview), [transactions](https://duckdb.org/docs/2.0/sql/statements/transactions), [window](https://duckdb.org/docs/2.0/sql/functions/window_functions) |
| Parquet + Zstandard | Реализация DuckDB 2.0.0 wheel | Типизированный сжатый snapshot без отдельного pyarrow пакета | [Parquet export](https://duckdb.org/docs/2.0/data/parquet/overview) |
| argparse/json/pathlib/sys | stdlib 3.12 | Параметры, JSON, пути, exit codes и UTF-8 stdout | [stdlib](https://docs.python.org/3.12/library/) |
| csv/io/tempfile/contextlib | stdlib 3.12 | Header/width boundary, frozen snapshot и закрытие ресурсов | [csv](https://docs.python.org/3.12/library/csv.html) |
| hashlib/os | stdlib 3.12 | SHA-256, fsync и no-overwrite hard link; SHA не цифровая подпись | [os](https://docs.python.org/3.12/library/os.html) |
| unittest/subprocess | stdlib 3.12 | 15 автоматических сценариев и настоящий CLI smoke | [unittest](https://docs.python.org/3.12/library/unittest.html) |
| zipfile/re | stdlib 3.12 | Явный список исходников, сигнатуры приватных данных, ZIP/контрольная сумма | [zipfile](https://docs.python.org/3.12/library/zipfile.html) |
| uv | 0.13.1 локально | Я разрешил зависимости и установил hashes в отдельную .venv | [uv](https://docs.astral.sh/uv/) |
| pip | Из venv/CI, patch не закрепляю | Установка requirements.lock с --require-hashes/--only-binary; не runtime dependency | [pip hashes](https://pip.pypa.io/en/stable/topics/secure-installs/) |
| Git/Markdown/JSON/TOML/YAML | Git format; текстовые конфиги | Собственный репозиторий, документы, IDE и CI | [Git](https://git-scm.com/docs), [GitHub Actions](https://docs.github.com/en/actions) |
| VS Code | Необязательный, не закрепляю | Карта кода и явные tasks; запуск GUI не подтверждаю | [tasks](https://code.visualstudio.com/docs/editor/tasks) |

В requirements.in одна прямая зависимость duckdb==2.0.0. requirements.lock
содержит exact pin и hashes официальных артефактов. В установленной .venv только
одна distribution: дополнительных Python-транзитивных пакетов нет. Нативный
движок/кодеки входят в DuckDB wheel; отдельно их версии я не измерял. Не ставлю
pandas/pyarrow/dbt и не скачиваю extensions: autoinstall/autoload отключены.

CI использует checkout 11d5960a326750d5838078e36cf38b85af677262,
setup-python a26af69be951a213d495a4c3e4e4022e16d87065 и
upload-artifact ea165f8d65b6e75b540449e92b4886f43607fa02 с contents:read.
Я закрепил actions по commit SHA и Python 3.12.15; версии хостов ubuntu-latest/
windows-latest управляются GitHub. Факт результатов CI — только VALIDATION.
