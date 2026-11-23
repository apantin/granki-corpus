#!/usr/bin/env python3
"""Проверка staged-снимка корпуса: формат, лицензии, обе версии текстов и пар."""
from __future__ import annotations
import csv
import hashlib
import io
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIRS = {'texts', 'pairs', 'scripts', '.githooks'}
ALLOWED_FILES = {'README.md', 'LICENSE.md', 'manifest.csv', '.gitignore'}
FIELDS = ('path source_url license attribution author genre period words sha256 collected '
          'site_terms source_id subgenre period_ai clean_version raw_path raw_sha256 split').split()
PAIR_FIELDS = ('pair_id source kind group unit origin_id primary purpose neutrality_reason '
               'worse_path worse_raw_path worse_sha256 worse_raw_sha256 '
               'better_path better_raw_path better_sha256 better_raw_sha256 '
               'split license attribution provenance decided_by period_ai length_ratio label').split()
LICENSES = {'MIT', 'CC0-1.0', 'public-domain', 'CC-BY-3.0', 'CC-BY-4.0',
            'CC-BY-SA-2.5', 'CC-BY-SA-3.0', 'CC-BY-SA-4.0'}
PRIVATE = re.compile(r'/home/[a-z]|/Users/[A-Za-z]|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|ru|me|org|net)\b')


def git(*args: str) -> bytes:
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, check=True).stdout


def validate(blobs: dict[str, bytes]) -> list[str]:
    problems = []
    registered: dict[str, str] = {}
    def table(path, fields):
        if path not in blobs:
            if path == 'manifest.csv':
                problems.append('manifest.csv: отсутствует')
            return []
        reader = csv.DictReader(io.StringIO(blobs[path].decode('utf-8')))
        if reader.fieldnames != fields:
            problems.append(f'{path}: неверные колонки')
            return []
        return list(reader)

    def file(path, sha, prefix):
        parts = PurePosixPath(path).parts
        if not path or not path.startswith(prefix + '/') or '..' in parts or not path.endswith('.md'):
            problems.append('Неверный путь текста в манифесте')
        elif path not in blobs or hashlib.sha256(blobs[path]).hexdigest() != sha:
            problems.append(f'{path}: файл отсутствует или sha256 не совпадает')
        if path in registered and registered[path] != sha:
            problems.append(f'{path}: противоречивые хеши')
        registered[path] = sha

    seen = set()
    for row in table('manifest.csv', FIELDS):
        if any(not row.get(f) for f in FIELDS):
            problems.append('manifest.csv: пустое обязательное поле')
        if row.get('license') not in LICENSES or not row.get('source_url', '').startswith(('https://', 'http://')):
            problems.append('manifest.csv: нет открытой лицензии или URL источника')
        if row.get('split') not in {'scouting', 'confirmation'}:
            problems.append('manifest.csv: неверная публичная часть')
        if row['path'] in seen:
            problems.append('manifest.csv: повтор пути')
        seen.add(row['path'])
        file(row['path'], row['sha256'], 'texts')
        file(row['raw_path'], row['raw_sha256'], 'texts')
    seen.clear()
    for row in table('pairs/manifest.csv', PAIR_FIELDS):
        if any(not row.get(f) for f in set(PAIR_FIELDS) - {'neutrality_reason', 'label'}):
            problems.append('pairs/manifest.csv: пустое обязательное поле')
        if row.get('license') not in LICENSES or row.get('split') not in {'scouting', 'confirmation'}:
            problems.append('pairs/manifest.csv: неверная лицензия или часть')
        if row['purpose'] == 'neutral-control' and not row['neutrality_reason']:
            problems.append('pairs/manifest.csv: нет основания нейтральности')
        if row['purpose']=='diagnostic-only' and row['primary']!='no':
            problems.append('pairs/manifest.csv: диагностическая пара не может быть основной')
        if row.get('label')=='construction-mixed-axes-legacy' and row['purpose']!='diagnostic-only':
            problems.append('pairs/manifest.csv: смешанная legacy-порча не допускается как контроль качества')
        if row['pair_id'] in seen:
            problems.append('pairs/manifest.csv: повтор ID')
        seen.add(row['pair_id'])
        for side in ('worse', 'better'):
            file(row[side + '_path'], row[side + '_sha256'], 'pairs')
            file(row[side + '_raw_path'], row[side + '_raw_sha256'], 'pairs')
    for path, data in blobs.items():
        top = path.split('/', 1)[0]
        if ('/' in path and top not in ALLOWED_DIRS) or ('/' not in path and path not in ALLOWED_FILES):
            problems.append(f'{path}: вне разрешённых путей')
        if top in {'texts', 'pairs'} and path != 'pairs/manifest.csv' and path not in registered:
            problems.append(f'{path}: файл без записи в манифесте')
        if len(data) > 5 * 1024 * 1024:
            problems.append(f'{path}: больше 5 МБ')
        if path not in {'scripts/check_commit.py', 'scripts/test_check_commit.py'}:
            if PRIVATE.search(data.decode('utf-8', 'ignore')):
                problems.append(f'{path}: локальный путь или почта')
    return problems


def main() -> int:
    blobs = {}
    for entry in git('ls-files', '--stage', '-z').decode().split('\0'):
        if not entry:
            continue
        meta, path = entry.split('\t', 1)
        mode, sha, stage = meta.split()
        if mode not in {'100644', '100755'} or stage != '0':
            print(f'check_commit: {path}: недопустимый тип файла или конфликт', file=sys.stderr)
            return 1
        blobs[path] = git('cat-file', 'blob', sha)
    problems = validate(blobs)
    for problem in problems:
        print(f'check_commit: {problem}', file=sys.stderr)
    return int(bool(problems))


if __name__ == '__main__':
    sys.exit(main())
