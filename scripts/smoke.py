"""Я показываю законченный CLI-сценарий в одноразовом каталоге."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='meter-demo-') as folder:
        work=Path(folder)
        def call(*args, expected=0):
            result=subprocess.run([sys.executable,'-m','meter_rollups',*map(str,args)],cwd=ROOT,
                                  capture_output=True,text=True,encoding='utf-8')
            if result.returncode!=expected:
                raise AssertionError(result.stderr)
            return json.loads(result.stdout) if expected==0 else result.stderr.strip()
        call('generate','--output',work/'input')
        call('ingest','--db',work/'meter.duckdb','--input',work/'input/initial.csv')
        repeat=call('ingest','--db',work/'meter.duckdb','--input',work/'input/initial.csv')
        assert repeat['duplicate_batch']
        call('ingest','--db',work/'meter.duckdb','--input',work/'input/late.csv')
        assert call('ingest','--db',work/'meter.duckdb','--input',work/'input/conflict.csv',expected=2)=='EVENT_CONFLICT'
        result=call('report','--db',work/'meter.duckdb')
        assert (result['event_count'],result['total_energy_wh'],result['batch_count'])==(6,910,2)
        exported=call('export','--db',work/'meter.duckdb','--output',work/'hours.parquet')
        assert exported['exported'] and (work/'hours.parquet').read_bytes()[:4]==b'PAR1'
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
