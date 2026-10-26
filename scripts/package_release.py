"""Я собираю ZIP только из явного allowlist и отклоняю приватные данные."""

import hashlib
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='duckdb-meter-rollups-0.1.0'


def package():
    names=(ROOT/'PUBLIC_FILES.txt').read_text().splitlines()
    if names!=sorted(set(names)):
        raise ValueError('Я ожидаю отсортированный уникальный список исходников')
    contents={}
    for name in names:
        path=ROOT/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.is_file():
            raise ValueError('В allowlist нужен обычный относительный файл')
        data=path.read_bytes()
        text=data.decode('utf-8')
        private_pattern=r'/home/|/Users/|[A-Z]:\\Users\\|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_|-----BEGIN .*PRIVATE KEY-----'
        # Сам шаблон сканирования содержит сигнатуры; я исключаю только этот literal.
        scanned=text.replace(private_pattern,'') if name=='scripts/package_release.py' else text
        if re.search(private_pattern,scanned):
            raise ValueError('В исходниках обнаружена приватная сигнатура: '+name)
        contents[name]=data
    folder=ROOT/'artifacts'
    folder.mkdir(exist_ok=True)
    archive=folder/(NAME+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
        for name,data in contents.items():
            info=zipfile.ZipInfo(NAME+'/'+name,date_time=(2026,10,26,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            out.writestr(info,data)
    with zipfile.ZipFile(archive) as check:
        if set(check.namelist())!={NAME+'/'+n for n in names}:
            raise ValueError('Состав ZIP отличается от allowlist')
        for name,data in contents.items():
            if check.read(NAME+'/'+name)!=data:
                raise ValueError('Байты ZIP отличаются от исходников')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder/'SHA256SUMS').write_text(digest+'  '+archive.name+'\n',encoding='utf-8')
    return archive,len(names),digest


if __name__=='__main__':
    import sys
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    path,count,digest=package()
    print(f'ZIP: {count} исходников; SHA256 {digest}')
