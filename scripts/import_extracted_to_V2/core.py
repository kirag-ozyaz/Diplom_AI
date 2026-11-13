"""НОВЫЙ импортёр: data/extracted/*.md -> data/chunked_manual.
Старый scripts/convert_chunked_V0_to_V2/convert.py НЕ изменяется.
Python 3.9+, только стандартная библиотека. Исходники и БД не изменяются.
"""
import argparse
import collections
import copy
import datetime
import json
from pathlib import Path
import re
import shutil
import sys
import preservation as p

VERSION = 'manual-markdown-candidate-1'
p.VERSION = VERSION
DEFAULT_CHAPTERS = ['1.' + str(i) for i in range(1, 10)]
POINT = re.compile(r'^\s*(1\.\d+\.\d+)\.(?:\s|$)')
HEADING = re.compile(r'^\s*#{1,6}\s*(\S.*)')
DOLLAR = re.compile(r'(?<!\\)\$\$?')


def parse_lines(text):
    """Границы строк с учётом формул и блоков кода; текст не нормализуется."""
    pos, fence, math = 0, None, None
    for line in text.splitlines(keepends=True):
        outside = fence is None and math is None
        yield pos, line, outside
        fm = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence):
                fence = None
        elif fm:
            fence = fm.group(1)
        else:
            for token in DOLLAR.finditer(line):
                if math is None:
                    math = token.group()
                elif token.group() == math:
                    math = None
            if r'\[' in line:
                p.require(math in (None, r'\['), 'Вложенная математическая разметка')
                math = r'\['
            if r'\]' in line:
                p.require(math == r'\[', 'Закрывающий разделитель \\] без \\[')
                math = None
        pos += len(line)
    p.require(fence is None and math is None, 'Не закрыта формула или блок кода; исходник не исправляется автоматически')


def split_safe(text, limit=60000):
    """Разрезы только по пустым строкам вне формул/кода, не внутри таблицы."""
    cuts = [0]
    for pos, line, outside in parse_lines(text):
        if outside and not line.strip():
            cuts.append(pos + len(line))
    cuts.append(len(text))
    atoms = [text[a:b] for a, b in zip(cuts, cuts[1:]) if a != b]
    pieces, current = [], ''
    for atom in atoms:
        p.require(len(atom.encode('utf-8')) <= limit,
                  'Единый абзац/таблица/формула больше 60000 байт; требуется явное разбиение исходника')
        if current and len((current + atom).encode('utf-8')) > limit:
            p.require(current.strip(), 'Слишком большой блок пустых строк')
            pieces.append(current)
            current = ''
        current += atom
    if current:
        if current.strip():
            pieces.append(current)
        elif pieces:
            p.require(len((pieces[-1] + current).encode('utf-8')) <= limit, 'Слишком много завершающих пробелов')
            pieces[-1] += current
    p.require(pieces and ''.join(pieces) == text, 'Невозможно безопасно сохранить весь текст')
    return pieces


def segment(text, chapter):
    """Покрывает ВЕСЬ Markdown. Заголовки разделов сохраняются активным контекстом."""
    starts = {0}
    for pos, line, outside in parse_lines(text):
        if not outside:
            continue
        match = POINT.match(line)
        if match:
            p.require(match.group(1).startswith(chapter + '.'), 'Чужая глава в собственном пункте: ' + match.group(1))
            starts.add(pos)
            continue
        heading = HEADING.match(line)
        if heading and not re.match(r'(?:Таблица|Примечани[ея]|Рис(?:унок)?\b)', heading.group(1), re.I):
            starts.add(pos)
    positions = sorted(starts) + [len(text)]
    out, seen = [], set()
    for a, b in zip(positions, positions[1:]):
        if a == b:
            continue
        span = text[a:b]
        if not span.strip():
            if out:
                out[-1]['end'] = b
                out[-1]['text'] += span
            continue
        if not out:
            a = 0
            span = text[:b]
        match = POINT.match(span.lstrip().splitlines()[0])
        clause = match.group(1) if match else ''
        if clause:
            p.require(clause not in seen, 'Повтор собственного пункта: ' + clause)
            seen.add(clause)
        out.append({'start': a, 'end': b, 'text': span, 'clause': clause,
                    'kind': 'clause' if clause else 'structural_context'})
    p.require(out and seen, 'Не найдены собственные пункты ' + chapter)
    p.require(''.join(s['text'] for s in out) == text, 'Не весь Markdown покрыт диапазонами')
    return out


