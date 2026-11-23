import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'collect'))
from articles import discover_urls,extract_candidate,SOURCES
from fetch import Fetcher


class CollectorTest(unittest.TestCase):
    def test_supplied_urls_are_host_scoped_deduplicated_and_deterministic(self):
        values=['https://zavtra.ru/blogs/b','https://else.invalid/blogs/a','https://zavtra.ru/blogs/a','https://zavtra.ru/blogs/b']
        left,_=discover_urls(None,'zavtra',supplied_urls=values)
        right,_=discover_urls(None,'zavtra',supplied_urls=reversed(values))
        self.assertEqual(left,right);self.assertEqual(len(left),2)
        self.assertTrue(all(v.startswith('https://zavtra.ru/') for v in left))

    def test_license_marker_and_reprints_do_not_pass_as_accepted_candidates(self):
        def cleaner(payload,url):return SimpleNamespace(raw='Текст',norm='Текст'),{'author':'Тестовый Автор'}
        features=lambda text:{'words':200,'cyrillic':1}
        self.assertEqual(extract_candidate(b'no marker','https://zavtra.ru/blogs/a','zavtra',cleaner=cleaner,features=features),(None,'no_license'))
        payload=SOURCES['zavtra']['license_pattern'].encode()
        accepted,reason=extract_candidate(payload,'https://zavtra.ru/blogs/a','zavtra',cleaner=cleaner,features=features)
        self.assertIsNone(reason);self.assertEqual(accepted[1]['author'],'Тестовый Автор')
        def reprint(payload,url):return SimpleNamespace(raw='Перепечатано',norm='Перепечатано'),{'author':'Тестовый Автор'}
        self.assertEqual(extract_candidate(payload,'https://zavtra.ru/blogs/a','zavtra',cleaner=reprint,features=features),(None,'translation_or_reprint'))

    def test_cached_response_never_issues_network_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            url='https://example.org/article';payload=b'cached html'
            path=Path(folder)/(hashlib.sha256(url.encode()).hexdigest()+'.html');path.write_bytes(payload)
            with patch('fetch.urlopen',side_effect=AssertionError('network request')):
                fetch=Fetcher(Path(folder));self.assertEqual(fetch.get(url),payload);self.assertEqual(fetch.bytes,0)


if __name__=='__main__':unittest.main()
