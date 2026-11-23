"""Сбор кандидатов двух CC-источников; деление и допуск в корпус задаёт вызывающий код."""
from __future__ import annotations
import hashlib
import re
from collections import Counter
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

SOURCES={
    'te-st':dict(site='https://te-st.org',license='CC-BY-SA-4.0',license_pattern='creativecommons.org/licenses/by-sa/4.0'),
    'zavtra':dict(site='https://zavtra.ru',license='CC-BY-4.0',license_pattern='creativecommons.org/licenses/by/4.0')}
NS={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}


def discover_urls(fetch,source,*,maps=8,supplied_urls=None):
    """Детерминированный порядок public-v1, кэш/robots/темп обеспечивает fetch.get."""
    site=SOURCES[source]['site'];urls=[];stats=Counter()
    if supplied_urls is not None:
        urls=[url for url in supplied_urls if urlsplit(url).hostname==urlsplit(site).hostname]
    elif source=='te-st':
        root=ET.fromstring(fetch.get(site+'/sitemap_index.xml'))
        indexes=[node.text for node in root.findall('s:sitemap/s:loc',NS) if 'post-sitemap' in node.text]
        indexes.sort(key=lambda value:hashlib.sha256(('public-v1'+value).encode()).digest())
        for url in indexes[:maps]:
            try:
                tree=ET.fromstring(fetch.get(url))
                urls.extend(node.text for node in tree.findall('s:url/s:loc',NS) if re.search(r'/20(?:0\d|1\d|2[0-2])/',node.text))
            except Exception as error:stats['map_error:'+type(error).__name__]+=1
    else:
        for page in range(1,maps+1):
            payload=fetch.get(site+'/blogs'+(f'?page={page}' if page>1 else '')).decode('utf-8','replace')
            urls.extend(site+path for path in re.findall(r'href="(/blogs/[^"?#/]+)"',payload))
    return sorted(set(urls),key=lambda value:hashlib.sha256(('public-v1'+value).encode()).digest()),stats


def extract_candidate(payload,url,source,*,cleaner,features):
    """Проверки public-v1; cleaner/features — общая реализация из granki-bench.

    Найденный CC-маркер не доказывает отсутствия исключения у конкретной статьи.
    Возвращается кандидат, не готовая запись публикационного манифеста.
    """
    spec=SOURCES[source]
    if urlsplit(url).hostname!=urlsplit(spec['site']).hostname:return None,'wrong_source_host'
    if spec['license_pattern'] not in payload.decode('utf-8','replace'):return None,'no_license'
    clean,meta=cleaner(payload,url);meta=dict(meta);ft=features(clean.norm)
    if ft['words']<150 or ft['cyrillic']<.65:return None,'preliminary_filter'
    if re.search(r'(?i)(перевод\s*[:—]|перев[её]л[а]?\s*[:—]|источник\s*:\s*https?://|перепечатано)',clean.raw):return None,'translation_or_reprint'
    author=meta.get('author') or ''
    if not author and source=='zavtra':
        from lxml import html
        tree=html.fromstring(payload)
        for node in tree.xpath('//a[contains(@href,"/blogs/authors/")]'):
            value=' '.join(node.text_content().split())
            if len(value.split()) in (2,3) and re.search('[А-ЯЁ]',value):author=value;break
    if not author:return None,'no_author'
    meta['author']=author
    return (clean,meta),None