def emit(source, meta, text, identity):
    parts = split_safe(text)
    ids = ['v2_' + p.sha(p.stable([VERSION, identity, i, part]))[:40]
           for i, part in enumerate(parts, 1)]
    result = []
    for i, (cid, part) in enumerate(zip(ids, parts), 1):
        m = copy.deepcopy(meta)
        m.update(part_index=i, part_count=len(parts), related_chunk_ids=ids,
                 contains_tables=('|' in part), contains_images=('![' in part or '<img' in part.lower()))
        result.append({'id': cid, 'content': part, 'metadata': m})
    return result


def grouped_relations(rows):
    groups = collections.OrderedDict()
    for row in rows:
        m = row['metadata']
        key = (m['source_file'], m.get('Scope'), m.get('Clause')) if m.get('Clause') else ('@', m.get('manual_block_id', row['id']))
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        ids = [r['id'] for r in group]
        for i, r in enumerate(group, 1):
            r['metadata'].update(part_index=i, part_count=len(group), related_chunk_ids=ids)


def prepare(input_root, v2_root, output, chapters=None):
    chapters = DEFAULT_CHAPTERS if chapters is None else chapters
    p.require(chapters and len(chapters) == len(set(chapters)), 'Нужны неповторяющиеся главы')
    p.require(all(re.fullmatch(r'1\.\d+', c) for c in chapters), 'Поддержаны собственные главы ПУЭ вида 1.x')
    ref = p.read_rows(v2_root)
    docs, scopes = p.document_index(ref)
    documents, original = [], {}
    for chapter in chapters:
        path = p.within(input_root / (chapter + '.md'), input_root)
        p.require(path.is_file(), 'Не найден Markdown: ' + str(path))
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')  # CRLF сохраняется; не используется read_text с преобразованием строк.
        segments = segment(text, chapter)
        choices = docs.get(chapter, set())
        p.require(len(choices) == 1, 'Неоднозначный/неизвестный документ V2 для ' + chapter)
        doc = next(iter(choices))
        expected = {str(x['row']['metadata'].get('Clause')) for x in ref
                    if x['row']['metadata']['source_file'] == doc and x['row']['metadata'].get('Clause')}
        actual = {s['clause'] for s in segments if s['clause']}
        p.require(expected == actual, 'Не совпало покрытие пунктов ' + chapter + ': нет=' + str(sorted(expected-actual)) + '; лишние=' + str(sorted(actual-expected)))
        for s in segments:
            if s['clause']:
                variants = scopes[(doc, s['clause'])]
                p.require(len(variants) == 1 and bool(next(iter(variants))), 'Неоднозначный Scope: ' + s['clause'])
        original[chapter] = (path, raw, text, segments, doc)
        documents.append({'chapter': chapter, 'document': doc, 'markdown': path.name,
                          'sha256': p.sha(raw), 'decoded_sha256': p.sha(text), 'characters': len(text),
                          'clauses': sorted(actual), 'spans': []})

    def build(stage):
        snap = stage / '_audit' / 'inputs' / 'manual'
        snap.mkdir(parents=True)
        pseudo, warnings = [], []
        for info in documents:
            chapter = info['chapter']
            path, raw, text, segments, doc = original[chapter]
            markdown_archive = stage / '_audit' / 'markdown' / path.name
            markdown_archive.parent.mkdir(parents=True, exist_ok=True)
            markdown_archive.write_bytes(raw)
            for s in segments:
                cid = 'md_' + p.sha(p.stable([path.name, p.sha(raw), s['start'], s['end']]))[:40]
                clause = s['clause']
                scope = next(iter(scopes[(doc, clause)])) if clause else 'manual_context_' + cid[3:15]
                meta = {'Document': doc, 'source_file': doc, 'Clause': clause, 'Scope': scope,
                    'ClauseKey': json.dumps([doc, scope, clause], ensure_ascii=False) if clause else '',
                    'Chapter': chapter, 'Section': '', 'Paragraph': '', 'section_heading': '', 'block_title': '',
                    'fragment_kind': s['kind'], 'numbering_scheme': 'hierarchical' if clause else 'context',
                    'scope_resolution': 'matched_scope_candidate' if clause else 'manual_structural_context',
                    'owner_review_status': 'user_supplied_manual_source',
                    'table_ownership': 'as_supplied_in_manual_markdown', 'reference_resolution': 'not_performed',
                    'references': [], 'table_ids': re.findall(r'(?mi)^\s*#*\s*Таблица\s+(\d+(?:\.\d+)+)', s['text']),
                    'chunking_version': VERSION, 'document_version_sha256': None,
                    'source_char_start': None, 'source_char_end': None, 'source_span_sha256': None,
                    'manual_block_id': cid, 'manual_markdown_sha256': p.sha(raw),
                    'manual_char_start': s['start'], 'manual_char_end': s['end'], 'manual_span_sha256': p.sha(s['text']),
                    'extraction_warnings': ['manual_markdown_not_docx_extraction'],
                    'origin_provenance': {'kind': 'manual_markdown', 'markdown_file': path.name,
                        'source_bytes_sha256': p.sha(raw), 'decoded_char_start': s['start'], 'decoded_char_end': s['end'],
                        'span_sha256': p.sha(s['text']), 'offset_basis': 'UTF-8-sig decoded text with original CRLF preserved',
                        'note': 'source_file is the logical DOCX association, not evidence of DOCX text offsets'}}
                pseudo.append({'id': cid, 'content': s['text'], 'metadata': meta})
                info['spans'].append({'start': s['start'], 'end': s['end'], 'source_id': cid, 'clause': clause})
                for _, _, _, refpath in p.references(s['text']):
                    if p.external_target(refpath):
                        continue
                    src = p.resource_path(input_root, path.name, refpath)
                    dest = snap / src.relative_to(input_root)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copyfile(src, dest)
                    p.require(p.sha(src.read_bytes()) == p.sha(dest.read_bytes()), 'Ресурс изменился при копировании')
                for line in s['text'].splitlines():
                    if re.search(r'(?<![/\w])img_[\w.-]+\.(?:png|gif)', re.sub(r'!\[[^\]]*\]\([^)]*\)', '', line)):
                        warnings.append({'markdown': path.name, 'clause': clause, 'code': 'bare_image_filename_preserved'})
            p.require(path.read_bytes() == raw, 'Markdown изменился во время импорта: ' + path.name)
        p.save_rows(snap, pseudo)
        items = p.read_rows(snap)
        rows, records = [], []
        for item in items:
            r = item['row']
            content, edits, external = p.relink(r['content'], snap, item['file'], stage)
            out = emit(r, r['metadata'], content, ['prepare', r['id']])
            rows += out
            records.append(p.add_record(stage, 'manual', item, out, edits, external, 'manual_markdown_preserved'))
        return p.finish(stage, {'operation': 'prepare_markdown', 'status': 'manual_markdown_candidates_prepared',
            'chapters': list(chapters), 'input_markdown_documents': len(documents),
            'own_clauses': sum(len(d['clauses']) for d in documents),
            'structural_context_blocks': sum(r['metadata']['fragment_kind'] == 'structural_context' for r in pseudo),
            'source_policy': 'as_supplied_no_normative_rewriting', 'markdown_documents': documents,
            'reference_v2_files': {x['file']: x['file_sha256'] for x in ref},
            'records': records, 'warnings': warnings}, rows)
    return p.publish(output, [input_root, v2_root], build)


