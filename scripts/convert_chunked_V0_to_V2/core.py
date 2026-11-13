"""Standalone, standard-library-only V0 import and candidate merge. Never writes a DB."""
import argparse
import collections
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlsplit

VERSION = 'v0-import-candidate-1'
REFERENCE = re.compile(r'!?\[[^\]\n]*\]\(([^)\n]+)\)|<img\b[^>]*?src=[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
HIERARCHICAL = re.compile(r'\d+(?:\.\d+){2,}')
TRACE_FIELDS = ('source_char_start', 'source_char_end', 'source_span_sha256')


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def sha(value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def within(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    require(path.is_relative_to(root), f'Путь вне разрешённой папки: {path}')
    return path


def project_path(root, value):
    return within(root / value, root)


def basename(value):
    return PurePosixPath(str(value).replace('\\', '/')).stem.casefold()


def read_rows(root):
    root = Path(root).resolve()
    require(root.is_dir(), f'Нет папки: {root}')
    files = sorted(root.glob('*.jsonl'))
    require(files, f'Нет JSONL непосредственно в папке: {root}')
    rows, seen = [], set()
    for path in files:
        within(path, root)
        file_digest = sha(path.read_bytes())
        for line, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except Exception as exc:
                raise ValueError(f'Неверный JSON: {path.name}:{line}: {exc}') from exc
            require(isinstance(row, dict), f'Не объект: {path.name}:{line}')
            require(isinstance(row.get('id'), str) and row['id'], f'Нет id: {path.name}:{line}')
            require(row['id'] not in seen, f'Повтор id: {row["id"]}')
            seen.add(row['id'])
            require(isinstance(row.get('content'), str) and row['content'].strip(), f'Нет content: {row["id"]}')
            require(isinstance(row.get('metadata'), dict), f'Нет metadata: {row["id"]}')
            rows.append({'row': row, 'file': path.name, 'line': line,
                         'file_sha256': file_digest})
    require(rows, 'Пустой корпус')
    return rows


def references(text):
    for m in REFERENCE.finditer(text):
        group = 1 if m.group(1) is not None else 2
        raw = m.group(group)
        # Markdown titles and complex/escaped destinations must not be silently guessed.
        target = raw.strip()
        if target.startswith('<') and target.endswith('>'):
            target = target[1:-1]
        require(not re.search(r'\s+[\"\x27]', target), f'Нужна явная обработка ссылки с title: {raw}')
        yield m.start(group), m.end(group), raw, target


def external_target(target):
    require(not re.match(r'^[A-Za-z]:[/\\]', target), f'Абсолютная Windows-ссылка не переносится: {target}')
    if target.startswith('#'):
        return True
    scheme = urlsplit(target).scheme.casefold()
    if scheme:
        require(scheme in ('http', 'https', 'mailto', 'data'), f'Неподдержанная схема ресурса: {scheme}')
        return True
    return False


def resource_path(root, filename, target):
    target = unquote(target)
    require(not re.match(r'^[A-Za-z]:|^[/\\]', target), f'Абсолютная ссылка не переносится: {target}')
    require('\\' not in target, f'Исправьте обратные слеши в Markdown-ссылке: {target}')
    target = urlsplit(target).path
    require(target, 'Пустой локальный ресурс')
    p = within(root / filename, root).parent / target
    p = within(p, root)
    require(p.is_file(), f'Не найден ресурс: {p}')
    return p


def asset_target(path):
    suffix = path.suffix.lower()
    require(re.fullmatch(r'\.[a-z0-9]{1,10}', suffix) is not None, f'Неподдержанное расширение ресурса: {path.name}')
    return 'assets/' + sha(path.read_bytes()) + suffix


def relink(text, root, filename, output):
    edits, external = [], []
    for start, end, raw, target in references(text):
        if external_target(target):
            external.append(target)
            continue
        path = resource_path(root, filename, target)
        dest = asset_target(path)
        out = output / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            shutil.copyfile(path, out)
        require(sha(path.read_bytes()) == sha(out.read_bytes()), 'Не совпал хеш копии ресурса')
        # Fragments/queries are preserved, not silently removed.
        parsed = urlsplit(target)
        if parsed.query:
            dest += '?' + parsed.query
        if parsed.fragment:
            dest += '#' + parsed.fragment
        edits.append({'start': start, 'end': end, 'before': raw, 'after': dest,
                      'resource_sha256': sha(path.read_bytes())})
    return apply_edits(text, edits), edits, external


def apply_edits(text, edits):
    previous = len(text) + 1
    for e in reversed(edits):
        require(0 <= e['start'] <= e['end'] < previous, 'Пересекающиеся правки ссылок')
        require(text[e['start']:e['end']] == e['before'], 'Не совпала исходная ссылка')
        text = text[:e['start']] + e['after'] + text[e['end']:]
        previous = e['start']
    return text


def split_lossless(text, limit=60000):
    parts = []
    while len(text.encode('utf-8')) > limit:
        lo, hi = 1, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(text[:mid].encode('utf-8')) <= limit:
                lo = mid
            else:
                hi = mid - 1
        # Prefer a paragraph boundary without deleting a single character.
        cut = text.rfind('\n\n', 0, lo)
        cut = cut + 2 if cut > lo // 2 else lo
        parts.append(text[:cut])
        text = text[cut:]
    if text:
        parts.append(text)
    return parts


def snapshot(rows, root, stage, side, include_prior_audit=False):
    target = stage / '_audit' / 'inputs' / side
    target.mkdir(parents=True, exist_ok=True)
    for name in sorted({x['file'] for x in rows}):
        shutil.copyfile(root / name, target / name)
    for item in rows:
        for _, _, _, ref in references(item['row']['content']):
            if external_target(ref):
                continue
            src = resource_path(root, item['file'], ref)
            dest = target / src.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copyfile(src, dest)
    if include_prior_audit and (root / '_audit').exists():
        shutil.copytree(root / '_audit', target / '_audit')
    return target


def document_index(v2):
    docs, scopes = collections.defaultdict(set), collections.defaultdict(set)
    for item in v2:
        meta = item['row']['metadata']
        doc = meta.get('source_file')
        require(isinstance(doc, str) and doc, 'У V2 нет source_file')
        docs[basename(doc)].add(doc)
        if meta.get('Clause'):
            scopes[(doc, str(meta['Clause']).strip())].add(meta.get('Scope', ''))
    return docs, scopes


def converted_meta(row, doc, scopes, item):
    old = row['metadata']
    clause = str(old.get('Clause') or '').strip()
    variants = scopes.get((doc, clause), set()) if clause else set()
    # A scope from the reference corpus is a candidate association, not semantic approval.
    matched = len(variants) == 1 and bool(next(iter(variants)))
    scope = next(iter(variants)) if matched else 'legacy_unresolved_' + sha(row['id'])[:12]
    kind = 'clause' if HIERARCHICAL.fullmatch(clause) else 'legacy_unassigned'
    if kind != 'clause':
        # Do not turn literal short/repeated numbers into an invented unique own clause.
        clause = ''
        matched = False
        scope = 'legacy_unassigned_' + sha(row['id'])[:12]
    meta = {'Document': doc, 'source_file': doc,
            'Clause': clause, 'Scope': scope,
            'ClauseKey': json.dumps([doc, scope, clause], ensure_ascii=False) if clause else '',
            'Chapter': old.get('Chapter') or ('.'.join(clause.split('.')[:2]) if clause else ''),
            'Section': old.get('Section', ''), 'Paragraph': old.get('Paragraph', ''),
            'section_heading': old.get('Paragraph', ''), 'block_title': '',
            'fragment_kind': kind, 'numbering_scheme': 'hierarchical' if clause else 'unresolved',
            'scope_resolution': 'matched_scope_candidate' if matched else 'requires_review',
            'owner_review_status': 'manual_import_not_reviewed',
            'table_ownership': 'requires_review', 'reference_resolution': 'not_performed',
            'references': [], 'table_ids': [], 'chunking_version': VERSION,
            'document_version_sha256': None,
            'source_char_start': None, 'source_char_end': None, 'source_span_sha256': None,
            'extraction_warnings': ['manual_import_not_raw_extraction', 'manual_formulas_tables_and_boundaries_require_review'],
            'legacy_metadata': copy.deepcopy(old),
            'origin_provenance': {'kind': 'legacy_jsonl', 'source_id': row['id'],
                'source_jsonl': item['file'], 'source_line': item['line'],
                'source_jsonl_sha256': item['file_sha256'],
                'source_row_sha256': sha(stable(row)), 'source_content_sha256': sha(row['content']),
                'source_created_at': row.get('created_at'),
                'note': 'source_file is a logical document association; text provenance is the archived JSONL, not DOCX offsets'}}
    return meta


def emitted_parts(row, meta, text, identity):
    pieces = split_lossless(text)
    ids = ['v2_' + sha(stable([VERSION, identity, i, piece]))[:40] for i, piece in enumerate(pieces, 1)]
    out = []
    for i, (cid, piece) in enumerate(zip(ids, pieces), 1):
        m = copy.deepcopy(meta)
        m.update(part_index=i, part_count=len(pieces), related_chunk_ids=ids,
                 contains_tables=('|' in piece), contains_images=('![' in piece or '<img' in piece.lower()))
        out.append({'id': cid, 'content': piece, 'metadata': m})
    return out


def add_record(stage, source_side, item, output_rows, edits, external, action):
    return {'side': source_side, 'source_file': item['file'], 'source_line': item['line'],
            'source_id': item['row']['id'], 'source_row_sha256': sha(stable(item['row'])),
            'output_ids': [r['id'] for r in output_rows], 'link_edits': edits,
            'external_resources': external, 'action': action}


def save_rows(stage, rows):
    by_doc = collections.defaultdict(list)
    for row in rows:
        by_doc[row['metadata']['source_file']].append(row)
    for doc, group in sorted(by_doc.items()):
        path = stage / (sha(doc)[:16] + '.chunked.jsonl')
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in group), encoding='utf-8')


def finish(stage, report, rows):
    save_rows(stage, rows)
    report.update(schema_version=VERSION, chunks=len(rows), documents=len({r['metadata']['source_file'] for r in rows}),
                  database_write_performed=False, ready_for_final_scoring=False,
                  semantic_or_visual_approval=False, qrels_rebuild_required=True)
    report['file_sha256'] = {p.relative_to(stage).as_posix(): sha(p.read_bytes())
        for p in sorted(stage.rglob('*')) if p.is_file()}
    report['report_body_sha256'] = sha(stable(report))
    write_json(stage / '_audit' / 'report.json', report)
    return report


def publish(output, inputs, builder):
    output = output.resolve()
    for root in inputs:
        root = root.resolve()
        require(not output.is_relative_to(root) and not root.is_relative_to(output), 'Выход и вход не должны пересекаться')
    require(not output.exists(), f'Папка уже существует; выберите новую, исходники не перезаписываются: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.v0_build_', dir=output.parent) as td:
        stage = Path(td) / 'result'
        stage.mkdir()
        result = builder(stage)
        require(not output.exists(), f'Выход появился во время выполнения: {output}')
        os.rename(stage, output)
    return result


def convert(input_root, v2_root, output, chapters=None, mapping=None):
    old, ref = read_rows(input_root), read_rows(v2_root)
    docs, scopes = document_index(ref)
    mapping = mapping or {}
    if chapters:
        wanted = set(chapters)
        old = [x for x in old if basename(x['row']['metadata'].get('source_file', '')) in wanted]
        require(old and wanted <= {basename(x['row']['metadata'].get('source_file', '')) for x in old}, 'Не все выбранные главы найдены')
    selected_files = {x['file'] for x in old}
    if chapters:
        require(all(basename(x['row']['metadata'].get('source_file', '')) in set(chapters) for x in read_rows(input_root) if x['file'] in selected_files), 'Выбор глав не поддерживает смешанные документы в одном JSONL; разделите файлы явно')
    known_docs = {d for ds in docs.values() for d in ds}
    resolved = {}
    for item in old:
        src = item['row']['metadata'].get('source_file', '')
        explicit = mapping.get(src) or mapping.get(item['file'])
        choices = {explicit} if explicit else docs.get(basename(src), set())
        require(len(choices) == 1, f'Неоднозначный/неизвестный документ {src!r}; укажите --document-map')
        doc = next(iter(choices))
        require(doc in known_docs, f'Документа из карты нет в V2: {doc}')
        resolved[item['row']['id']] = doc
    def build(stage):
        snapshot(old, input_root, stage, 'v0')
        rows, records, warnings = [], [], []
        for item in old:
            row = item['row']
            text, edits, external = relink(row['content'], input_root, item['file'], stage)
            meta = converted_meta(row, resolved[row['id']], scopes, item)
            parts = emitted_parts(row, meta, text, ['convert', item['file'], item['line'], sha(stable(row)), meta])
            rows += parts
            records.append(add_record(stage, 'v0', item, parts, edits, external, 'converted'))
            if re.search(r'(?<!\$)\$\$[^$\n]+\$(?!\$)', text):
                warnings.append({'id': row['id'], 'code': 'possible_math_delimiter_error'})
        return finish(stage, {'operation': 'convert', 'status': 'manual_import_candidates_require_review',
            'input_rows': len(old), 'input_documents': len({x['file'] for x in old}),
            'reference_v2_files': {x['file']: x['file_sha256'] for x in ref},
            'selected_chapters': chapters or 'all_input_jsonl', 'records': records, 'warnings': warnings,
            'scope_note': 'V2 scopes matched by document and own clause are candidates, not content/ownership approval'}, rows)
    return publish(output, [input_root, v2_root], build)


def group_rows(rows):
    groups = collections.OrderedDict()
    for item in rows:
        meta = item['row']['metadata']
        doc = meta.get('source_file')
        require(doc, 'Нет canonical source_file')
        clause = str(meta.get('Clause') or '').strip()
        scope = str(meta.get('Scope') or '')
        key = (doc, scope, clause) if clause else (doc, '@unassigned', item['row']['id'])
        groups.setdefault(key, []).append(item)
    for key, group in groups.items():
        if key[1] == '@unassigned':
            continue
        counts = {x['row']['metadata'].get('part_count', 1) for x in group}
        indices = [x['row']['metadata'].get('part_index', 1) for x in group]
        require(len(counts) == 1 and len(group) == next(iter(counts)) and sorted(indices) == list(range(1, len(group)+1)),
                f'Неоднозначные/неполные части собственного пункта: {key}')
        group.sort(key=lambda x: x['row']['metadata'].get('part_index', 1))
    return groups


def merge(v0_root, v2_root, output, apply=False, prefer_v0=None, prefer_v2=False):
    require(not (prefer_v0 and prefer_v2), 'Выберите одну политику приоритета')
    require(not apply or prefer_v0 or prefer_v2, '--apply требует явного --prefer-v0-chapters или --prefer-v2')
    # The importer audit must be intact before a converted corpus may be merged.
    check(v0_root)
    old, new = read_rows(v0_root), read_rows(v2_root)
    reference = read_json(v0_root / '_audit' / 'report.json').get('reference_v2_files')
    require(reference is not None and reference == {x['file']: x['file_sha256'] for x in new}, 'Набор V2 изменился после конвертации V0. Повторите конвертацию в новую папку')
    a, b = group_rows(old), group_rows(new)
    require(not ({r['row']['id'] for r in old} & {r['row']['id'] for r in new}), 'Пересечение ID двух входов')
    preferred = set(prefer_v0 or [])
    require(not preferred or preferred <= {basename(x['row']['metadata']['source_file']) for x in old}, 'В V0 нет запрошенных глав приоритета')
    selections, conflicts, dispositions = [], [], []
    for key, group in b.items():
        other = a.get(key)
        side, chosen, reason = 'v2', group, 'v2_only'
        if other:
            same = ''.join(x['row']['content'] for x in other) == ''.join(x['row']['content'] for x in group)
            want_old = basename(key[0]) in preferred
            side, chosen = ('v0', other) if want_old else ('v2', group)
            reason = 'equal_text' if same else 'explicit_priority_candidate'
            if not same:
                conflicts.append({'document': key[0], 'scope': key[1], 'clause': key[2],
                    'v0_ids': [x['row']['id'] for x in other], 'v2_ids': [x['row']['id'] for x in group],
                    'selected_candidate': side if apply else None, 'semantic_approval': False,
                    'v0_text_sha256': sha(''.join(x['row']['content'] for x in other)),
                    'v2_text_sha256': sha(''.join(x['row']['content'] for x in group))})
            discarded = group if side == 'v0' else other
            discarded_side = 'v2' if side == 'v0' else 'v0'
            dispositions += [(discarded_side, x, 'archived_alternative') for x in discarded]
        selections.append((key, side, chosen, reason))
    for key, group in a.items():
        if key in b:
            continue
        if key[1] == '@unassigned':
            dispositions += [('v0', x, 'archived_unassigned_requires_review') for x in group]
        else:
            selections.append((key, 'v0', group, 'v0_only_requires_review'))
    def build(stage):
        snapshot(old, v0_root, stage, 'v0', include_prior_audit=True)
        snapshot(new, v2_root, stage, 'v2')
        write_json(stage / '_audit' / 'conflicts.json', conflicts)
        rows, records = [], []
        for _, side, group, reason in selections:
            for item in group:
                if not apply:
                    dispositions.append((side, item, 'planned_not_emitted'))
                    continue
                source = item['row']
                root = v0_root if side == 'v0' else v2_root
                text, edits, external = relink(source['content'], root, item['file'], stage)
                meta = copy.deepcopy(source['metadata'])
                meta['parent_source_trace'] = {f: meta.get(f) for f in TRACE_FIELDS}
                for f in TRACE_FIELDS:
                    meta[f] = None
                meta['owner_review_status'] = 'merged_candidate_not_reviewed'
                meta['chunking_version'] = 'v0-v2-merge-candidate-1'
                meta['merge_provenance'] = {'side': side, 'source_id': source['id'],
                    'source_row_sha256': sha(stable(source)), 'selection_reason': reason,
                    'content_changes': 'local_resource_destinations_only'}
                # Parts are re-grouped below; no stale related IDs are copied.
                parts = emitted_parts(source, meta, text, ['merge', side, source['id'], sha(stable(source))])
                rows += parts
                records.append(add_record(stage, side, item, parts, edits, external, reason))
        # Entire selected clause, including all its parts, gets one valid relation group.
        grouped = collections.OrderedDict()
        for row in rows:
            meta = row['metadata']
            key = (meta['source_file'], meta.get('Scope'), meta.get('Clause')) if meta.get('Clause') else ('@', row['id'])
            grouped.setdefault(key, []).append(row)
        for group in grouped.values():
            ids = [r['id'] for r in group]
            for index, row in enumerate(group, 1):
                row['metadata'].update(part_index=index, part_count=len(group), related_chunk_ids=ids)
        records += [add_record(stage, side, item, [], [], [], action) for side, item, action in dispositions]
        return finish(stage, {'operation': 'merge', 'status': 'merged_candidates_require_review' if apply else 'plan_only_no_active_chunks',
            'input_v0_rows': len(old), 'input_v2_rows': len(new), 'conflicts': len(conflicts),
            'prefer_v0_chapters': sorted(preferred), 'prefer_v2': prefer_v2,
            'records': records, 'archived_rows': sum(not x['output_ids'] for x in records),
            'note': 'All input rows/assets are archived. Priority selects a candidate, never confirms normative correctness. Unassigned V0 blocks stay in archive for review.'}, rows)
    return publish(output, [v0_root, v2_root], build)


def check(root):
    root = Path(root).resolve()
    report = read_json(root / '_audit' / 'report.json')
    expected = report.pop('report_body_sha256')
    require(sha(stable(report)) == expected, 'Изменён отчёт')
    for rel, digest in report['file_sha256'].items():
        path = within(root / rel, root)
        require(path.is_file() and sha(path.read_bytes()) == digest, f'Изменён/исчез файл: {rel}')
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual_files == set(report['file_sha256']) | {'_audit/report.json'}, 'Лишние или недостающие файлы в наборе')
    rows = read_rows(root) if report['chunks'] else []
    by_id = {x['row']['id']: x['row'] for x in rows}
    require(len(rows) == report['chunks'], 'Не совпало число чанков')
    # Re-read immutable input snapshots and replay only recorded link substitutions.
    snapshots = {}
    for side in {r['side'] for r in report['records']}:
        snapshot_root = root / '_audit' / 'inputs' / side
        data = read_rows(snapshot_root)
        snapshots[side] = {(x['file'], x['line']): x['row'] for x in data}
    seen_outputs, seen_inputs = set(), set()
    for record in report['records']:
        source_key = (record['side'], record['source_file'], record['source_line'])
        require(source_key not in seen_inputs, 'Исходная строка учтена дважды')
        seen_inputs.add(source_key)
        source = snapshots[record['side']][(record['source_file'], record['source_line'])]
        require(source['id'] == record['source_id'] and sha(stable(source)) == record['source_row_sha256'], 'Не совпал снимок исходной строки')
        if record['output_ids']:
            require(not (seen_outputs & set(record['output_ids'])), 'Выходная строка учтена дважды')
            seen_outputs.update(record['output_ids'])
            require(all(cid in by_id for cid in record['output_ids']), 'Потеряна часть чанка')
            expected_content = apply_edits(source['content'], record['link_edits'])
            actual_content = ''.join(by_id[cid]['content'] for cid in record['output_ids'])
            require(expected_content == actual_content, f'Текст потерян/изменён: {source["id"]}')
    require(seen_outputs == set(by_id), 'Не все выходные чанки имеют происхождение')
    expected_inputs = {(side, f, line) for side, data in snapshots.items() for f, line in data}
    require(expected_inputs == seen_inputs, 'Не все входные строки сохранены или учтены')
    group_rows(rows) if rows else None
    for item in rows:
        row, meta = item['row'], item['row']['metadata']
        require(len(row['id'].encode()) <= 4096 and len(row['content'].encode()) <= 60000, 'Превышен лимит ID/content')
        require(len(json.dumps(meta, ensure_ascii=False).encode()) <= 60000, 'Превышен лимит metadata')
        require(meta.get('owner_review_status') != 'reviewed', 'Конвертер не может утверждать reviewed')
        require(all(meta.get(f) is None for f in TRACE_FIELDS), 'Нельзя выдавать чужие offsets/span за происхождение текущего текста')
        for _, _, _, ref in references(row['content']):
            if external_target(ref):
                continue
            resource_path(root, item['file'], ref)
        require(all(cid in by_id for cid in meta.get('related_chunk_ids', [])), 'Битая связь related_chunk_ids')
    return {'status': 'technical_preservation_passed', 'chunks': len(rows),
            'input_rows_accounted': len(seen_inputs), 'text_and_asset_integrity_verified': True,
            'database_write_performed': False, 'semantic_or_visual_approval': False,
            'ready_for_final_scoring': False}


