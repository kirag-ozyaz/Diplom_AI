"""Проверки V3 без GPU, Milvus и Ollama: токенизация, BM25, RRF, окна, шаги, настройки.
Запуск из папки V3: python -m unittest discover -s scripts/tests -t . -v"""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

V3 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V3 / 'src'))
from retrieval_v3 import hybrid_retriever as hr
from retrieval_v3.hybrid_retriever import (BM25, Tokenizer, V3Error, load_v3_config, parse_variant,
                                           rrf, windows)


class TokenizerTest(unittest.TestCase):
    def test_clause_is_one_token(self):
        tokens = Tokenizer('none')('Требования п. 1.7.82 к заземлению')
        self.assertIn('#1.7.82', tokens)
        self.assertNotIn('82', tokens)

    def test_yo_and_case(self):
        self.assertEqual(Tokenizer('none')('ЁЛКА'), ['елка'])

    def test_snowball_joins_forms(self):
        try:
            tok = Tokenizer('snowball')
        except V3Error:
            self.skipTest('snowballstemmer не установлен')
        self.assertEqual(tok('заземления'), tok('заземлением'))


class BM25Test(unittest.TestCase):
    def test_ranking(self):
        docs = {'a': 'заземление нейтрали трансформатора', 'b': 'освещение помещений', 'c': 'п. 1.7.82 заземление'}
        bm = BM25(docs, Tokenizer('none'))
        self.assertEqual(bm.search('1.7.82', 3)[0][0], 'c')
        self.assertEqual(bm.search('освещение', 3)[0][0], 'b')
        self.assertEqual(bm.search('кабель', 3), [])

    def test_bad_params(self):
        with self.assertRaises(V3Error):
            BM25({'a': 'x'}, Tokenizer('none'), k1=0)


class FusionTest(unittest.TestCase):
    def test_rrf(self):
        out = rrf({'bm25': ['a', 'b'], 'e5': ['b', 'c']}, {'bm25': 1.0, 'e5': 1.0}, 60)
        self.assertEqual(out[0][0], 'b')
        self.assertAlmostEqual(out[0][1], 1/62 + 1/61)

    def test_rrf_weight_zero(self):
        out = rrf({'bm25': ['a'], 'e5': ['b']}, {'bm25': 0.0, 'e5': 1.0}, 60)
        self.assertEqual(out[0][0], 'b')

    def test_rrf_duplicate(self):
        with self.assertRaises(V3Error):
            rrf({'bm25': ['a', 'a']}, {}, 60)


class WindowsTest(unittest.TestCase):
    def test_short_text(self):
        self.assertEqual(windows('abc', 1500, 300), ['abc'])

    def test_cover_and_overlap(self):
        text = ''.join(chr(1072 + i % 32) for i in range(5439))
        parts = windows(text, 1500, 300)
        self.assertTrue(all(len(p) <= 1500 for p in parts))
        self.assertEqual(parts[0][-300:], parts[1][:300])
        self.assertTrue(text.endswith(parts[-1]))


class VariantTest(unittest.TestCase):
    def test_default_steps(self):
        spec = importlib.util.spec_from_file_location('v3_eval', V3 / 'scripts/v3_evaluation.py')
        ev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ev)
        for v in ev.DEFAULT_VARIANTS:
            parse_variant(v)
        self.assertEqual(parse_variant('bm25_e5_clip+rerank+exact'), (['bm25', 'e5', 'clip'], {'rerank', 'exact'}))

    def test_bad_steps(self):
        for v in ('bm25_bm25', 'tfidf', 'bm25+fast', 'e5+fullchunk'):
            with self.assertRaises(V3Error):
                parse_variant(v)


class ExactClauseTest(unittest.TestCase):
    def setUp(self):
        self.r = types.SimpleNamespace(clause_index={'1.7.82': ['c1'], '1.7.5': ['c2'], '2.5.1': ['c3']})

    def ids(self, q):
        return hr.HybridRetrieverV3.exact_clause_ids(self.r, q)

    def test_clause(self):
        self.assertEqual(self.ids('Что сказано в п. 1.7.82?'), ['c1'])

    def test_table_and_figure_are_not_clauses(self):
        self.assertEqual(self.ids('Что указано в таблице 1.7.5?'), [])
        self.assertEqual(self.ids('Покажите рис. 2.5.1'), [])


class ConfigTest(unittest.TestCase):
    def test_project_config(self):
        cfg = json.loads((V3 / 'configs/v3_config.json').read_text(encoding='utf-8'))
        self.assertEqual((cfg['device'], cfg['clip_device']), ('cuda', 'cuda'))
        self.assertEqual(cfg['schema_version'], hr.DEFAULT['schema_version'])

    def make(self, **change):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'V2/src/retrieval_eval').mkdir(parents=True)
        cfg = {**json.loads((V3 / 'configs/v3_config.json').read_text(encoding='utf-8')),
               'project_root': str(tmp), **change}
        p = tmp / 'v3_config.json'
        p.write_text(json.dumps(cfg), encoding='utf-8')
        return p

    def test_load(self):
        c = load_v3_config(self.make())
        self.assertEqual(c['_results'], (V3 / 'results').resolve())

    def test_results_outside_v3(self):
        with self.assertRaises(V3Error):
            load_v3_config(self.make(results_dir='/tmp/elsewhere'))

    def test_bad_depth(self):
        with self.assertRaises(V3Error):
            load_v3_config(self.make(search_depth=100, candidate_depth=50))


if __name__ == '__main__':
    unittest.main()
