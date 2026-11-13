"""Изолированные тесты исключения архива. Запуск без Milvus и моделей."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
SCRIPTS = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load('audit_test_reader', SCRIPTS / 'prepare_retrieval_qrels.py')
configurer = load('audit_test_config', SCRIPTS / 'configure_manual_corpus.py')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.corpus = self.root / 'V2/data/chunked_merged_manual'
        self.corpus.mkdir(parents=True)
        self.row = {'id': 'active', 'content': 'Сохранённый текст $x=a+b$.', 'metadata': {'source_file': '1.1.docx', 'Clause': '1.1.1'}}
        self.write(self.corpus / 'active.jsonl', self.row)

    def tearDown(self): self.temp.cleanup()

    def write(self, path, row):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')

    def read(self): return tool.load_corpus(self.root, self.corpus)

    def test_original_content_metadata_and_id(self):
        self.assertEqual(self.read()[0]['active'], self.row)

    def test_nested_active_documents_allowed(self):
        other = copy.deepcopy(self.row); other['id'] = 'nested'
        self.write(self.corpus / 'nested/doc.jsonl', other)
        self.assertEqual(set(self.read()[0]), {'active', 'nested'})

    def test_archive_not_in_rows_locations_manifest_order(self):
        other = copy.deepcopy(self.row); other['id'] = 'archived'
        self.write(self.corpus / '_audit/inputs/v2/old.jsonl', other)
        chunks, locations, files, order = self.read()
        self.assertEqual(set(chunks), {'active'})
        self.assertEqual(set(locations), {'active'})
        self.assertEqual(len(files), 1)
        self.assertTrue(all('_audit' not in name for name in order))

    def test_duplicate_id_in_archive_ignored(self):
        self.write(self.corpus / '_audit/original.jsonl', self.row)
        self.assertEqual(len(self.read()[0]), 1)

    def test_invalid_json_in_archive_not_read(self):
        path = self.corpus / '_audit/broken.jsonl'; path.parent.mkdir()
        path.write_text('not JSON', encoding='utf-8')
        self.assertEqual(len(self.read()[0]), 1)

    def test_nested_case_insensitive_audit(self):
        self.write(self.corpus / 'nested/_AuDiT/old.jsonl', self.row)
        self.assertEqual(len(self.read()[0]), 1)

    def test_archive_cannot_be_selected_directly(self):
        path = self.corpus / '_audit/inputs/v2/old.jsonl'; self.write(path, self.row)
        with self.assertRaises(tool.Invalid): tool.load_corpus(self.root, path.parent)

    def test_only_archive_is_not_a_corpus(self):
        (self.corpus / 'active.jsonl').unlink()
        self.write(self.corpus / '_audit/old.jsonl', self.row)
        with self.assertRaises(tool.Invalid): self.read()

    def test_live_duplicate_remains_error(self):
        self.write(self.corpus / 'another.jsonl', self.row)
        with self.assertRaises(tool.Invalid): self.read()

    def test_live_invalid_json_remains_error(self):
        (self.corpus / 'broken.jsonl').write_text('broken', encoding='utf-8')
        with self.assertRaises(tool.Invalid): self.read()

    def test_live_link_to_archive_rejected(self):
        path = self.corpus / '_audit/old.jsonl'; self.write(path, self.row)
        link = self.corpus / 'alias.jsonl'
        try: link.symlink_to(path)
        except OSError: self.skipTest('symlink недоступны')
        with self.assertRaises(tool.Invalid): self.read()

    def test_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            path=Path(other)/'outside.jsonl'; self.write(path, self.row)
            with self.assertRaises(tool.Invalid): tool.load_corpus(self.root, path.parent)

    def test_archive_changes_do_not_change_manifest(self):
        before = self.read()[2]
        self.write(self.corpus / '_audit/original.jsonl', self.row)
        self.assertEqual(before, self.read()[2])

    def setup_config(self):
        v2 = self.root / 'V2'
        (v2 / 'scripts').mkdir(); (v2 / 'configs').mkdir()
        shutil.copyfile(SCRIPTS / 'prepare_retrieval_qrels.py', v2 / 'scripts/prepare_retrieval_qrels.py')
        config = {'schema_version':'v2-pipeline-1', 'paths': {'chunks':'old', 'questions':'kept'},
                  'modes':{'base':{'model':'user_model','collection':'user_collection'}},'device':'cuda'}
        path = v2 / 'configs/pipeline_manual.json'
        path.write_text(json.dumps(config), encoding='utf-8-sig')
        return v2, path, config

    def test_config_changes_only_corpus_path(self):
        v2, src, config = self.setup_config(); raw = src.read_bytes()
        result = configurer.configure(v2)
        updated = json.loads(Path(result['config']).read_text())
        expected = copy.deepcopy(config); expected['paths']['chunks'] = 'V2/data/chunked_merged_manual'
        self.assertEqual(updated, expected)
        self.assertEqual(src.read_bytes(), raw)
        self.assertEqual(result['chunks'], 1)
        self.assertFalse(result['database_write_performed'])

    def test_config_no_overwrite(self):
        v2, _, _ = self.setup_config(); configurer.configure(v2)
        with self.assertRaises(ValueError): configurer.configure(v2)

    def test_config_outside_configs_rejected(self):
        v2, _, _ = self.setup_config()
        with self.assertRaises(ValueError): configurer.configure(v2, output='elsewhere.json')

    def test_unpatched_reader_refused(self):
        v2, _, _ = self.setup_config()
        (v2 / 'scripts/prepare_retrieval_qrels.py').write_text('EXCLUDES_AUDIT = False\n', encoding='utf-8')
        with self.assertRaises(ValueError): configurer.configure(v2)

    def test_python39_syntax(self):
        for name in ['prepare_retrieval_qrels.py', 'configure_manual_corpus.py']:
            ast.parse((SCRIPTS / name).read_text(encoding='utf-8'), feature_version=(3,9))


if __name__ == '__main__': unittest.main()