def main(command=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[2]))
    if command is None:
        parser.add_argument('command', choices=['convert', 'merge', 'check'])
    parser.add_argument('--input', default='data/chunked')
    parser.add_argument('--v2', default='V2/data/chunked')
    parser.add_argument('--v0', default='data/chunked_V0')
    parser.add_argument('--output')
    parser.add_argument('--chapters', nargs='+')
    parser.add_argument('--document-map')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--prefer-v0-chapters', nargs='+')
    parser.add_argument('--prefer-v2', action='store_true')
    args = parser.parse_args()
    command = command or args.command
    root = Path(args.project_root).resolve()
    try:
        if command == 'convert':
            dest = project_path(root, args.output or 'data/chunked_V0')
            result = convert(project_path(root, args.input), project_path(root, args.v2), dest,
                args.chapters, read_json(project_path(root, args.document_map)) if args.document_map else None)
        elif command == 'merge':
            dest = project_path(root, args.output or ('V2/data/chunked_merged' if args.apply else 'V2/results/convert_chunked_V0_to_V2/plan'))
            result = merge(project_path(root, args.v0), project_path(root, args.v2), dest,
                args.apply, args.prefer_v0_chapters, args.prefer_v2)
        else:
            dest = project_path(root, args.output or args.v0)
            result = check(dest)
        summary = {k: v for k, v in result.items() if k not in ('records', 'file_sha256', 'warnings', 'reference_v2_files')}
        if 'report_body_sha256' in summary:
            summary.pop('report_body_sha256')
        summary['output'] = str(dest)
        summary['report'] = str(dest / '_audit' / 'report.json')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc), 'database_write_performed': False}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
