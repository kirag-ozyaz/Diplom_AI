import copy
import json
from pathlib import Path
import tempfile
import unittest
import core

DOC = 'data/raw/Нормативная база/ПУЭ/DOCX/1.1.docx'

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old, self.v2 = self.root/'old', self.root/'v2'
        self.old.mkdir(); self.v2.mkdir()
        (self.old/'formula.png').write_bytes(b'old-image')
        (self.v2/'formula.png').write_bytes(b'new-image')
        self.manual = {'id':'old1','content':'Пункт 1.1.1. Формула $x=2$.\n\n![f](formula.png)',
                       'metadata':{'source_file':'1.1.md','Clause':'1.1.1','Chapter':'','Document':'ПУЭ'},'created_at':'original-date'}
        self.auto = {'id':'auto1','content':'1.1.1. ![formula](formula.png)',
                     'metadata':{'source_file':DOC,'Document':DOC,'Clause':'1.1.1',
                     'Scope':'section_0000_run_0000','part_index':1,'part_count':1,
                     'owner_review_status':'structural_candidate_not_reviewed',
                     'source_char_start':0,'source_char_end':80,'source_span_sha256':'original-span'}}
        self.write(self.old,[self.manual]); self.write(self.v2,[self.auto])

    def tearDown(self): self.tmp.cleanup()

    def write(self, path, rows):
        (path/'corpus.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')

    def convert(self, **kwargs):
        out=self.root/'converted'
        core.convert(self.old,self.v2,out,**kwargs)
        return out

    def row(self, path): return core.read_rows(path)[0]['row']

    def test_convert_preserves_formula_and_provenance(self):
        out=self.convert(); row=self.row(out); meta=row['metadata']
        self.assertIn('$x=2$',row['content'])
        self.assertEqual(meta['legacy_metadata'],self.manual['metadata'])
        self.assertEqual(meta['Chapter'],'1.1')
        self.assertEqual(meta['source_file'],DOC)
        self.assertIsNone(meta['source_span_sha256'])
        self.assertIsNone(meta['document_version_sha256'])
        self.assertEqual(meta['origin_provenance']['source_created_at'],'original-date')
        self.assertFalse(core.check(out)['semantic_or_visual_approval'])

    def test_inputs_unchanged(self):
        before={str(p):p.read_bytes() for r in (self.old,self.v2) for p in r.rglob('*') if p.is_file()}
        self.convert()
        self.assertEqual(before,{str(p):p.read_bytes() for r in (self.old,self.v2) for p in r.rglob('*') if p.is_file()})

    def test_deterministic_ids_and_rows(self):
        a=self.convert();b=self.root/'second';core.convert(self.old,self.v2,b)
        self.assertEqual(core.read_rows(a),core.read_rows(b))
        self.assertEqual((a/'_audit/report.json').read_bytes(),(b/'_audit/report.json').read_bytes())

    def test_reject_existing_output(self):
        a=self.convert()
        with self.assertRaises(ValueError):core.convert(self.old,self.v2,a)

    def test_reject_output_inside_input(self):
        with self.assertRaises(ValueError):core.convert(self.old,self.v2,self.old/'child')

    def test_reject_output_parent_of_input(self):
        with self.assertRaises(ValueError):core.convert(self.old,self.v2,self.root)

    def test_missing_asset_no_partial_output(self):
        (self.old/'formula.png').unlink()
        with self.assertRaises(ValueError):self.convert()
        self.assertFalse((self.root/'converted').exists())

    def test_path_traversal_rejected(self):
        (self.root/'secret.png').write_bytes(b'not-a-resource')
        self.manual['content']='![x](../secret.png)';self.write(self.old,[self.manual])
        with self.assertRaises(ValueError):self.convert()

    def test_windows_absolute_link_rejected(self):
        self.manual['content']='![x](C:/private.png)';self.write(self.old,[self.manual])
        with self.assertRaises(ValueError):self.convert()

    def test_duplicate_id_rejected(self):
        self.write(self.old,[self.manual,self.manual])
        with self.assertRaises(ValueError):self.convert()

    def test_invalid_json_rejected(self):
        (self.old/'corpus.jsonl').write_text('{broken}\n',encoding='utf-8')
        with self.assertRaises(ValueError):self.convert()

    def test_unknown_document_rejected(self):
        self.manual['metadata']['source_file']='unknown.md';self.write(self.old,[self.manual])
        with self.assertRaises(ValueError):self.convert()

    def test_explicit_document_map(self):
        self.manual['metadata']['source_file']='manual.md';self.write(self.old,[self.manual])
        out=self.convert(mapping={'manual.md':DOC})
        self.assertEqual(self.row(out)['metadata']['source_file'],DOC)

    def test_ambiguous_document_rejected(self):
        extra=copy.deepcopy(self.auto);extra['id']='auto2';extra['metadata']['source_file']='different/1.1.docx'
        self.write(self.v2,[self.auto,extra])
        with self.assertRaises(ValueError):self.convert()

    def test_ambiguous_scope_not_guessed(self):
        extra=copy.deepcopy(self.auto);extra['id']='auto2';extra['metadata']['Scope']='other'
        self.write(self.v2,[self.auto,extra]);row=self.row(self.convert())
        self.assertEqual(row['metadata']['scope_resolution'],'requires_review')
        self.assertNotEqual(row['metadata']['Scope'],self.auto['metadata']['Scope'])

    def test_short_clause_not_promoted(self):
        self.manual['metadata']['Clause']='1';self.write(self.old,[self.manual]);row=self.row(self.convert())
        self.assertEqual(row['metadata']['Clause'],'')
        self.assertEqual(row['metadata']['legacy_metadata']['Clause'],'1')

    def test_utf8_lossless_split(self):
        text=('Формула $x=2$, пояснение.\n\n'*5000)
        pieces=core.split_lossless(text)
        self.assertEqual(''.join(pieces),text)
        self.assertTrue(all(len(s.encode())<=60000 for s in pieces))

    def test_large_conversion(self):
        self.manual['content']='Я'*40000;self.write(self.old,[self.manual]);out=self.convert()
        self.assertEqual(len(core.read_rows(out)),2)
        core.check(out)

    def test_external_link_not_fetched(self):
        self.manual['content']='См. [источник](https://example.org/source)';self.write(self.old,[self.manual]);out=self.convert()
        self.assertEqual(self.row(out)['content'],self.manual['content'])
        core.check(out)

    def test_html_img_preserved_and_relinked(self):
        self.manual['content']='<img src="formula.png" alt="f">';self.write(self.old,[self.manual]);out=self.convert()
        self.assertIn('assets/',self.row(out)['content']);core.check(out)

    def test_extra_file_detected(self):
        out=self.convert();(out/'extra.jsonl').write_text('{}\n',encoding='utf-8')
        with self.assertRaises(ValueError):core.check(out)

    def test_modified_content_detected(self):
        out=self.convert();p=next(out.glob('*.jsonl'));p.write_text(p.read_text().replace('$x=2$','$x=3$'),encoding='utf-8')
        with self.assertRaises(ValueError):core.check(out)

    def test_modified_asset_detected(self):
        out=self.convert();next((out/'assets').iterdir()).write_bytes(b'changed')
        with self.assertRaises(ValueError):core.check(out)

    def test_modified_archive_detected(self):
        out=self.convert();(out/'_audit/inputs/v0/corpus.jsonl').write_text('{}\n',encoding='utf-8')
        with self.assertRaises(ValueError):core.check(out)

    def test_merge_plan_emits_no_active_chunks(self):
        out=self.convert();dest=self.root/'plan';r=core.merge(out,self.v2,dest)
        self.assertEqual(r['chunks'],0);self.assertEqual(r['conflicts'],1)
        self.assertFalse(list(dest.glob('*.jsonl')));core.check(dest)

    def test_apply_requires_explicit_priority(self):
        out=self.convert()
        with self.assertRaises(ValueError):core.merge(out,self.v2,self.root/'merged',apply=True)

    def test_merge_prefers_manual_without_losing_alternative(self):
        out=self.convert();dest=self.root/'merged';r=core.merge(out,self.v2,dest,apply=True,prefer_v0=['1.1'])
        self.assertEqual(r['chunks'],1);self.assertIn('$x=2$',self.row(dest)['content'])
        self.assertEqual(self.row(dest)['metadata']['merge_provenance']['side'],'v0')
        self.assertTrue((dest/'_audit/inputs/v2/formula.png').is_file())
        self.assertFalse(r['ready_for_final_scoring']);core.check(dest)

    def test_merge_prefers_v2_explicitly(self):
        out=self.convert();dest=self.root/'merged';core.merge(out,self.v2,dest,apply=True,prefer_v2=True)
        self.assertEqual(self.row(dest)['metadata']['merge_provenance']['side'],'v2');core.check(dest)

    def test_v2_only_document_retained(self):
        extra=copy.deepcopy(self.auto);extra['id']='second_doc';extra['metadata']['source_file']='raw/2.2.docx'
        self.write(self.v2,[self.auto,extra]);out=self.convert();dest=self.root/'merged';r=core.merge(out,self.v2,dest,apply=True,prefer_v0=['1.1'])
        self.assertEqual(r['documents'],2);core.check(dest)

    def test_manual_only_clause_retained(self):
        extra=copy.deepcopy(self.manual);extra['id']='old2';extra['metadata']['Clause']='1.1.2'
        self.write(self.old,[self.manual,extra]);out=self.convert();dest=self.root/'merged'
        r=core.merge(out,self.v2,dest,apply=True,prefer_v0=['1.1'])
        self.assertEqual(r['chunks'],2);core.check(dest)

    def test_unassigned_manual_archived_not_duplicate_active(self):
        extra=copy.deepcopy(self.manual);extra['id']='heading';extra['metadata']['Clause']='';extra['content']='Заголовок'
        self.write(self.old,[self.manual,extra]);out=self.convert();dest=self.root/'merged'
        r=core.merge(out,self.v2,dest,apply=True,prefer_v0=['1.1'])
        self.assertEqual(r['chunks'],1)
        self.assertTrue(any(x['action']=='archived_unassigned_requires_review' for x in r['records']))
        core.check(dest)

    def test_unknown_priority_chapter_rejected(self):
        out=self.convert()
        with self.assertRaises(ValueError):core.merge(out,self.v2,self.root/'merged',apply=True,prefer_v0=['9.9'])

    def test_merge_multipart_preserves_all_parts(self):
        self.manual['content']='Я'*40000;self.write(self.old,[self.manual]);out=self.convert();dest=self.root/'merged'
        core.merge(out,self.v2,dest,apply=True,prefer_v0=['1.1'])
        rows=[x['row'] for x in core.read_rows(dest)]
        self.assertEqual(len(rows),2)
        self.assertEqual(''.join(x['content'] for x in rows),self.manual['content'])
        self.assertTrue(all(x['metadata']['part_count']==2 for x in rows));core.check(dest)

    def test_merge_checks_v0_audit_before_use(self):
        out=self.convert();next((out/'assets').iterdir()).write_bytes(b'bad')
        with self.assertRaises(ValueError):core.merge(out,self.v2,self.root/'merged',apply=True,prefer_v2=True)

    def test_chapter_selection_missing_fails(self):
        with self.assertRaises(ValueError):self.convert(chapters=['1.2'])

    def test_math_warning_does_not_autocorrect_content(self):
        self.manual['content']='система $$TN$';self.write(self.old,[self.manual]);out=self.convert()
        self.assertEqual(self.row(out)['content'],self.manual['content'])
        self.assertTrue(core.read_json(out/'_audit/report.json')['warnings'])

    def test_changed_reference_v2_rejected(self):
        out=self.convert();self.auto['content']='Изменено';self.write(self.v2,[self.auto])
        with self.assertRaises(ValueError):core.merge(out,self.v2,self.root/'merged',apply=True,prefer_v2=True)

    def test_chapter_filter_cannot_hide_rows_in_mixed_file(self):
        extra=copy.deepcopy(self.manual);extra['id']='old_other';extra['metadata']['source_file']='1.2.md'
        self.write(self.old,[self.manual,extra])
        with self.assertRaises(ValueError):self.convert(chapters=['1.1'])

    def test_file_uri_not_treated_as_web_url(self):
        self.manual['content']='![x](file:///private.png)';self.write(self.old,[self.manual])
        with self.assertRaises(ValueError):self.convert()

if __name__=='__main__':unittest.main()
