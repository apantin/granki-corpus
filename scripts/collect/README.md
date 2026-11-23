# Публичные сборщики

`fetch.py` — HTTP-кэш, robots.txt, задержка не меньше трёх секунд и Crawl-delay, ограничение размера ответа. Попадание в кэш не вызывает HTTP-запросов.

`articles.py` — поиск кандидатов «Теплицы» и «Завтра», стабильный порядок public-v1, предварительная проверка CC-маркера, объёма, русского текста, переводов/перепечаток и наличия автора. Общая очистка передаётся из открытого пакета granki-bench; собственная реализация очистки не дублируется.

Минимальное использование после добавления `scripts/collect` в путь импорта:

```python
from pathlib import Path
from articles import discover_urls, extract_candidate
from fetch import Fetcher
from bench.cleaning import html_article, text_features

fetch = Fetcher(Path('work/cache'), delay=3)
urls, counters = discover_urls(fetch, 'te-st', maps=1)
for url in urls[:50]:
    candidate, reason = extract_candidate(
        fetch.get(url), url, 'te-st',
        cleaner=html_article, features=text_features,
    )
```

Кандидат не публикуется автоматически: CC-маркер в подвале не исключает особых прав конкретной статьи. До публикации нужны проверка происхождения, атрибуции, исключений лицензии, качества извлечения и запись обеих версий с хешами. Деление, квоты и назначение файлов — ответственность вызывающего кода; этот модуль не читает внешние реестры и не назначает проверочные части.

Сборщики используют зависимости извлечения пакета granki-bench (`data` extra). Тесты кэша и границ кандидатов: `python -m unittest discover -s scripts -p 'test_*.py'`.
