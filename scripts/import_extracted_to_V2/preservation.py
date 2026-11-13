"""Изолированные функции сохранности нового Markdown-импортёра.
Старый convert_chunked_V0_to_V2/convert.py и его core.py не изменяются.
Этот модуль не запускают отдельно: команды находятся в prepare.py, check.py, merge.py.
"""
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