def check(root):
    result = p.check(root)
    report = p.read_json(root / '_audit' / 'report.json')
    p.require(report['schema_version'] == VERSION, 'Это не набор нового Markdown-импортёра')
    rows = p.read_rows(root) if report['chunks'] else []
    by_id = {x['row']['id']: x['row'] for x in rows}
    if report['operation'] == 'prepare_markdown':
        pseudo = p.read_rows(root / '_audit' / 'inputs' / 'manual')
        sources = {x['row']['id']: x['row'] for x in pseudo}
        covered = set()
        for info in report['markdown_documents']:
            path = p.within(root / '_audit' / 'markdown' / info['markdown'], root)
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            p.require(p.sha(raw) == info['sha256'] and p.sha(text) == info['decoded_sha256'], 'Изменён исходный Markdown')
            p.require(len(text) == info['characters'], 'Не совпал размер исходного Markdown')
            cursor, content, clauses = 0, [], []
            for span in info['spans']:
                p.require(span['start'] == cursor and span['end'] > cursor, 'Пропуск/пересечение диапазонов Markdown')
                row = sources[span['source_id']]
                m = row['metadata']
                p.require(row['id'] not in covered, 'Повтор диапазона Markdown')
                covered.add(row['id'])
                original = text[span['start']:span['end']]
                p.require(row['content'] == original, 'Не совпал текст диапазона Markdown')
                p.require(m['source_file'] == info['document'] and m['Chapter'] == info['chapter']
                    and m['Clause'] == span['clause'], 'Не совпала принадлежность диапазона')
                p.require(m['manual_char_start'] == span['start'] and m['manual_char_end'] == span['end']
                    and m['manual_markdown_sha256'] == info['sha256'] and m['manual_span_sha256'] == p.sha(original), 'Неверное происхождение Markdown')
                cursor = span['end']
                content.append(original)
                if span['clause']:
                    clauses.append(span['clause'])
            p.require(cursor == len(text) and ''.join(content) == text, 'Markdown восстановлен не целиком')
            p.require(sorted(clauses) == info['clauses'] and len(clauses) == len(set(clauses)), 'Неверное покрытие пунктов')
        p.require(covered == set(sources), 'Лишний исходный блок вне Markdown')
        for record in report['records']:
            source = sources[record['source_id']]
            for cid in record['output_ids']:
                for key, value in source['metadata'].items():
                    p.require(by_id[cid]['metadata'].get(key) == value, 'Изменено происхождение/метаданные Markdown: ' + key)
        result.update(markdown_documents_reconstructed=len(report['markdown_documents']),
                      own_clauses=report['own_clauses'], markdown_bytes_preserved=True)
    elif report['operation'] == 'merge_manual_documents':
        manual_root = root / '_audit' / 'inputs' / 'manual'
        check(manual_root)
        mr = p.read_json(manual_root / '_audit' / 'report.json')
        manual_docs = {x['document'] for x in mr['markdown_documents']
                       if x['chapter'] in report['prefer_manual_chapters']}
        v2 = p.read_rows(root / '_audit' / 'inputs' / 'v2')
        v2_by_id = {x['row']['id']: x['row'] for x in v2}
        p.require(mr['reference_v2_files'] == {x['file']: x['file_sha256'] for x in v2}, 'Не совпал замороженный эталон V2')
        manual_by_id = {x['row']['id']: x['row'] for x in p.read_rows(manual_root)}
        for record in report['records']:
            source = (manual_by_id if record['side'] == 'manual' else v2_by_id)[record['source_id']]
            doc = source['metadata']['source_file']
            chosen = report['applied'] and ((record['side'] == 'manual' and doc in manual_docs)
                      or (record['side'] == 'v2' and doc not in manual_docs))
            p.require(bool(record['output_ids']) == bool(chosen), 'Нарушен приоритет целого документа')
            for cid in record['output_ids']:
                m = by_id[cid]['metadata']
                p.require(m['source_file'] == doc and m.get('Clause') == source['metadata'].get('Clause')
                    and m.get('Scope') == source['metadata'].get('Scope'), 'Изменена принадлежность чанка')
                mp = m['merge_provenance']
                p.require(mp['side'] == record['side'] and mp['source_id'] == source['id']
                    and mp['source_row_sha256'] == p.sha(p.stable(source)), 'Неверное происхождение объединённого чанка')
        result.update(whole_document_priority_verified=True,
                      manual_documents_selected=len(manual_docs) if report['applied'] else 0)
    else:
        raise ValueError('Неизвестная операция нового импортёра')
    return result


