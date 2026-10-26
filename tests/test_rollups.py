"""Я проверяю контракт, повторы, атомарный отказ, поздние данные и Parquet."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import duckdb

from meter_rollups.store import HEADER, InputError, ingest, report, export_parquet
from meter_rollups.synthetic import generate


class Rollups(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.db=self.root/'meter.duckdb'
        self.inputs=self.root/'input'
        generate(self.inputs)
        self.addCleanup(self.temporary.cleanup)

    def file(self,rows,name='custom.csv',header=None):
        path=self.root/name
        with path.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n')
            writer.writerow(header or HEADER)
            writer.writerows(rows)
        return path

    def test_initial_exact_sums_and_grain(self):
        result=ingest(self.db,self.inputs/'initial.csv')
        self.assertEqual((result['input_rows'],result['new_events'],result['duplicate_rows']),(6,5,1))
        summary=report(self.db)
        self.assertEqual((summary['event_count'],summary['total_energy_wh'],len(summary['hours'])),(5,840,3))
        self.assertEqual(summary['hours'][0]['energy_wh'],350)
        self.assertEqual(summary['hours'][1]['day_cumulative_wh'],440)
        self.assertEqual(summary['hours'][0]['meter_count'],2)

    def test_identical_batch_is_noop(self):
        ingest(self.db,self.inputs/'initial.csv')
        before=report(self.db)
        self.assertTrue(ingest(self.db,self.inputs/'initial.csv')['duplicate_batch'])
        self.assertEqual(report(self.db),before)

    def test_same_event_in_another_delivery_does_not_double_count(self):
        ingest(self.db,self.inputs/'initial.csv')
        other=self.file([('E001','SITE_A','M01','2026-10-26T10:05:00Z','100')])
        result=ingest(self.db,other)
        self.assertEqual((result['new_events'],result['duplicate_rows']),(0,1))
        self.assertEqual(report(self.db)['total_energy_wh'],840)
        self.assertEqual(report(self.db)['batch_count'],2)

    def test_late_event_updates_old_bucket_and_day_window(self):
        ingest(self.db,self.inputs/'initial.csv')
        result=ingest(self.db,self.inputs/'late.csv')
        self.assertEqual((result['new_events'],result['duplicate_rows']),(1,1))
        summary=report(self.db)
        self.assertEqual((summary['event_count'],summary['total_energy_wh']),(6,910))
        self.assertEqual(summary['hours'][0]['energy_wh'],420)
        self.assertEqual(summary['hours'][1]['day_cumulative_wh'],510)

    def test_conflict_rejects_whole_batch_including_new_event(self):
        ingest(self.db,self.inputs/'initial.csv')
        before=report(self.db)
        with self.assertRaisesRegex(InputError,'EVENT_CONFLICT'):
            ingest(self.db,self.inputs/'conflict.csv')
        self.assertEqual(report(self.db),before)

    def test_intra_package_conflict_has_no_facts(self):
        path=self.file([('E1','S1','M1','2026-10-26T00:00:00Z','1'),
                        ('E1','S1','M1','2026-10-26T00:00:00Z','2')])
        with self.assertRaisesRegex(InputError,'EVENT_CONFLICT'):
            ingest(self.db,path)
        self.assertEqual(report(self.db)['event_count'],0)
        self.assertEqual(report(self.db)['batch_count'],0)

    def test_exact_contract_rejects_bad_values(self):
        cases=[('E1','S1','M1','2026-02-30T00:00:00Z','1'),
               ('E1','S1','M1','0000-01-01T00:00:00Z','1'),
               ('E1','S1','M1','2026-10-26T00:00:00+03:00','1'),
               ('E1','S1','M1','2026-10-26T00:00:00Z','-1'),
               ('E1','S1','M1','2026-10-26T00:00:00Z','1.5'),
               ('E1','S1','M1','2026-10-26T00:00:00Z','01'),
               ('E1','S1','M1','2026-10-26T00:00:00Z','1000000001'),
               ('','S1','M1','2026-10-26T00:00:00Z','1')]
        for row in cases:
            with self.subTest(row=row), self.assertRaisesRegex(InputError,'ROW_CONTRACT'):
                ingest(self.db,self.file([row]))
        self.assertEqual(report(self.db)['event_count'],0)

    def test_header_width_and_empty_file(self):
        for path in (self.file([],name='empty.csv'),
                     self.file([('E1',)],name='width.csv'),
                     self.file([],name='header.csv',header=list(reversed(HEADER)))):
            with self.subTest(path=path.name),self.assertRaises(InputError):
                ingest(self.db,path)
        self.assertFalse(self.db.exists())

    def test_foreign_database_is_not_modified(self):
        with duckdb.connect(str(self.db)) as db:
            db.execute('CREATE TABLE other (n INTEGER)')
            db.execute('INSERT INTO other VALUES (42)')
        with self.assertRaisesRegex(InputError,'DATABASE_IDENTITY'):
            ingest(self.db,self.inputs/'initial.csv')
        with duckdb.connect(str(self.db)) as db:
            self.assertEqual(db.execute('SELECT * FROM other').fetchall(),[(42,)])

    def test_parquet_roundtrip_and_no_overwrite(self):
        ingest(self.db,self.inputs/'initial.csv')
        target=self.root/'hours.parquet'
        result=export_parquet(self.db,target)
        self.assertEqual(len(result['sha256']),64)
        with duckdb.connect() as db:
            self.assertEqual(db.execute('SELECT count(*),sum(energy_wh) FROM read_parquet(?)',
                                        [str(target)]).fetchone(),(3,840))
        original=target.read_bytes()
        with self.assertRaisesRegex(InputError,'OUTPUT_EXISTS'):
            export_parquet(self.db,target)
        self.assertEqual(target.read_bytes(),original)

    def test_snapshot_exports_remain_unchanged_after_late_ingestion(self):
        ingest(self.db,self.inputs/'initial.csv')
        target=self.root/'before.parquet'
        export_parquet(self.db,target)
        before=target.read_bytes()
        ingest(self.db,self.inputs/'late.csv')
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual(report(self.db)['total_energy_wh'],910)

    def test_utc_day_resets_cumulative_sum(self):
        path=self.file([('E1','S1','M1','2026-10-26T23:59:59Z','5'),
                        ('E2','S1','M1','2026-10-27T00:00:00Z','7')])
        ingest(self.db,path)
        self.assertEqual([r['day_cumulative_wh'] for r in report(self.db)['hours']],[5,7])

    def test_cli_safe_failure_and_json(self):
        completed=subprocess.run([sys.executable,'-m','meter_rollups','ingest','--db',str(self.db),
                                  '--input',str(self.inputs/'initial.csv')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['new_events'],5)
        rejected=subprocess.run([sys.executable,'-m','meter_rollups','ingest','--db',str(self.db),
                                 '--input',str(self.inputs/'conflict.csv')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(rejected.returncode,2)
        self.assertEqual(rejected.stderr.strip(),'EVENT_CONFLICT')
        self.assertNotIn(str(self.root),rejected.stderr)

    def test_generator_refuses_existing_output(self):
        with self.assertRaisesRegex(InputError,'OUTPUT_EXISTS'):
            generate(self.inputs)

    def test_missing_report_does_not_create_database(self):
        with self.assertRaisesRegex(InputError,'DATABASE_MISSING'):
            report(self.db)
        self.assertFalse(self.db.exists())


if __name__=='__main__':
    unittest.main()
