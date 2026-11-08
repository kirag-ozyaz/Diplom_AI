#!/usr/bin/env python3
"""Standalone read-only audit of V2 extraction. Python 3.10+, standard library."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sys
import unicodedata
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

VERSION = 'extraction-audit-1.3'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
V = 'urn:schemas-microsoft-com:vml'
# A literal '[' before an inline image must not swallow its '![' marker.
LINK = re.compile(r'(!?)\[([^\[\]]*)\]\(([^)]+)\)')
CLAUSE = re.compile(r'^\s*(?:#{1,6}\s*)?(\d+\.\d+\.\d+(?:\.\d+)*)(?:\.)?\s+(?=\S)', re.M)

def sha(b): return hashlib.sha256(b).hexdigest()
def inside(p, parent): return p == parent or parent in p.parents

def path(root, value):
    p = (root / value).resolve()
    if not inside(p, root): raise ValueError('Path outside project: '+str(value))
    return p

def xml(b):
    if len(b) > 30000000 or b'<!DOCTYPE' in b.upper() or b'<!ENTITY' in b.upper():
        raise ValueError('Unsafe/oversized XML')
    return ET.fromstring(b)

def fp(e):
    return (e.tag, tuple(sorted(e.attrib.items())), (e.text or '').strip(), tuple(fp(c) for c in e))

def text(e): return ''.join(n.text or '' for n in e.iter('{'+W+'}t'))
def norm(s): return re.sub(r'\s+', '', unicodedata.normalize('NFKC', s.replace('\\|','|').replace('<br>','\n')))
def plain(s): return LINK.sub('', s)

def md_tables(md):
    groups, acc = [], []
    for line in md.splitlines()+['']:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'): acc.append(line)
        elif acc: groups.append(acc); acc=[]
    result=[]
    for group in groups:
        rows=[]
        for line in group:
            cells = re.split(r'(?<!\\)\|',line)[1:-1]
            if cells and all(re.fullmatch(r'\s*:?-{3,}:?\s*',c) for c in cells): continue
            rows.append([norm(plain(c)) for c in cells])
        result.append(rows)
    return result


def visible_children(container, wanted):
    """OOXML content controls are transparent for block/row/cell inventory."""
    for e in container:
        local=e.tag.rsplit('}',1)[-1]
        if local in wanted:
            yield e
        elif local in ('sdtContent','customXml'):
            yield from visible_children(e,wanted)
        elif local=='sdt':
            content=e.find('{'+W+'}sdtContent')
            if content is not None:
                yield from visible_children(content,wanted)

def check_document(root, extracted, rec):
    issues=[]
    out={'source_file':rec.get('source_file'), 'markdown':rec.get('markdown'), 'findings':issues}
    def add(level, code, **details): issues.append(dict(level=level, code=code, **details))
    src=path(root,rec['source_file']); dest=path(root,rec['markdown'])
    if not inside(dest, extracted): raise ValueError('Markdown outside selected extraction')
    if not src.is_file() or not dest.is_file():
        add('error','source_or_markdown_missing'); return out
    source_bytes=src.read_bytes(); md=dest.read_text(encoding='utf-8-sig')
    out.update(source_sha256=sha(source_bytes),markdown_sha256=sha(dest.read_bytes()))
    if out['source_sha256'] != rec.get('source_sha256'): add('error','source_sha256_mismatch')
    sidecar=dest.parent/'source.json'
    if not sidecar.is_file(): add('error','source_json_missing')
    elif json.loads(sidecar.read_text(encoding='utf-8-sig')) != rec: add('error','source_json_differs_from_manifest')
    resources=[]; images=[]
    for image,label,target in LINK.findall(md):
        u=urlsplit(target.strip().strip('<>'))
        if u.scheme or u.netloc: add('review','external_link_not_checked',target=target); continue
        if not u.path: continue
        asset=(dest.parent/unquote(u.path)).resolve()
        if not inside(asset,dest.parent): add('error','resource_outside_document_folder',target=target); continue
        if not asset.is_file(): add('error','linked_resource_missing',target=target); continue
        resources.append(asset)
        if image: images.append(asset)
        if re.fullmatch('[a-f0-9]{64}',asset.stem) and sha(asset.read_bytes()) != asset.stem:
            add('error','resource_content_hash_mismatch',target=target)
    if re.search(r'<(?:img|table|math)\b',md,re.I): add('review','html_content_requires_review')
    if src.suffix.lower()=='.md':
        original=source_bytes.decode('utf-8-sig')
        strip=lambda s: re.sub(r'!\[([^\]]*)\]\([^)]+\)',r'![\1](IMAGE)',s)
        if strip(original)!=strip(md): add('error','markdown_source_text_changed')
        hashes=Counter(sha(p.read_bytes()) for p in images)
        expected=Counter()
        for image,label,target in LINK.findall(original):
            if not image: continue
            u=urlsplit(target.strip().strip('<>'))
            if u.scheme or u.netloc: add('review','external_source_image',target=target); continue
            asset=(src.parent/unquote(u.path)).resolve()
            if not inside(asset,root) or not asset.is_file(): add('error','source_image_missing',target=target)
            else: expected[sha(asset.read_bytes())]+=1
        if hashes!=expected: add('error','markdown_image_content_or_occurrences_differ')
        add('review','markdown_html_layout_and_nonimage_resources_not_verified')
        return out
    if src.suffix.lower()!='.docx': add('error','unsupported_source_format'); return out
    with ZipFile(src) as z:
        if sum(i.file_size for i in z.infolist())>250000000: raise ValueError('Uncompressed DOCX exceeds 250 MB')
        doc=xml(z.read('word/document.xml')); body=doc.find('{'+W+'}body')
        if body is None: raise ValueError('Missing document body')
        parents={c:e for e in body.iter() for c in e}
        paragraphs=list(body.iter('{'+W+'}p'))
        leaf=[p for p in paragraphs if not any(e.tag=='{'+W+'}p' for e in list(p.iter())[1:])]
        expected=Counter(norm(text(p)) for p in leaf if norm(text(p))); actual=norm(plain(md))
        missing=[dict(text_excerpt=s[:240],expected_occurrences=n,observed_occurrences=actual.count(s)) for s,n in expected.items() if actual.count(s)<n]
        if missing: add('review','paragraph_text_occurrences_not_confirmed',count=len(missing),examples=missing)
        out['paragraphs_checked']=sum(expected.values())
        clauses=[m.group(1) for p in visible_children(body,{'p'}) for m in [CLAUSE.match(text(p))] if m]
        out['literal_clauses']=len(clauses)
        if clauses!=CLAUSE.findall(md): add('review','literal_clause_sequence_differs',source=clauses,extracted=CLAUSE.findall(md))
        if not clauses: add('review','no_literal_numbered_clauses_found')
        styles={}
        if 'word/styles.xml' in z.namelist(): styles={e.get('{'+W+'}styleId'):e for e in xml(z.read('word/styles.xml')).findall('{'+W+'}style')}
        def numbered(p):
            if p.find('./{'+W+'}pPr/{'+W+'}numPr') is not None: return True
            s=p.find('./{'+W+'}pPr/{'+W+'}pStyle'); sid=s.get('{'+W+'}val') if s is not None else None; seen=set()
            while sid in styles and sid not in seen:
                seen.add(sid); st=styles[sid]
                if st.find('./{'+W+'}pPr/{'+W+'}numPr') is not None: return True
                s=st.find('{'+W+'}basedOn'); sid=s.get('{'+W+'}val') if s is not None else None
            return False
        n=sum(numbered(p) for p in paragraphs)
        if n: add('review','automatic_numbering_not_reconstructed',paragraphs=n)
        tables=list(visible_children(body,{'tbl'})); expected_tables=[]; merged=[]
        for t in tables:
            rows=[[norm(text(c)) for c in visible_children(r,{'tc'})] for r in visible_children(t,{'tr'})]
            width=max(map(len,rows),default=0); expected_tables.append([r+['']*(width-len(r)) for r in rows])
            if any(e.tag in ('{'+W+'}gridSpan','{'+W+'}vMerge') for e in t.iter()): merged.append(t)
        actual_tables=md_tables(md)
        out['tables']=dict(source_top_level=len(tables),markdown=len(actual_tables),merged=len(merged))
        if expected_tables!=actual_tables:
            differences=[]
            for ti in range(max(len(expected_tables),len(actual_tables))):
                expected_rows=expected_tables[ti] if ti<len(expected_tables) else []
                actual_rows=actual_tables[ti] if ti<len(actual_tables) else []
                for ri in range(max(len(expected_rows),len(actual_rows))):
                    left=expected_rows[ri] if ri<len(expected_rows) else None
                    right=actual_rows[ri] if ri<len(actual_rows) else None
                    if left!=right:
                        differences.append(dict(table=ti+1,row=ri+1,source_cells=left,extracted_cells=right))
            add('review','table_cells_or_order_not_confirmed',difference_count=len(differences),examples=differences[:20])
        xml_assets=[]
        for asset in resources:
            if asset.suffix.lower()=='.xml':
                try: xml_assets.append(fp(xml(asset.read_bytes())))
                except (ValueError,ET.ParseError): add('error','invalid_linked_xml',path=asset.name)
        actual_xml=Counter(xml_assets)
        needed=Counter(fp(t) for t in merged)
        for signature,n in needed.items():
            if actual_xml[signature]<n: add('error','merged_table_xml_missing_or_changed',expected=n,found=actual_xml[signature])
        if merged: add('review','merged_table_visual_layout_requires_review',count=len(merged))
        math=[]
        for e in body.iter():
            if e.tag not in ('{'+M+'}oMath','{'+M+'}oMathPara'): continue
            p=parents.get(e); nested=False
            while p is not None:
                if p.tag in ('{'+M+'}oMath','{'+M+'}oMathPara'): nested=True; break
                p=parents.get(p)
            if not nested: math.append(e)
        for signature,n in Counter(fp(e) for e in math).items():
            if actual_xml[signature]<n: add('error','formula_xml_missing_or_changed',expected=n,found=actual_xml[signature])
        out['formula_blocks']=len(math)
        if math: add('review','formula_xml_preserved_but_searchability_not_proven',count=len(math))
        rels={}
        if 'word/_rels/document.xml.rels' in z.namelist(): rels={r.get('Id'):r for r in xml(z.read('word/_rels/document.xml.rels'))}
        expected_images=Counter()
        for e in body.iter():
            rid=(e.get('{'+R+'}embed') or e.get('{'+R+'}link')) if e.tag=='{'+A+'}blip' else e.get('{'+R+'}id') if e.tag=='{'+V+'}imagedata' else None
            if not rid: continue
            rel=rels.get(rid)
            if rel is None: add('error','image_relationship_missing',rid=rid); continue
            if rel.get('TargetMode')=='External': add('review','external_image_not_preserved',rid=rid); continue
            target=rel.get('Target',''); member=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('word',target))
            expected_images[sha(z.read(member))]+=1
        actual_images=Counter(sha(p.read_bytes()) for p in images)
        if expected_images!=actual_images: add('error','image_content_or_occurrences_differ',source=dict(expected_images),extracted=dict(actual_images),missing=dict(expected_images-actual_images),extra=dict(actual_images-expected_images))
        out['image_occurrences']=sum(expected_images.values())
        supplementary=[]
        for name in z.namelist():
            if re.fullmatch(r'word/(?:header\d+|footer\d+|footnotes|endnotes|comments)\.xml',name):
                extra=xml(z.read(name))
                if text(extra).strip() or any(e.tag in ('{'+A+'}blip','{'+V+'}imagedata','{'+M+'}oMath') for e in extra.iter()): supplementary.append(name)
        if supplementary: add('review','supplementary_parts_not_verified',parts=supplementary)
        if any(e.tag in ('{'+W+'}del','{'+W+'}ins','{'+W+'}altChunk','{'+W+'}txbxContent','{'+W+'}object') for e in body.iter()): add('review','revisions_textboxes_or_embedded_objects_require_review')
    return out

def audit(root, extracted, raw):
    manifest_file=(extracted/'extraction.json').resolve()
    if not inside(manifest_file,extracted): raise ValueError('Manifest outside selected extraction directory')
    b=manifest_file.read_bytes(); manifest=json.loads(b.decode('utf-8-sig'))
    if manifest.get('schema_version')!='v2-documents-1': raise ValueError('Expected v2-documents-1 extraction.json')
    records=manifest.get('documents')
    if not isinstance(records,list) or not records: raise ValueError('No extracted document records')
    if not raw.is_dir(): raise ValueError('Raw directory does not exist')
    issues=[]; listed=[path(root,r['source_file']) for r in records]
    if len(listed)!=len(set(listed)): issues.append(dict(level='error',code='duplicate_source_records'))
    sources={p.resolve() for p in raw.rglob('*') if p.is_file() and p.suffix.lower() in ('.docx','.md')}
    for p in sorted(sources-set(listed)): issues.append(dict(level='error',code='source_not_in_extraction',path=str(p.relative_to(root))))
    for p in listed:
        if not inside(p,raw): issues.append(dict(level='error',code='source_outside_selected_raw',path=str(p)))
    other=[str(p.relative_to(root)) for p in raw.rglob('*') if p.is_file() and p.suffix.lower() in ('.pdf','.doc','.rtf','.odt')]
    if other: issues.append(dict(level='review',code='other_document_formats_not_extracted',paths=other))
    docs=[]
    for rec in records:
        try: docs.append(check_document(root,extracted,rec))
        except (OSError,ValueError,KeyError,TypeError,ET.ParseError,BadZipFile,RuntimeError) as exc:
            docs.append(dict(source_file=rec.get('source_file'),findings=[dict(level='error',code='document_audit_failed',detail=str(exc))]))
    findings=issues+[f for d in docs for f in d['findings']]; counts=Counter(f['level'] for f in findings)
    return dict(schema_version=VERSION,script_sha256=sha(Path(__file__).read_bytes()),extraction_manifest_sha256=sha(b),
        audited_at=datetime.now().astimezone().isoformat(),status='failed' if counts['error'] else 'requires_review' if counts['review'] else 'technical_checks_passed',
        automatically_approved_for_chunking=False,scope='Structural evidence only; no semantic, visual, OCR, qrels or indexing approval.',
        counts=dict(documents=len(docs),errors=counts['error'],review=counts['review']),issue_counts=dict(Counter(f['code'] for f in findings)),global_findings=issues,documents=docs)


def select_input(root, explicit=None):
    if explicit:
        selected=path(root,explicit)
        return selected, dict(mode='explicit',directory=str(selected),ignored_incomplete=[])
    base=path(root,'V2/results/retrieval')
    candidates=[]; incomplete=[]
    if base.is_dir():
        for folder in base.iterdir():
            if not folder.is_dir() or not re.fullmatch(r'documents_\d{8}_\d{6}_\d{6}',folder.name): continue
            try: stamp=datetime.strptime(folder.name,'documents_%Y%m%d_%H%M%S_%f')
            except ValueError: continue
            checked=path(root,folder)
            if (checked/'extraction.json').is_file(): candidates.append((stamp,checked))
            else: incomplete.append(folder.name)
    if not candidates:
        raise ValueError('Нет завершённого извлечения в V2/results/retrieval: нужен documents_<дата>_<время>_<микросекунды>/extraction.json. Сначала выполните prepare-documents либо задайте --input.')
    selected=max(candidates,key=lambda item:item[0])[1]
    return selected,dict(mode='latest_completed_by_folder_timestamp',directory=str(selected),ignored_incomplete=sorted(incomplete))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='Optional extraction directory; default latest documents_<timestamp> with extraction.json in V2/results/retrieval')
    parser.add_argument('--project-root',default='.',help='Project root; default current directory')
    parser.add_argument('--raw',default='data/raw',help='Source directory, relative to project root')
    args=parser.parse_args(argv)
    try:
        root=Path(args.project_root).resolve(); extracted,selection=select_input(root,args.input); raw=path(root,args.raw)
        report=audit(root,extracted,raw)
        report['input_selection']=selection
        output=path(root,'V2/results/extraction_audit/'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        if any(inside(output,p) or inside(p,output) for p in (raw,extracted)): raise ValueError('Output overlaps source/extraction')
        output.mkdir(parents=True,exist_ok=False)
        with (output/'audit.json').open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
        lines=['# Проверка извлечения','','Status: '+report['status'],'','Структурная сверка, не автоматическое одобрение. Полные подробности: audit.json.','',json.dumps(report['counts']), '','## Findings']
        lines += ['- '+k+': '+str(v) for k,v in report['issue_counts'].items()]
        for d in report['documents']:
            lines+=['','## '+str(d['source_file'])]+['- '+f['level']+': '+f['code'] for f in d['findings']]
        with (output/'audit.md').open('x',encoding='utf-8') as f: f.write('\n'.join(lines)+'\n')
        print(json.dumps(dict(report=str(output/'audit.json'),input=str(extracted),selection=selection['mode'],ignored_incomplete=selection['ignored_incomplete'],status=report['status'],**report['counts']),ensure_ascii=False,indent=2))
        return 2 if report['counts']['errors'] else 1 if report['counts']['review'] else 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('AUDIT ERROR: '+str(exc),file=sys.stderr); return 2

if __name__=='__main__': sys.exit(main())
