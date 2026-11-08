"""Извлечение DOCX/Markdown. Исходники read-only; OMML и неоднозначности не скрываются."""
import hashlib
import json
import re
import os
from pathlib import Path
from .common import ensure, inside, path_in, run_id, write_json, file_sha


def extract_documents(config, source_path=None):
    source = path_in(config['_root'], source_path) if source_path else config['paths']['raw']
    ensure(source.exists(), 'Нет исходных документов')
    files = sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in ('.docx', '.md')) if source.is_dir() else [source]
    ensure(files, 'Нет DOCX/Markdown')
    out = config['paths']['results'] / ('documents_' + run_id())
    ensure(inside(out, config['_v2']), 'Выход вне V2')
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for file in files:
        ensure(inside(file, config['_root']), 'Источник вне проекта')
        ensure(file.suffix.lower() in ('.docx', '.md'), 'Поддерживаются DOCX и Markdown; другие форматы не конвертируются молча')
        rel = file.relative_to(config['_root']).as_posix()
        identity = hashlib.sha256(rel.encode()).hexdigest()[:16]
        folder = out / identity
        folder.mkdir()
        assets = folder / 'assets'
        warnings = []
        if file.suffix.lower() == '.md':
            text = file.read_text(encoding='utf-8-sig')
            def replace_image(m):
                target = m.group(2).strip().strip('<>')
                ensure(not re.match(r'^[A-Za-z]+:', target), 'Внешний ресурс Markdown не скачивается автоматически')
                p = (file.parent / target).resolve()
                ensure(inside(p, config['_root']) and p.is_file(), 'Нет локального ресурса: ' + target)
                assets.mkdir(exist_ok=True)
                name = file_sha(p) + p.suffix.lower()
                dest = assets / name
                if not dest.exists():
                    with dest.open('xb') as stream:
                        stream.write(p.read_bytes())
                return '![' + m.group(1) + '](assets/' + name + ')'
            text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, text)
            warnings.append('Markdown HTML/resources require source review; only local Markdown image links are copied')
        else:
            from docx import Document
            from docx.oxml.ns import qn
            doc = Document(file)
            image_names = {}
            # rId сохраняется независимо от положения повторных рисунков.
            for rid, relation in doc.part.rels.items():
                if 'image' not in relation.reltype:
                    continue
                if relation.is_external:
                    warnings.append('external_image_not_fetched:' + rid)
                    continue
                part = relation.target_part
                assets.mkdir(exist_ok=True)
                suffix = Path(str(part.partname)).suffix.lower()
                name = hashlib.sha256(part.blob).hexdigest() + suffix
                dest = assets / name
                if not dest.exists():
                    with dest.open('xb') as stream:
                        stream.write(part.blob)
                image_names[rid] = 'assets/' + name
            math_counter = [0]
            def render(element):
                tag = element.tag.rsplit('}',1)[-1]
                if tag in ('oMath','oMathPara'):
                    from lxml import etree
                    math_counter[0] += 1
                    name = 'formula_%04d.omml.xml' % math_counter[0]
                    assets.mkdir(exist_ok=True)
                    with (assets/name).open('xb') as stream:
                        stream.write(etree.tostring(element, encoding='utf-8', xml_declaration=True))
                    warnings.append('formula_preserved_as_OMML_not_transcribed:' + name)
                    return '[Формула OMML](assets/' + name + ')'
                if tag == 't':
                    return element.text or ''
                if tag in ('br','cr'):
                    return '\n'
                if tag == 'tab':
                    return '\t'
                if tag == 'blip':
                    rid = element.get(qn('r:embed'))
                    if rid in image_names:
                        return '![](' + image_names[rid] + ')'
                return ''.join(render(child) for child in element)
            def visible_children(container, wanted):
                # Word content controls can wrap blocks, table rows OR cells.
                for child in container:
                    kind = child.tag.rsplit('}', 1)[-1]
                    if kind in wanted:
                        yield child
                    elif kind in ('sdt', 'sdtContent', 'customXml'):
                        if kind == 'sdt':
                            content = child.find(qn('w:sdtContent'))
                            if content is not None:
                                yield from visible_children(content, wanted)
                        else:
                            yield from visible_children(child, wanted)
                    elif kind not in ('sectPr', 'sdtPr', 'sdtEndPr', 'tblPr', 'tblGrid', 'trPr', 'tcPr'):
                        warnings.append('unhandled_structure_requires_review:' + kind)
            blocks=[]
            for element in visible_children(doc.element.body, {'p', 'tbl'}):
                kind=element.tag.rsplit('}',1)[-1]
                if kind=='p':
                    text_part=render(element)
                    if element.xpath('.//w:numPr'):
                        warnings.append('automatic_list_numbering_requires_review')
                    if text_part.strip():
                        blocks.append(text_part)
                elif kind=='tbl':
                    rows=[]
                    merged=False
                    for tr in visible_children(element, {'tr'}):
                        cells=[]
                        for tc in visible_children(tr, {'tc'}):
                            merged |= bool(tc.xpath('.//w:gridSpan | .//w:vMerge'))
                            cells.append(render(tc).replace('|',r'\|').replace('\n','<br>'))
                        rows.append(cells)
                    if rows:
                        width=max(map(len, rows))
                        rows=[r+['']*(width-len(r)) for r in rows]
                        blocks.append('\n'.join(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*width)+' |']+['| '+' | '.join(r)+' |' for r in rows[1:]]))
                    if merged:
                        from lxml import etree
                        assets.mkdir(exist_ok=True)
                        name='table_'+hashlib.sha256(etree.tostring(element)).hexdigest()[:16]+'.xml'
                        with (assets/name).open('wb') as stream:
                            stream.write(etree.tostring(element,encoding='utf-8',xml_declaration=True))
                        warnings.append('merged_cells_preserved_in_XML_require_review:' + name)
                        blocks.append('[Исходная структура таблицы](assets/'+name+')')
            text='\n\n'.join(blocks)+'\n'
            warnings.append('headers_footers_footnotes_and_automatic_numbering_require_manual_review')
        target=folder/'document.md'
        with target.open('x',encoding='utf-8') as stream:
            stream.write(text)
        record={'extraction_version':'v2-documents-2-sdt','source_file':rel,'source_sha256':file_sha(file),'markdown':target.relative_to(config['_root']).as_posix(),
                'document_id':rel,'warnings':sorted(set(warnings)),'extraction_review_status':'unreviewed'}
        write_json(folder/'source.json',record,config['_v2'])
        records.append(record)
    report={'schema_version':'v2-documents-1','documents':records,'output':out.relative_to(config['_root']).as_posix(),
            'ready_for_final_scoring':False,'note':'Сохранение структуры не доказывает полноту извлечения. Формулы не превращаются в выдуманный текст.'}
    write_json(out/'extraction.json',report,config['_v2'])
    return report
