#!/usr/bin/env python3
"""Проверка перед коммитом в корпус.

- файлы только в разрешённых местах;
- у каждого текста в texts/ есть запись в manifest.csv, и хеш совпадает;
- у каждой записи манифеста есть лицензия и источник;
- в служебных файлах нет локальных путей и адресов почты.

Включить: git config core.hooksPath .githooks
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIRS = {'texts', 'scripts', '.githooks'}
ALLOWED_FILES = {'README.md', 'LICENSE.md', 'manifest.csv', '.gitignore'}
FIELDS = ['path', 'source_url', 'license', 'attribution', 'author', 'genre', 'period', 'words', 'sha256', 'collected']
PRIVATE = re.compile(r'/home/[a-z]|/Users/[A-Za-z]|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|ru|me|org|net)\b')


def git(*args: str) -> bytes:
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, check=True).stdout


def main() -> int:
    problems = []
    staged = [p for p in git('diff', '--cached', '--name-only', '--diff-filter=ACMR').decode().splitlines() if p]
    manifest_rows = list(csv.DictReader(io.StringIO(git('show', ':manifest.csv').decode('utf-8'))))
    header = git('show', ':manifest.csv').decode('utf-8').splitlines()[0].split(',')
    if header != FIELDS:
        problems.append(f'manifest.csv: колонки должны быть {",".join(FIELDS)}')
    by_path = {row['path']: row for row in manifest_rows}
    for row in manifest_rows:
        if not row.get('license') or not row.get('source_url'):
            problems.append(f'manifest.csv: у {row.get("path")} нет лицензии или источника')
    for path in staged:
        top = path.split('/', 1)[0]
        if '/' in path and top not in ALLOWED_DIRS or '/' not in path and path not in ALLOWED_FILES:
            problems.append(f'{path}: вне разрешённых путей')
            continue
        data = git('show', f':{path}')
        if path.startswith('texts/'):
            row = by_path.get(path)
            if row is None:
                problems.append(f'{path}: нет записи в manifest.csv')
            elif hashlib.sha256(data).hexdigest() != row['sha256']:
                problems.append(f'{path}: sha256 не совпадает с manifest.csv')
        elif path != 'scripts/check_commit.py':
            found = PRIVATE.search(data.decode('utf-8', 'ignore'))
            if found:
                problems.append(f'{path}: похоже на локальный путь или почту: {found.group(0)}')
    tracked = {p for p in git('ls-files', 'texts').decode().splitlines() if p} | {p for p in staged if p.startswith('texts/')}
    for path in sorted(set(by_path) - tracked):
        problems.append(f'manifest.csv: {path} — нет такого файла')
    for p in problems:
        print(f'check_commit: {p}', file=sys.stderr)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