def merge(manual_root, v2_root, output, apply=False, prefer=None):
    p.require(not apply or prefer, '--apply требует явного --prefer-manual-chapters')
    check(manual_root)
    mr = p.read_json(manual_root / '_audit' / 'report.json')
    p.require(mr['operation'] == 'prepare_markdown', 'Вход --manual должен быть результатом prepare.py')
    manual, v2 = p.read_rows(manual_root), p.read_rows(v2_root)
    p.require(mr['reference_v2_files'] == {x['file']: x['file_sha256'] for x in v2},
              'V2 изменился после импорта: повторите prepare.py с новым --output')
    p.group_rows(manual)
    p.group_rows(v2)
    preferred = set(prefer or [])
    p.require(preferred <= set(mr['chapters']), 'Импортёр не содержит всех запрошенных глав')
    selected = {d['document'] for d in mr['markdown_documents'] if d['chapter'] in preferred}
    p.require(not ({x['row']['id'] for x in manual} & {x['row']['id'] for x in v2}), 'Пересечение ID двух входов')

    def build(stage):
        p.snapshot(manual, manual_root, stage, 'manual', include_prior_audit=True)
        p.snapshot(v2, v2_root, stage, 'v2')
        rows, records = [], []
        counts = collections.Counter()
        for side, items, source_root in [('manual', manual, manual_root), ('v2', v2, v2_root)]:
            for item in items:
                source = item['row']
                chosen = ((side == 'manual' and source['metadata']['source_file'] in selected)
                          or (side == 'v2' and source['metadata']['source_file'] not in selected))
                if not apply or not chosen:
                    action = 'planned_not_emitted' if not apply else 'archived_whole_document_alternative'
                    records.append(p.add_record(stage, side, item, [], [], [], action))
                    counts['archived_rows'] += 1
                    continue
                content, edits, external = p.relink(source['content'], source_root, item['file'], stage)
                m = copy.deepcopy(source['metadata'])
                m['parent_source_trace'] = {f: m.get(f) for f in p.TRACE_FIELDS}
                for field in p.TRACE_FIELDS:
                    m[field] = None
                m['owner_review_status'] = 'user_supplied_manual_source' if side == 'manual' else 'v2_candidate_unchanged_content'
                m['chunking_version'] = VERSION
                m['merge_provenance'] = {'side': side, 'source_id': source['id'],
                    'source_row_sha256': p.sha(p.stable(source)), 'selection_policy': 'whole_document',
                    'content_changes': 'local_resource_destinations_only'}
                # Существующие части V2 не режем заново и не «чиняем» их разметку.
                p.require(len(content.encode('utf-8')) <= 60000, 'После переноса ссылок превышен лимит content')
                cid = 'v2_' + p.sha(p.stable([VERSION, 'merge', side, source['id'], content]))[:40]
                out = [{'id': cid, 'content': content, 'metadata': m}]
                rows += out
                records.append(p.add_record(stage, side, item, out, edits, external, 'selected_whole_document'))
                counts[side + '_active_chunks'] += 1
        grouped_relations(rows)
        return p.finish(stage, {'operation': 'merge_manual_documents',
            'status': 'merged_manual_candidates_prepared' if apply else 'plan_only_no_active_chunks',
            'applied': bool(apply), 'input_manual_rows': len(manual), 'input_v2_rows': len(v2),
            'prefer_manual_chapters': sorted(preferred), 'selection_policy': 'whole_document',
            'manual_documents_selected': len(selected) if apply else 0,
            'v2_documents_retained': len({x['row']['metadata']['source_file'] for x in v2} - selected) if apply else 0,
            'source_policy': 'as_supplied_no_normative_rewriting', 'records': records, **counts}, rows)
    return p.publish(output, [manual_root, v2_root], build)


