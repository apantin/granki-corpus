import csv
import hashlib
import io
import unittest
from check_commit import FIELDS, PAIR_FIELDS, validate


def csv_bytes(fields, records):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    return out.getvalue().encode()


class CheckTest(unittest.TestCase):
    def test_texts_also_checked_for_private_patterns(self):
        data=b'contact: author@example.com'
        row=dict.fromkeys(FIELDS,'value')
        row.update(path='texts/t.md',raw_path='texts/t.raw.md',source_url='https://example.org/article',
                   license='CC-BY-4.0',split='scouting',sha256=hashlib.sha256(data).hexdigest(),raw_sha256=hashlib.sha256(data).hexdigest())
        self.assertTrue(validate({'manifest.csv':csv_bytes(FIELDS,[row]),row['path']:data,row['raw_path']:data}))
    def test_missing_new_fields_and_unregistered(self):
        self.assertTrue(validate({'manifest.csv': b'path,license\n'}))
        self.assertTrue(validate({'manifest.csv': csv_bytes(FIELDS, []), 'texts/x.md': b'x'}))

    def test_both_text_versions_and_deletion(self):
        content = 'Текст'.encode()
        row = dict.fromkeys(FIELDS, 'value')
        row.update(path='texts/t.md', raw_path='texts/t.raw.md', source_url='https://example.org/article',
                   license='CC-BY-4.0', split='scouting', sha256=hashlib.sha256(content).hexdigest(),
                   raw_sha256=hashlib.sha256(content).hexdigest())
        blobs = {'manifest.csv': csv_bytes(FIELDS, [row]), row['path']: content, row['raw_path']: content}
        self.assertEqual(validate(blobs), [])
        del blobs[row['raw_path']]
        self.assertTrue(validate(blobs))
        for field in ('site_terms', 'clean_version', 'raw_sha256'):
            bad = row | {field: ''}
            self.assertTrue(validate(blobs | {'manifest.csv': csv_bytes(FIELDS, [bad])}))

    def test_pairs_require_license_hash_decision(self):
        content = b'x'
        pair = dict.fromkeys(PAIR_FIELDS, 'value')
        pair.update(license='CC-BY-4.0', split='scouting')
        blobs = {'manifest.csv': csv_bytes(FIELDS, [])}
        for side in ('worse', 'better'):
            for raw in ('', '_raw'):
                pair[f'{side}{raw}_path'] = f'pairs/source/{side}{raw}.md'
                pair[f'{side}{raw}_sha256'] = hashlib.sha256(content).hexdigest()
                blobs[pair[f'{side}{raw}_path']] = content
        blobs['pairs/manifest.csv'] = csv_bytes(PAIR_FIELDS, [pair])
        self.assertEqual(validate(blobs), [])
        for field in ('license', 'worse_sha256', 'decided_by', 'attribution'):
            bad = pair | {field: ''}
            self.assertTrue(validate(blobs | {'pairs/manifest.csv': csv_bytes(PAIR_FIELDS, [bad])}))

    def test_diagnostic_legacy_cannot_be_primary_or_quality(self):
        content=b'x';pair=dict.fromkeys(PAIR_FIELDS,'value')
        pair.update(license='CC-BY-4.0',split='scouting',purpose='diagnostic-only',primary='no',label='construction-mixed-axes-legacy')
        blobs={'manifest.csv':csv_bytes(FIELDS,[])}
        for side in ('worse','better'):
            for raw in ('','_raw'):
                path=f'pairs/source/{side}{raw}.md';pair[f'{side}{raw}_path']=path
                pair[f'{side}{raw}_sha256']=hashlib.sha256(content).hexdigest();blobs[path]=content
        self.assertEqual(validate(blobs|{'pairs/manifest.csv':csv_bytes(PAIR_FIELDS,[pair])}),[])
        for changed in [dict(primary='yes'),dict(purpose='quality')]:
            self.assertTrue(validate(blobs|{'pairs/manifest.csv':csv_bytes(PAIR_FIELDS,[pair|changed])}))


if __name__ == '__main__':
    unittest.main()
