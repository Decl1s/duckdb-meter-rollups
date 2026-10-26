"""Я принимаю полный CSV одним COMMIT; SQL формирует почасовую витрину."""

from contextlib import contextmanager
import csv
import hashlib
import io
import os
from pathlib import Path
import tempfile

import duckdb

ROOT = Path(__file__).parent
HEADER = ['event_id', 'site_id', 'meter_id', 'occurred_at', 'energy_wh']
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100000


class InputError(ValueError):
    """Я возвращаю фиксированный код, без исходной строки или приватного пути."""


def snapshot(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise InputError('INPUT_NOT_REGULAR')
        with path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise InputError('INPUT_TOO_LARGE')
        text = data.decode('utf-8')
        if '\x00' in text or text.startswith('\ufeff'):
            raise InputError('INPUT_ENCODING')
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        if next(reader, None) != HEADER:
            raise InputError('CSV_HEADER')
        count = 0
        for row in reader:
            count += 1
            if len(row) != len(HEADER):
                raise InputError('CSV_WIDTH')
            if count > MAX_ROWS:
                raise InputError('INPUT_TOO_MANY_ROWS')
        if not count:
            raise InputError('CSV_EMPTY')
        return data
    except (OSError, UnicodeError, csv.Error):
        raise InputError('INPUT_UNREADABLE') from None


@contextmanager
def database(path: Path, *, create: bool = False):
    """Я проверяю маркер существующей БД и не делаю auto-migration чужой схемы."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InputError('DATABASE_NOT_REGULAR')
    existed = path.exists()
    if not existed and not create:
        raise InputError('DATABASE_MISSING')
    connection = None
    try:
        connection = duckdb.connect(str(path), read_only=not create, config={
            'autoinstall_known_extensions': False, 'autoload_known_extensions': False,
            'threads': 2, 'memory_limit': '256MB',
        })
        if existed:
            names = {r[0] for r in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
            if names != {'app_meta', 'ingest_batch', 'meter_event', 'hourly_usage'}:
                raise InputError('DATABASE_IDENTITY')
            if connection.execute('SELECT * FROM app_meta').fetchall() != [('duckdb-meter-rollups', 1)]:
                raise InputError('DATABASE_IDENTITY')
        else:
            connection.execute('BEGIN')
            try:
                connection.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
                connection.execute('COMMIT')
            except BaseException:
                connection.execute('ROLLBACK')
                raise
        yield connection
    except duckdb.Error:
        # Ошибка COMMIT не доказывает rollback: повторяю тот же CSV по batch identity.
        raise InputError('DATABASE_UNCONFIRMED') from None
    finally:
        if connection is not None:
            connection.close()


def ingest(db_path: Path, input_path: Path) -> dict:
    data = snapshot(input_path)
    digest = hashlib.sha256(data).hexdigest()
    batch_id = hashlib.sha256(b'meter-csv:v1\0' + data).hexdigest()
    # DuckDB читает уже замороженные байты, изменение исходного файла не смешает версии.
    with tempfile.TemporaryDirectory(prefix='meter-input-') as folder:
        frozen = Path(folder) / 'input.csv'
        frozen.write_bytes(data)
        with database(db_path, create=True) as connection:
            old = connection.execute('SELECT input_rows,new_events,duplicate_rows FROM ingest_batch WHERE batch_id=?',
                                     [batch_id]).fetchone()
            if old:
                return dict(batch_id=batch_id, duplicate_batch=True, input_rows=old[0],
                            new_events=0, duplicate_rows=old[0])
            connection.execute('BEGIN')
            try:
                connection.execute("CREATE TEMP TABLE incoming AS SELECT * FROM read_csv(?, "
                                   "header=true, auto_detect=false, delim=',', quote='\"', escape='\"', "
                                   "strict_mode=true, null_padding=false, columns={"
                                   "'event_id':'VARCHAR','site_id':'VARCHAR','meter_id':'VARCHAR',"
                                   "'occurred_at':'VARCHAR','energy_wh':'VARCHAR'})", [str(frozen)])
                count = connection.execute('SELECT count(*) FROM incoming').fetchone()[0]
                if not 1 <= count <= MAX_ROWS:
                    raise InputError('CSV_ROW_COUNT')
                if connection.execute((ROOT / 'validate.sql').read_text(encoding='utf-8')).fetchone()[0]:
                    raise InputError('ROW_CONTRACT')
                connection.execute("CREATE TEMP TABLE canonical AS SELECT DISTINCT event_id,site_id,meter_id,"
                                   "strptime(occurred_at,'%Y-%m-%dT%H:%M:%SZ') AS occurred_at,"
                                   "cast(energy_wh AS BIGINT) AS energy_wh FROM incoming")
                if connection.execute('SELECT event_id FROM canonical GROUP BY event_id HAVING count(*)>1 LIMIT 1').fetchone():
                    raise InputError('EVENT_CONFLICT')
                if connection.execute('SELECT c.event_id FROM canonical c JOIN meter_event e USING(event_id) '
                                      'WHERE (c.site_id,c.meter_id,c.occurred_at,c.energy_wh) '
                                      'IS DISTINCT FROM (e.site_id,e.meter_id,e.occurred_at,e.energy_wh) LIMIT 1').fetchone():
                    raise InputError('EVENT_CONFLICT')
                new_count = connection.execute('SELECT count(*) FROM canonical c WHERE NOT EXISTS '
                                               '(SELECT 1 FROM meter_event e WHERE e.event_id=c.event_id)').fetchone()[0]
                connection.execute('INSERT INTO ingest_batch(batch_id,input_sha256,input_rows,new_events,duplicate_rows) '
                                   'VALUES (?,?,?,?,?)', [batch_id,digest,count,new_count,count-new_count])
                connection.execute('INSERT INTO meter_event SELECT c.*,? FROM canonical c '
                                   'WHERE NOT EXISTS (SELECT 1 FROM meter_event e WHERE e.event_id=c.event_id)', [batch_id])
                connection.execute('COMMIT')
            except BaseException:
                try:
                    connection.execute('ROLLBACK')
                except duckdb.Error:
                    pass
                raise
    return dict(batch_id=batch_id,duplicate_batch=False,input_rows=count,
                new_events=new_count,duplicate_rows=count-new_count)


def report(db_path: Path) -> dict:
    with database(db_path) as connection:
        rows = connection.execute('SELECT * FROM hourly_usage ORDER BY site_id,hour_utc').fetchall()
        events = connection.execute('SELECT count(*),coalesce(sum(energy_wh),0) FROM meter_event').fetchone()
        batches = connection.execute('SELECT count(*) FROM ingest_batch').fetchone()[0]
    return {'event_count':events[0], 'total_energy_wh':int(events[1]), 'batch_count':batches,
            'hours':[dict(site_id=r[0],hour_utc=r[1].isoformat()+'Z',event_count=r[2],meter_count=r[3],
                          energy_wh=int(r[4]),day_cumulative_wh=int(r[5])) for r in rows]}


def export_parquet(db_path: Path, output: Path) -> dict:
    """Я публикую один полностью записанный Parquet без замены существующего файла."""
    if output.exists() or output.is_symlink():
        raise InputError('OUTPUT_EXISTS')
    pending = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.meter-',suffix='.parquet',dir=output.parent,delete=False) as temp:
            pending = Path(temp.name)
        with database(db_path) as connection:
            connection.execute("COPY (SELECT * FROM hourly_usage ORDER BY site_id,hour_utc) TO ? "
                               "(FORMAT PARQUET, COMPRESSION ZSTD)", [str(pending)])
        with pending.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.link(pending,output)
        if os.name == 'posix':
            descriptor = os.open(output.parent,os.O_RDONLY | getattr(os,'O_DIRECTORY',0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return {'exported':True, 'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    except FileExistsError:
        raise InputError('OUTPUT_EXISTS') from None
    except OSError:
        raise InputError('EXPORT_UNCONFIRMED') from None
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