def main(command):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument('--output', help='Новая папка результата; существующие папки не перезаписываются')
    if command == 'prepare':
        parser.add_argument('--input', default='data/extracted')
        parser.add_argument('--v2', default='V2/data/chunked')
        parser.add_argument('--chapters', nargs='+', default=DEFAULT_CHAPTERS)
    if command == 'merge':
        parser.add_argument('--manual', default='data/chunked_manual')
        parser.add_argument('--v2', default='V2/data/chunked')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--prefer-manual-chapters', nargs='+')
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        default = 'data/chunked_manual'
        if command == 'merge':
            default = 'V2/data/chunked_merged_manual' if args.apply else 'V2/results/import_extracted_to_V2/plan'
        dest = p.project_path(root, args.output or default)
        if command == 'prepare':
            result = prepare(p.project_path(root, args.input), p.project_path(root, args.v2), dest, args.chapters)
        elif command == 'merge':
            result = merge(p.project_path(root, args.manual), p.project_path(root, args.v2), dest,
                           args.apply, args.prefer_manual_chapters)
        else:
            result = check(dest)
        summary = {k: v for k, v in result.items() if k not in
                   ('records', 'file_sha256', 'report_body_sha256', 'markdown_documents', 'warnings', 'reference_v2_files')}
        summary.update(output=str(dest), report=str(dest / '_audit' / 'report.json'))
        code = 0
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
        summary = {'status': 'failed', 'error': str(exc), 'database_write_performed': False}
        code = 1
    message = json.dumps(summary, ensure_ascii=False, indent=2)
    # Копия ВСЕГО вывода (включая ошибки) находится вне проверяемого корпуса.
    try:
        logs = root / 'V2/results/import_extracted_to_V2/logs'
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + command + '.log')
        log.write_text(message + '\n', encoding='utf-8')
        summary['console_log'] = str(log)
        message = json.dumps(summary, ensure_ascii=False, indent=2)
        log.write_text(message + '\n', encoding='utf-8')
    except OSError as exc:
        summary['log_write_error'] = str(exc)
        message = json.dumps(summary, ensure_ascii=False, indent=2)
        code = 1
    print(message)
    return code
