"""Я оставляю CLI тонким: параметры здесь, SQL и транзакции — в store."""

import argparse
import json
from pathlib import Path
import sys

from .store import InputError, ingest, report, export_parquet
from .synthetic import generate


def main() -> int:
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Почасовое энергопотребление на DuckDB')
    commands=parser.add_subparsers(dest='command',required=True)
    g=commands.add_parser('generate',help='Создать новый synthetic input каталог')
    g.add_argument('--output',type=Path,required=True)
    i=commands.add_parser('ingest',help='Принять полный CSV с защитой от конфликтов')
    i.add_argument('--db',type=Path,required=True)
    i.add_argument('--input',type=Path,required=True)
    r=commands.add_parser('report',help='Прочитать SQL витрину')
    r.add_argument('--db',type=Path,required=True)
    e=commands.add_parser('export',help='Сохранить новый Parquet файл')
    e.add_argument('--db',type=Path,required=True)
    e.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='generate':
            result=generate(args.output)
        elif args.command=='ingest':
            result=ingest(args.db,args.input)
        elif args.command=='report':
            result=report(args.db)
        else:
            result=export_parquet(args.db,args.output)
    except (InputError,OSError):
        # Только известный безопасный код, без traceback/DSN/CSV payload.
        error=sys.exception()
        print(str(error) if isinstance(error,InputError) else 'FILESYSTEM_ERROR',file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
