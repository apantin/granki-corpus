"""HTTP-кэш с robots.txt, задержкой и ограничением размера ответа."""
from __future__ import annotations
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

AGENT = 'granki-corpus-research/0.1'


class Fetcher:
    def __init__(self, cache: Path, *, delay: float = 3, max_size: int = 8*1024*1024):
        self.cache, self.delay, self.max_size = cache, delay, max_size
        self.cache.mkdir(parents=True, exist_ok=True)
        self.robots = {}
        self.last = {}
        self.bytes = 0

    def _download(self, url):
        host = urlsplit(url).netloc
        pause = max(self.delay, self.robots[host].crawl_delay(AGENT) or self.robots[host].crawl_delay('*') or 0) if host in self.robots else self.delay
        time.sleep(max(0, pause - (time.monotonic() - self.last.get(host, 0))))
        try:
            with urlopen(Request(url, headers={'User-Agent': AGENT}), timeout=25) as response:
                data = response.read(self.max_size + 1)
            if len(data) > self.max_size:
                raise ValueError('Ответ превышает предел размера')
            self.bytes += len(data)
            return data
        finally:
            self.last[host] = time.monotonic()

    def get(self, url):
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'}:
            raise ValueError('Только HTTP(S)')
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache / (key + '.html')
        if path.exists():
            return path.read_bytes()
        if parsed.netloc not in self.robots:
            robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
            # Ошибка получения robots закрывает сбор; отсутствие правил не предполагается.
            raw = self._download(robots_url)
            parser = RobotFileParser(robots_url)
            parser.parse(raw.decode('utf-8', 'replace').splitlines())
            self.robots[parsed.netloc] = parser
            (self.cache / (hashlib.sha256(robots_url.encode()).hexdigest() + '.robots')).write_bytes(raw)
        if not self.robots[parsed.netloc].can_fetch(AGENT, url):
            raise PermissionError('robots.txt запрещает запрос')
        data = self._download(url)
        path.write_bytes(data)
        with (self.cache / 'log.jsonl').open('a') as f:
            f.write(json.dumps({'url': url, 'collected': datetime.now(timezone.utc).isoformat(),
                                'path': path.name, 'sha256': hashlib.sha256(data).hexdigest()}) + '\n')
        return data
