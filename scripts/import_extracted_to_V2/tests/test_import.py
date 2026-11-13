"""Изолированные проверки; никаких обращений к Drive, БД или данным пользователя."""
import ast
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core as c
p = c.p


class ParserTests(unittest.TestCase):
    def test_complete_text(self):
        text = '# Глава\r\n\r\n1.1.1. Текст\r\n\r\n## Новый раздел\r\n1.1.2. Конец\r\n'
        blocks = c.segment(text, '1.1')
        self.assertEqual(''.join(b['text'] for b in blocks), text)
        self.assertEqual([b['clause'] for b in blocks if b['clause']], ['1.1.1', '1.1.2'])
        self.assertEqual(sum(b['kind'] == 'structural_context' for b in blocks), 2)

    def test_formula_and_table_unchanged(self):
        text = '1.1.1. Текст\n\n$$\nx = a + b\n\n1.1.99. Это внутри формулы\n$$\n\n|a|b|\n|-|-|\n|1|2|\n'
        blocks = c.segment(text, '1.1')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['text'], text)

    def test_fence(self):
        text = '1.1.1. Текст\n\n```text\n1.1.99. Код\n## Не заголовок\n```\n'
        self.assertEqual(len(c.segment(text, '1.1')), 1)

    def test_heading_table_stays_with_clause(self):
        text = '1.1.1. Текст\n\n### Таблица 1.1.1\n|a|b|\n|-|-|\n|1|2|\n'
        self.assertEqual(len(c.segment(text, '1.1')), 1)

    def test_duplicate_clause(self):
        with self.assertRaises(ValueError):
            c.segment('1.1.1. a\n1.1.1. b\n', '1.1')

    def test_wrong_chapter(self):
        with self.assertRaises(ValueError):
            c.segment('1.2.1. a\n', '1.1')

    def test_unclosed_math(self):
        with self.assertRaises(ValueError):
            c.segment('1.1.1. $$x\n', '1.1')

    def test_unclosed_fence(self):
        with self.assertRaises(ValueError):
            c.segment('1.1.1. a\n```\na', '1.1')

    def test_escaped_dollar(self):
        self.assertEqual(len(c.segment('1.1.1. Цена \\$5\n', '1.1')), 1)

    def test_bracket_math(self):
        text = '1.1.1. a\n\\[\nx\n\n1.1.99. inside\n\\]\n'
        self.assertEqual(len(c.segment(text, '1.1')), 1)

    def test_split_at_paragraphs_only(self):
        text = 'a' * 30000 + '\n\n' + 'b' * 30000
        pieces = c.split_safe(text)
        self.assertEqual(len(pieces), 2)
        self.assertEqual(''.join(pieces), text)

    def test_no_arbitrary_atomic_cut(self):
        with self.assertRaises(ValueError):
            c.split_safe('a' * 60001)

    def test_no_cut_inside_math(self):
        with self.assertRaises(ValueError):
            c.split_safe('$$\n' + ('a' * 30000) + '\n\n' + ('b' * 30000) + '\n$$')

    def test_no_cut_inside_table(self):
        with self.assertRaises(ValueError):
            c.split_safe('|a|b|\n' + '|x|' * 21000)

    def test_python39_syntax(self):
        for path in Path(c.__file__).parent.glob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 9))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.md = self.root / 'data/extracted'
        self.v2 = self.root / 'V2/data/chunked'
        self.out = self.root / 'data/chunked_manual'
        self.merged = self.root / 'V2/data/chunked_merged_manual'
        self.md.mkdir(parents=True)
        self.v2.mkdir(parents=True)
        self.raw = b'\xef\xbb\xbf' + ('# ПУЭ\r\n\r\n1.1.1. Формула $x=a+b$.\r\n\r\n|a|b|\r\n|-|-|\r\n|1|2|\r\n\r\n![рис](image/a.png)\r\n\r\n## Раздел\r\n1.1.2. Конец.\r\n').encode('utf-8')
        (self.md / '1.1.md').write_bytes(self.raw)
        (self.md / 'image').mkdir()
        (self.md / 'image/a.png').write_bytes(b'EXACT_ASSET_BYTES')
        def row(doc, clause, number):
            return {'id': 'v2_old_' + str(number), 'content': clause + '. Старый текст',
                    'metadata': {'source_file': doc, 'Document': doc, 'Scope': 'pue', 'Clause': clause,
                        'part_index': 1, 'part_count': 1, 'related_chunk_ids': ['v2_old_' + str(number)]}}
        self.refs = [row('raw/1.1.docx', '1.1.1', 1), row('raw/1.1.docx', '1.1.2', 2), row('raw/2.1.docx', '2.1.1', 3)]
        self.write_refs()

    def tearDown(self):
        self.temp.cleanup()

    def write_refs(self):
        (self.v2 / 'ref.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in self.refs), encoding='utf-8')

    def prepare(self):
        return c.prepare(self.md, self.v2, self.out, ['1.1'])

    def test_preserve_bom_crlf_formula_table_asset(self):
        self.prepare()
        result = c.check(self.out)
        self.assertTrue(result['markdown_bytes_preserved'])
        self.assertEqual((self.out / '_audit/markdown/1.1.md').read_bytes(), self.raw)
        self.assertEqual((self.md / '1.1.md').read_bytes(), self.raw)
        self.assertTrue(any(f.read_bytes() == b'EXACT_ASSET_BYTES' for f in (self.out / 'assets').glob('*')))

    def test_offsets_are_honest(self):
        self.prepare()
        for item in p.read_rows(self.out):
            m = item['row']['metadata']
            self.assertIsNone(m['source_char_start'])
            self.assertIsNone(m['document_version_sha256'])
            self.assertEqual(m['manual_markdown_sha256'], p.sha(self.raw))
            self.assertEqual(m['origin_provenance']['kind'], 'manual_markdown')

    def test_missing_markdown(self):
        (self.md / '1.1.md').unlink()
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.out.exists())

    def test_missing_asset(self):
        (self.md / 'image/a.png').unlink()
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.out.exists())

    def test_path_escape(self):
        (self.md / '1.1.md').write_text('1.1.1. ![x](../../outside.png)\n1.1.2. b\n', encoding='utf-8')
        (self.root / 'outside.png').write_bytes(b'outside')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.out.exists())

    def test_symlink_escape(self):
        outside = self.root / 'outside.png'
        outside.write_bytes(b'outside')
        (self.md / 'image/a.png').unlink()
        (self.md / 'image/a.png').symlink_to(outside)
        with self.assertRaises(ValueError): self.prepare()

    def test_unsupported_scheme(self):
        (self.md / '1.1.md').write_text('1.1.1. ![x](file:///tmp/a.png)\n1.1.2. b\n', encoding='utf-8')
        with self.assertRaises(ValueError): self.prepare()

    def test_missing_clause(self):
        (self.md / '1.1.md').write_text('1.1.1. a\n', encoding='utf-8')
        with self.assertRaises(ValueError): self.prepare()

    def test_extra_clause(self):
        (self.md / '1.1.md').write_bytes(self.raw + b'1.1.3. extra\n')
        with self.assertRaises(ValueError): self.prepare()

    def test_ambiguous_document(self):
        r = copy.deepcopy(self.refs[0]); r['id'] = 'ambiguous'; r['metadata']['source_file'] = 'other/1.1.docx'
        self.refs.append(r); self.write_refs()
        with self.assertRaises(ValueError): self.prepare()

    def test_ambiguous_scope(self):
        r = copy.deepcopy(self.refs[0]); r['id'] = 'ambiguous'; r['metadata']['Scope'] = 'another'
        self.refs.append(r); self.write_refs()
        with self.assertRaises(ValueError): self.prepare()

    def test_output_exists_no_overwrite(self):
        self.prepare()
        before = (self.out / '_audit/report.json').read_bytes()
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(before, (self.out / '_audit/report.json').read_bytes())

    def test_output_overlap(self):
        with self.assertRaises(ValueError): c.prepare(self.md, self.v2, self.md / 'out', ['1.1'])

    def test_plan_has_no_active_chunks(self):
        self.prepare()
        plan = self.root / 'plan'
        report = c.merge(self.out, self.v2, plan)
        self.assertEqual(report['chunks'], 0)
        self.assertFalse(list(plan.glob('*.jsonl')))
        self.assertEqual(c.check(plan)['chunks'], 0)

    def test_apply_requires_explicit_priority(self):
        self.prepare()
        with self.assertRaises(ValueError): c.merge(self.out, self.v2, self.merged, True)

    def test_unknown_preferred_chapter(self):
        self.prepare()
        with self.assertRaises(ValueError): c.merge(self.out, self.v2, self.merged, True, ['1.2'])

    def test_v2_changed_refused(self):
        self.prepare()
        self.refs[0]['content'] += ' changed'; self.write_refs()
        with self.assertRaises(ValueError): c.merge(self.out, self.v2, self.merged, True, ['1.1'])
        self.assertFalse(self.merged.exists())

    def test_whole_document_merge(self):
        self.prepare()
        before_md, before_v2 = (self.md / '1.1.md').read_bytes(), (self.v2 / 'ref.jsonl').read_bytes()
        report = c.merge(self.out, self.v2, self.merged, True, ['1.1'])
        result = c.check(self.merged)
        self.assertTrue(result['whole_document_priority_verified'])
        self.assertEqual(report['v2_documents_retained'], 1)
        rows = p.read_rows(self.merged)
        self.assertTrue(all(x['row']['metadata']['merge_provenance']['side'] == 'manual' for x in rows if x['row']['metadata']['source_file'] == 'raw/1.1.docx'))
        kept = [x['row'] for x in rows if x['row']['metadata']['source_file'] == 'raw/2.1.docx']
        self.assertEqual(kept[0]['content'], self.refs[2]['content'])
        self.assertEqual(before_md, (self.md / '1.1.md').read_bytes())
        self.assertEqual(before_v2, (self.v2 / 'ref.jsonl').read_bytes())

    def test_file_tampering(self):
        self.prepare()
        path = next(self.out.glob('*.jsonl'))
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError): c.check(self.out)

    def test_extra_file_refused(self):
        self.prepare()
        (self.out / 'unknown.txt').write_text('extra', encoding='utf-8')
        with self.assertRaises(ValueError): c.check(self.out)

    def test_report_tampering(self):
        self.prepare()
        path = self.out / '_audit/report.json'
        report = p.read_json(path); report['chunks'] += 1; p.write_json(path, report)
        with self.assertRaises(ValueError): c.check(self.out)

    def test_deterministic_ids(self):
        self.prepare()
        other = self.root / 'other'
        c.prepare(self.md, self.v2, other, ['1.1'])
        self.assertEqual([x['row']['id'] for x in p.read_rows(self.out)], [x['row']['id'] for x in p.read_rows(other)])

    def test_windows_absolute_asset_refused(self):
        (self.md / '1.1.md').write_text('1.1.1. ![x](C:/image.png)\n1.1.2. b\n', encoding='utf-8')
        with self.assertRaises(ValueError): self.prepare()

    def test_archive_unchosen_v2(self):
        self.prepare()
        c.merge(self.out, self.v2, self.merged, True, ['1.1'])
        archived = p.read_rows(self.merged / '_audit/inputs/v2')
        self.assertEqual([x['row'] for x in archived], self.refs)


if __name__ == '__main__':
    unittest.main()
