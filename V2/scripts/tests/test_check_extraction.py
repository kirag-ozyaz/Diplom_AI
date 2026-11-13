import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
SCRIPT=HERE/'check_extraction.py'
if not SCRIPT.exists(): SCRIPT=HERE.parent/'check_extraction.py'
spec=importlib.util.spec_from_file_location('auditor',SCRIPT)
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
W=a.W; M=a.M; A=a.A; R=a.R

def doc_xml(body):
    return ('<w:document xmlns:w="'+W+'" xmlns:m="'+M+'" xmlns:a="'+A+'" xmlns:r="'+R+'"><w:body>'+body+'</w:body></w:document>').encode()
def para(t): return '<w:p><w:r><w:t>'+t+'</w:t></w:r></w:p>'

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.raw=self.root/'data/raw'; self.raw.mkdir(parents=True)
        self.extracted=self.root/'V2/results/retrieval/documents_fixture'; self.folder=self.extracted/'document'; self.folder.mkdir(parents=True)
        self.assets=self.folder/'assets'; self.assets.mkdir()
    def make(self,body=None,md='1.1.1. Test text\n',extras=None):
        self.src=self.raw/'sample.docx'
        with ZipFile(self.src,'w') as z:
            z.writestr('word/document.xml',doc_xml(body or para('1.1.1. Test text')))
            for k,v in (extras or {}).items(): z.writestr(k,v)
        self.dest=self.folder/'document.md'; self.dest.write_text(md,encoding='utf-8')
        self.rec=dict(source_file='data/raw/sample.docx',source_sha256=a.sha(self.src.read_bytes()),markdown=self.dest.relative_to(self.root).as_posix(),warnings=[],extraction_review_status='unreviewed')
        self.commit()
    def commit(self):
        (self.folder/'source.json').write_text(json.dumps(self.rec),encoding='utf-8')
        (self.extracted/'extraction.json').write_text(json.dumps(dict(schema_version='v2-documents-1',documents=[self.rec])),encoding='utf-8')
    def run_audit(self): return a.audit(self.root,self.extracted,self.raw)
    def codes(self): return self.run_audit()['issue_counts']
    def test_clean_and_read_only(self):
        self.make(); before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report=self.run_audit(); self.assertEqual(report['status'],'technical_checks_passed')
        self.assertFalse(report['automatically_approved_for_chunking'])
        self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))
    def test_source_hash(self):
        self.make(); self.src.write_bytes(self.src.read_bytes()+b'tampered')
        self.assertIn('source_sha256_mismatch',self.codes())
    def test_missing_paragraph(self):
        self.make(); self.dest.write_text('1.1.1. Different text\n',encoding='utf-8')
        self.assertIn('paragraph_text_occurrences_not_confirmed',self.codes())
    def test_clause_order(self):
        self.make(para('1.1.1. First')+para('1.1.2. Second'),'1.1.2. Second\n\n1.1.1. First\n')
        self.assertIn('literal_clause_sequence_differs',self.codes())
    def test_automatic_numbering(self):
        self.make('<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Text</w:t></w:r></w:p>','Text\n')
        self.assertIn('automatic_numbering_not_reconstructed',self.codes())
    def test_style_numbering(self):
        styles='<w:styles xmlns:w="'+W+'"><w:style w:styleId="List"><w:pPr><w:numPr/></w:pPr></w:style></w:styles>'
        self.make('<w:p><w:pPr><w:pStyle w:val="List"/></w:pPr><w:r><w:t>Text</w:t></w:r></w:p>','Text\n',{'word/styles.xml':styles})
        self.assertIn('automatic_numbering_not_reconstructed',self.codes())
    def test_table_cells(self):
        table='<w:tbl><w:tr><w:tc>'+para('Header')+'</w:tc></w:tr><w:tr><w:tc>'+para('123')+'</w:tc></w:tr></w:tbl>'
        self.make(para('1.1.1. Test text')+table,'1.1.1. Test text\n\n| Header |\n| --- |\n| 123 |\n')
        self.assertNotIn('table_cells_or_order_not_confirmed',self.codes())
        self.dest.write_text(self.dest.read_text().replace('123','124'),encoding='utf-8')
        self.assertIn('table_cells_or_order_not_confirmed',self.codes())
    def test_merged_xml(self):
        table='<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'+para('Header')+'</w:tc></w:tr></w:tbl>'
        self.make(para('1.1.1. Test text')+table,'1.1.1. Test text\n\n| Header |\n| --- |\n\n[table](assets/table.xml)\n')
        (self.assets/'table.xml').write_text('<w:tbl xmlns:w="'+W+'"><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'+para('Header')+'</w:tc></w:tr></w:tbl>',encoding='utf-8')
        self.assertNotIn('merged_table_xml_missing_or_changed',self.codes())
        self.assertIn('merged_table_visual_layout_requires_review',self.codes())
        (self.assets/'table.xml').write_text('<w:tbl xmlns:w="'+W+'"/>',encoding='utf-8')
        self.assertIn('merged_table_xml_missing_or_changed',self.codes())
    def test_formula_xml(self):
        math='<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>'
        self.make(para('1.1.1. Test text')+'<w:p>'+math+'</w:p>','1.1.1. Test text\n\n[formula](assets/f.xml)\n')
        (self.assets/'f.xml').write_text('<m:oMath xmlns:m="'+M+'"><m:r><m:t>x</m:t></m:r></m:oMath>',encoding='utf-8')
        self.assertNotIn('formula_xml_missing_or_changed',self.codes())
        (self.assets/'f.xml').write_text('<m:oMath xmlns:m="'+M+'"/>',encoding='utf-8')
        self.assertIn('formula_xml_missing_or_changed',self.codes())
    def test_images_and_hash(self):
        image=b'fixture image bytes'; filename=a.sha(image)+'.png'
        rels='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="image" Target="media/a.png"/></Relationships>'
        self.make(para('1.1.1. Test text')+'<w:p><w:r><a:blip r:embed="rId1"/></w:r></w:p>','1.1.1. Test text\n\n![](assets/'+filename+')\n',{'word/_rels/document.xml.rels':rels,'word/media/a.png':image})
        asset=self.assets/filename; asset.write_bytes(image)
        self.assertNotIn('image_content_or_occurrences_differ',self.codes())
        asset.write_bytes(b'bad'); codes=self.codes()
        self.assertIn('resource_content_hash_mismatch',codes); self.assertIn('image_content_or_occurrences_differ',codes)
    def test_missing_link(self):
        self.make(md='1.1.1. Test text\n\n![](assets/missing.png)\n')
        self.assertIn('linked_resource_missing',self.codes())
    def test_inventory(self):
        self.make(); (self.raw/'missing.docx').write_bytes(b'not extracted')
        self.assertIn('source_not_in_extraction',self.codes())
    def test_outside_resource(self):
        self.make(md='1.1.1. Test text\n\n[bad](../../../../../../etc/passwd)\n')
        self.assertIn('resource_outside_document_folder',self.codes())
    def test_supplementary(self):
        self.make(extras={'word/footnotes.xml':'<w:footnotes xmlns:w="'+W+'">'+para('Footnote')+'</w:footnotes>'})
        self.assertIn('supplementary_parts_not_verified',self.codes())
    def test_cli_report_and_status(self):
        self.make(); before=self.src.read_bytes()
        command=[sys.executable,str(SCRIPT),'--project-root',str(self.root),'--input',self.extracted.relative_to(self.root).as_posix()]
        first=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stderr); printed=json.loads(first.stdout)
        self.assertTrue(Path(printed['report']).is_file())
        self.assertEqual(self.src.read_bytes(),before)
        self.dest.write_text('lost text',encoding='utf-8')
        second=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(second.returncode,1,second.stderr)
        self.assertNotEqual(json.loads(second.stdout)['report'],printed['report'])


    def clone_run(self,name):
        import shutil
        dest=self.extracted.parent/name
        shutil.copytree(self.extracted,dest)
        rec=dict(self.rec)
        rec['markdown']=rec['markdown'].replace(self.extracted.name,name)
        (dest/'document/source.json').write_text(json.dumps(rec),encoding='utf-8')
        (dest/'extraction.json').write_text(json.dumps(dict(schema_version='v2-documents-1',documents=[rec])),encoding='utf-8')
        return dest
    def test_auto_newest_completed_ignores_mtime(self):
        import os
        self.make()
        older=self.clone_run('documents_20261108_141723_743877')
        newer=self.clone_run('documents_20261108_142000_000001')
        os.utime(older,(2000000000,2000000000))
        selected,meta=a.select_input(self.root)
        self.assertEqual(selected,newer)
        self.assertEqual(meta['mode'],'latest_completed_by_folder_timestamp')
    def test_auto_skips_incomplete(self):
        self.make(); older=self.clone_run('documents_20261108_141723_743877')
        unfinished=self.extracted.parent/'documents_20261108_150000_000001'; unfinished.mkdir()
        selected,meta=a.select_input(self.root)
        self.assertEqual(selected,older)
        self.assertEqual(meta['ignored_incomplete'],[unfinished.name])
    def test_auto_no_runs(self):
        self.make()
        with self.assertRaises(ValueError): a.select_input(self.root)
    def test_auto_explicit_wins(self):
        self.make(); self.clone_run('documents_20261108_141723_743877')
        selected,meta=a.select_input(self.root,self.extracted.relative_to(self.root))
        self.assertEqual(selected,self.extracted)
        self.assertEqual(meta['mode'],'explicit')
    def test_auto_corrupt_manifest_fails_no_fallback(self):
        self.make(); self.clone_run('documents_20261108_141723_743877')
        newer=self.clone_run('documents_20261108_150000_000001')
        (newer/'extraction.json').write_text('broken',encoding='utf-8')
        result=subprocess.run([sys.executable,str(SCRIPT),'--project-root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertFalse(result.stdout)
    def test_auto_cli_without_input(self):
        self.make(); newest=self.clone_run('documents_20261108_141723_743877')
        result=subprocess.run([sys.executable,str(SCRIPT),'--project-root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        summary=json.loads(result.stdout)
        self.assertEqual(summary['input'],str(newest))
        report=json.loads(Path(summary['report']).read_text(encoding='utf-8'))
        self.assertEqual(report['input_selection']['directory'],str(newest))
    def test_auto_invalid_dates_ignored(self):
        self.make(); valid=self.clone_run('documents_20261108_141723_743877')
        self.clone_run('documents_20261340_256199_999999')
        selected,meta=a.select_input(self.root)
        self.assertEqual(selected,valid)


    def bracket_image_fixture(self):
        image=b'bracket image fixture'; name=a.sha(image)+'.png'
        rels='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="image" Target="media/a.png"/></Relationships>'
        body=para('1.1.1. Test text')+'<w:p><w:r><w:t>Expression [</w:t></w:r><w:r><a:blip r:embed="rId1"/></w:r><w:r><w:t>, units]</w:t></w:r></w:p>'
        md='1.1.1. Test text\n\nExpression [![](assets/'+name+'), units]\n'
        self.make(body,md,{'word/_rels/document.xml.rels':rels,'word/media/a.png':image})
        asset=self.assets/name; asset.write_bytes(image)
        return asset
    def test_inline_image_after_literal_bracket(self):
        self.bracket_image_fixture()
        self.assertNotIn('image_content_or_occurrences_differ',self.codes())
        self.dest.write_text('1.1.1. Test text\n\nExpression [, units]\n',encoding='utf-8')
        self.assertIn('image_content_or_occurrences_differ',self.codes())
    def test_inline_image_after_bracket_corruption_detected(self):
        asset=self.bracket_image_fixture(); asset.write_bytes(b'corrupted')
        codes=self.codes()
        self.assertIn('resource_content_hash_mismatch',codes)
        self.assertIn('image_content_or_occurrences_differ',codes)


    def test_content_control_wrapped_table_rows_cells(self):
        table='<w:sdt><w:sdtPr/><w:sdtContent><w:tbl><w:sdt><w:sdtContent><w:tr><w:sdt><w:sdtContent><w:tc>'+para('Preserved cell')+'</w:tc></w:sdtContent></w:sdt></w:tr></w:sdtContent></w:sdt></w:tbl></w:sdtContent></w:sdt>'
        self.make(para('1.1.1. Test text')+table,'1.1.1. Test text\n\n| Preserved cell |\n| --- |\n')
        self.assertNotIn('table_cells_or_order_not_confirmed',self.codes())
        self.assertNotIn('paragraph_text_occurrences_not_confirmed',self.codes())
    def test_content_control_lost_cell_detected(self):
        table='<w:sdt><w:sdtContent><w:tbl><w:tr><w:tc>'+para('Lost cell')+'</w:tc></w:tr></w:tbl></w:sdtContent></w:sdt>'
        self.make(para('1.1.1. Test text')+table)
        codes=self.codes()
        self.assertIn('paragraph_text_occurrences_not_confirmed',codes)
        self.assertIn('table_cells_or_order_not_confirmed',codes)
    def test_content_control_clause_order(self):
        body='<w:sdt><w:sdtContent>'+para('1.1.1. First')+para('1.1.2. Second')+'</w:sdtContent></w:sdt>'
        self.make(body,'1.1.2. Second\n\n1.1.1. First\n')
        self.assertIn('literal_clause_sequence_differs',self.codes())

if __name__=='__main__': unittest.main(verbosity=2)
