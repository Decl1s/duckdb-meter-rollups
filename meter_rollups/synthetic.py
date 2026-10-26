"""Я генерирую короткую воспроизводимую историю без реальных измерений."""

import csv
from pathlib import Path

from .store import HEADER, InputError


def generate(output: Path) -> dict:
    try:
        output.mkdir()
    except FileExistsError:
        raise InputError('OUTPUT_EXISTS') from None
    rows = [
        ('E001','SITE_A','M01','2026-10-26T10:05:00Z','100'),
        ('E002','SITE_A','M01','2026-10-26T10:30:00Z','200'),
        ('E003','SITE_A','M02','2026-10-26T10:40:00Z','50'),
        ('E004','SITE_B','M03','2026-10-26T10:15:00Z','400'),
        ('E005','SITE_A','M01','2026-10-26T11:10:00Z','90'),
    ]
    batches = {'initial.csv':rows+[rows[0]],
               'late.csv':[('E006','SITE_A','M01','2026-10-26T10:50:00Z','70'),rows[1]],
               'conflict.csv':[('E007','SITE_A','M01','2026-10-26T10:55:00Z','30'),
                               (*rows[1][:4],'201')]}
    for name, data in batches.items():
        with (output/name).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n')
            writer.writerow(HEADER)
            writer.writerows(data)
    return {'generated_files':3,'initial_rows':6,'late_rows':2,'conflict_rows':2}
