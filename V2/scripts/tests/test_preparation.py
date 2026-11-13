import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2/'src'))
from retrieval_eval.preparation import prepare_markdown, segment_document, split_text, normalize_legacy_markup
spec = importlib.util.spec_from_file_location('coverage14', V2/'scripts/check_preparation.py')
cov = importlib.util.module_from_spec(spec); spec.loader.exec_module(cov)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'V2/results/retrieval/documents_20261108_000000_000001'
        self.source.mkdir(parents=True)
        self.config = {'_root': self.root, '_v2': self.root/'V2'}
        self.records = []

    def add(self, text, name='a', asset=None):
        folder = self.source/name; folder.mkdir()
        md = folder/'document.md'; md.write_text(text, encoding='utf-8')
        rec = {'document_id': name+'.docx', 'source_file': 'data/raw/'+name+'.docx',
               'source_sha256': cov.sha(name.encode()), 'markdown': md.relative_to(self.root).as_posix(),
               'warnings': [], 'extraction_review_status': 'unreviewed'}
        (folder/'source.json').write_text(json.dumps(rec),encoding='utf-8')
        if asset:
            (folder/'assets').mkdir(); (folder/'assets/image.png').write_bytes(asset)
        self.records.append(rec)
        self.manifest()
        return md

    def manifest(self):
        (self.source/'extraction.json').write_text(json.dumps({'schema_version':'v2-documents-1','documents':self.records}),encoding='utf-8')

    def run_prepare(self):
        r = prepare_markdown(self.config, str(self.source))
        self.report = self.root/'V2/report.json'
        self.report.write_text(json.dumps(r),encoding='utf-8')
        return r

    def rows(self):
        return [json.loads(line) for f in (self.root/'V2/data/chunked').glob('*.jsonl') for line in f.read_text(encoding='utf-8').splitlines()]

    def test_all_characters_partitioned(self):
        text='Title\n\n1. One\n\n2. Two\n\nI. Next\n\n1. Restart\n'
        units,_=segment_document(text)
        self.assertEqual(''.join(u['text'] for u in units),text)

    def test_repeat_scoped_without_heading(self):
        self.add('1. A\n\n2. B\n\n1. C\n')
        self.run_prepare(); rows=self.rows()
        ones=[r for r in rows if r['metadata']['Clause']=='1']
        self.assertEqual(len(ones),2)
        self.assertNotEqual(ones[0]['metadata']['ClauseKey'],ones[1]['metadata']['ClauseKey'])
        self.assertEqual(cov.check(self.root,self.report)['status'],'technical_coverage_passed')

    def test_heading_scopes(self):
        self.add('ПРИЛОЖЕНИЕ 1\n\n1. A\n\nПРИЛОЖЕНИЕ 2\n\n1. B\n')
        self.run_prepare(); rows=self.rows()
        ones=[r for r in rows if r['metadata']['Clause']=='1']
        self.assertNotEqual(ones[0]['metadata']['Scope'],ones[1]['metadata']['Scope'])
        self.assertTrue(all(r['metadata']['section_heading'] for r in ones))

    def test_preamble_not_dropped(self):
        self.add('Important preamble\n\n1.1.1. Text\n')
        self.run_prepare()
        self.assertIn('Important preamble',''.join(r['content'] for r in self.rows()))
        self.assertEqual(cov.check(self.root,self.report)['documents'],1)

    def test_no_number_document_kept(self):
        self.add('Содержание\n\nВступительный текст\n')
        r=self.run_prepare()
        self.assertEqual(r['documents_prepared'],1)
        self.assertEqual(self.rows()[0]['metadata']['Clause'],'')

    def test_nested_list_not_owner_in_pue(self):
        units,_=segment_document('1.1.1. Clause\n\n1. subitem\n\n2. subitem\n\n1.1.2. Next\n')
        self.assertEqual([u['clause'] for u in units if u['kind']=='clause'],['1.1.1','1.1.2'])

    def test_inline_reference_not_owner(self):
        units,_=segment_document('See 1.2.3 for context\n')
        self.assertFalse(any(u['kind']=='clause' for u in units))

    def test_table_row_not_owner(self):
        units,_=segment_document('| 1. value |\n| --- |\n')
        self.assertFalse(any(u['kind']=='clause' for u in units))

    def test_bracket_wrapped_image(self):
        self.add('1.1.1. [![](assets/image.png), где x]\n',asset=b'image data')
        r=self.run_prepare()
        self.assertEqual(r['assets_copied'],1)
        self.assertIn('[![](assets/',self.rows()[0]['content'])
        cov.check(self.root,self.report)

    def test_missing_resource_blocks_before_write(self):
        self.add('1.1.1. ![](assets/missing.png)\n')
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse((self.root/'V2/data/chunked').exists())

    def test_external_link_not_fetched(self):
        self.add('1.1.1. [link](https://example.org/test)\n')
        r=self.run_prepare()
        self.assertEqual(r['assets_copied'],0)
        self.assertTrue(any(w['problem']=='external_or_anchor_link_not_fetched' for w in r['warnings']))

    def test_nonempty_target_never_overwritten(self):
        self.add('1.1.1. Text\n'); self.run_prepare()
        before={p.name:p.read_bytes() for p in (self.root/'V2/data/chunked').glob('*.jsonl')}
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'V2/data/chunked').glob('*.jsonl')})

    def test_empty_target_allowed(self):
        self.add('1.1.1. Text\n'); (self.root/'V2/data/chunked').mkdir(parents=True)
        self.run_prepare(); self.assertEqual(len(self.rows()),1)

    def test_manifest_missing_markdown_blocks(self):
        md=self.add('1.1.1. Text\n'); md.unlink()
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse((self.root/'V2/data/chunked').exists())

    def test_extra_markdown_blocks(self):
        self.add('1.1.1. Text\n'); (self.source/'extra.md').write_text('Extra')
        with self.assertRaises(ValueError): self.run_prepare()

    def test_sidecar_mismatch_blocks(self):
        self.add('1.1.1. Text\n'); self.records[0]['source_sha256']='bad'; self.manifest()
        with self.assertRaises(ValueError): self.run_prepare()

    def test_duplicate_manifest_blocks(self):
        self.add('1.1.1. Text\n'); self.records.append(copy.deepcopy(self.records[0])); self.manifest()
        with self.assertRaises(ValueError): self.run_prepare()

    def test_empty_document_blocks(self):
        self.add('  \n')
        with self.assertRaises(ValueError): self.run_prepare()

    def test_oversize_block_blocks_without_truncation(self):
        self.add('1.1.1. '+'x'*1500); self.config['max_chunk_bytes']=1024
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse((self.root/'V2/data/chunked').exists())

    def test_split_keeps_parts_and_byte_limit(self):
        parts=split_text('1.1.1. '+'я'*300+'\n\n'+'б'*300,1024)
        self.assertEqual(len(parts),2)
        self.assertTrue(all(len(x.encode())<=1024 for x in parts))

    def test_multiple_documents_and_coverage(self):
        self.add('1.1.1. A\n','a');self.add('No numbered clauses\n','b')
        r=self.run_prepare();checked=cov.check(self.root,self.report)
        self.assertEqual(r['documents_prepared'],2);self.assertEqual(checked['documents'],2)

    def test_changed_chunk_detected(self):
        self.add('1.1.1. Original\n'); self.run_prepare()
        file=next((self.root/'V2/data/chunked').glob('*.jsonl'))
        row=json.loads(file.read_text());row['content']='Modified'
        file.write_text(json.dumps(row),encoding='utf-8')
        with self.assertRaises(ValueError): cov.check(self.root,self.report)

    def test_changed_source_detected(self):
        md=self.add('1.1.1. Original\n'); self.run_prepare();md.write_text('Changed')
        with self.assertRaises(ValueError): cov.check(self.root,self.report)

    def test_ids_independent_of_extraction_timestamp(self):
        self.add('1.1.1. Stable\n');self.run_prepare();old=self.rows()[0]['id']
        import shutil
        shutil.rmtree(self.root/'V2/data/chunked')
        new=self.source.with_name('documents_20261109_000000_000001');self.source.rename(new);self.source=new
        for rec in self.records:
            rec['markdown']=str(new.relative_to(self.root))+'/'+Path(rec['markdown']).parent.name+'/document.md'
            (new/Path(rec['markdown']).parent.name/'source.json').write_text(json.dumps(rec))
        self.manifest();self.run_prepare();self.assertEqual(old,self.rows()[0]['id'])


    def test_signature_and_rules_title_not_owned_by_decree(self):
        self.add('3. Вступает в силу.\n\nМинистр\n\nН.Г. ШУЛЬГИНОВ\n\nУТВЕРЖДЕНЫ\n\nприказом от 12 августа 2022 г. N 811\n\nПРАВИЛА ТЕХНИЧЕСКОЙ ЭКСПЛУАТАЦИИ ЭЛЕКТРОУСТАНОВОК ПОТРЕБИТЕЛЕЙ ЭЛЕКТРИЧЕСКОЙ ЭНЕРГИИ\n\nI. Общие положения\n\n1. Правила устанавливают требования.\n')
        self.run_prepare(); rows = self.rows()
        decree = next(r for r in rows if r['metadata']['Clause']=='3')
        self.assertNotIn('Министр',decree['content']); self.assertNotIn('УТВЕРЖДЕНЫ',decree['content'])
        self.assertEqual(len([r for r in rows if r['metadata']['fragment_kind']=='service_block']),2)
        cov.check(self.root,self.report)

    def test_standalone_coefficients_table_has_no_invented_owner(self):
        self.add('16. Испытание образцов.\n\nКоэффициенты перегрузки\n\n| Нагрузка | Значение |\n| --- | --- |\n| Гололед | 1,3 |\n\n* Примечание.\n')
        self.run_prepare(); rows=self.rows()
        clause=next(r for r in rows if r['metadata']['Clause']=='16')
        table=next(r for r in rows if r['metadata']['fragment_kind']=='table_block')
        self.assertNotIn('Гололед',clause['content']); self.assertIn('Примечание',table['content'])
        self.assertEqual(table['metadata']['Clause'],''); self.assertEqual(table['metadata']['ClauseKey'],'')
        self.assertEqual(table['metadata']['table_ownership'],'requires_review')
        cov.check(self.root,self.report)

    def test_caption_in_prose_is_not_a_boundary(self):
        units,_=segment_document('1. Коэффициенты перегрузки устанавливаются расчётом.\n\nКоэффициенты перегрузки\n\nНе таблица.\n')
        self.assertFalse(any(u['kind']=='table_block' for u in units))

    def test_safe_link_cleanup_keeps_label_and_standard_number(self):
        text='1.1.1. См. #M12291 1200003320ГОСТ 15150-69#S и #M12293 0 1 2 3 4 5 6 7 8 9СНиП 2.01.07-85#S.\n'
        cleaned,edits,left=normalize_legacy_markup(text)
        self.assertEqual(cleaned,'1.1.1. См. ГОСТ 15150-69 и СНиП 2.01.07-85.\n')
        self.assertEqual(len(edits),4); self.assertFalse(left)
        self.add(text);r=self.run_prepare()
        self.assertEqual(r['removed_control_tokens'],4)
        self.assertTrue(cov.check(self.root,self.report)['normalization_deletions_verified'])

    def test_numeric_label_3064_not_eaten(self):
        text='#M12291 12000076223064-80#S'
        cleaned,edits,left=normalize_legacy_markup(text)
        self.assertEqual(cleaned,text);self.assertFalse(edits);self.assertEqual(len(left),2)

    def test_numeric_label_30030_not_eaten(self):
        text='#M12291 120001242630030 "Трансформаторы"#S'
        self.assertEqual(normalize_legacy_markup(text)[0],text)

    def test_numeric_label_short_ambiguous_not_eaten(self):
        for text in ('#M12291 1234567-80#S','#M12291 1234567.3#S','#M12291 1234567 В#S','#M12291 1234567В#S'):
            self.assertEqual(normalize_legacy_markup(text)[0],text)

    def test_g0_followed_by_useful_list_number(self):
        self.assertEqual(normalize_legacy_markup('#G01) в нормальном режиме:')[0],'1) в нормальном режиме:')
        self.assertEqual(normalize_legacy_markup('#G01.1.1. Норма')[0],'1.1.1. Норма')

    def test_marker_before_clause_is_detected_and_audited(self):
        self.add('#G0\n\n#G01.1.1. ГОСТ 30030, 220 В.\n')
        self.run_prepare();rows=self.rows()
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['metadata']['Clause'],'1.1.1')
        self.assertIn('30030, 220 В',rows[0]['content']);cov.check(self.root,self.report)

    def test_unresolved_markup_is_preserved_and_reported(self):
        self.add('1.1.1. #M12291 120001242630030 "Трансформаторы"#S\n')
        r=self.run_prepare();self.assertEqual(r['unresolved_markup_tokens'],2)
        self.assertIn('120001242630030',self.rows()[0]['content']);cov.check(self.root,self.report)

    def test_url_and_code_tokens_not_cleaned(self):
        for text in ('[x](https://example.org/#G0)', '`#G0`', '```text\n#G0\n```', 'https://example.org/#G1'):
            self.assertEqual(normalize_legacy_markup(text)[0],text)

    def test_unknown_control_form_is_preserved(self):
        text='#M999 123ГОСТ 123#S #G9'
        clean,edits,left=normalize_legacy_markup(text)
        self.assertEqual(clean,text);self.assertFalse(edits);self.assertEqual(len(left),3)

    def test_validator_rejects_deleted_printed_number(self):
        text='ГОСТ 30030'
        with self.assertRaises(ValueError):cov.validate_normalization(text,[{'start':5,'end':10,'removed':'30030','kind':'legacy_link_open'}],0)

    def test_validator_rejects_deletion_inside_code(self):
        with self.assertRaises(ValueError):cov.validate_normalization('`#G0`',[{'start':1,'end':4,'removed':'#G0','kind':'legacy_format'}],0)

    def test_validator_rejects_numeric_label_swallowing(self):
        text='#M12291 120001242630030 "Трансформаторы"#S'
        with self.assertRaises(ValueError):cov.validate_normalization(text,[{'start':0,'end':22,'removed':text[:22],'kind':'legacy_link_open'}],0)

    def test_normalization_edit_tampering_detected(self):
        self.add('1.1.1. #G0Норма\n');self.run_prepare()
        report=json.loads(self.report.read_text());span=next(s for s in report['document_inventory'][0]['source_spans'] if s['normalization_edits'])
        span['normalization_edits'][0]['end']+=1
        self.report.write_text(json.dumps(report))
        with self.assertRaises(ValueError):cov.check(self.root,self.report)

    def test_empty_legacy_anchor_cleaned_without_eating_next_text(self):
        text='#M12293 0 1 2 3 4 5 6 7 8 9\n\nГлава 1.3\n'
        self.assertEqual(normalize_legacy_markup(text)[0],'\n\nГлава 1.3\n')

    def test_unpaired_close_is_not_silently_removed(self):
        self.assertEqual(normalize_legacy_markup('ГОСТ 30030#S')[0],'ГОСТ 30030#S')


if __name__ == '__main__':
    unittest.main()
