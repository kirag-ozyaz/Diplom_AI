#!/usr/bin/env python3
"""Independent local structural coverage check, not semantic or visual acceptance."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
LINK = re.compile(r'(!?)\[([^\[\]]*)\]\(([^)]+)\)')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def confined(root, value):
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    return path



def validate_normalization(original, edits, base):
    """Independent deletion-allowlist check; never trust the reported text.

    The full original remains in source Markdown. Every non-whitespace deletion
    must be one known control token, NOT a printed name, a standard number, a
    unit of measurement, URL, code or an arbitrary fragment of source text.
    """
    opening = re.compile(r'#M12293[ \t]+(?:[0-9]{1,10}[ \t]+){9}[0-9]{1,10}(?![0-9])|#M12291[ \t]+[0-9]{1,10}(?![0-9])')
    labels = re.compile(r'(?:СНиП|ГОСТ|СанПиН|ПУЭ|ПЭЭП|ПТБ|НПБ|Правил[а-я]*|приказ[а-я]*|ГЛ\.|глав[а-я]*|Раздел|Приложения)', re.I)
    protected = [(m.start(), m.end()) for pattern in
                 (r'```[\s\S]*?```', r'`[^`\n]*`', r'\]\([^\n)]*\)', r'https?://[^\s<>]+')
                 for m in re.finditer(pattern, original)]
    parts, cursor, open_positions = [], 0, set()
    for edit in edits:
        a, b = edit['start']-base, edit['end']-base
        if not (cursor <= a < b <= len(original)) or original[a:b] != edit['removed']:
            raise ValueError('Неверный диапазон/текст удаления маркера')
        if any(a < y and x < b for x, y in protected):
            raise ValueError('Очистка затронула URL или код')
        literal, kind = original[a:b], edit['kind']
        if kind == 'legacy_format':
            valid = literal in ('#G0', '#G1')
        elif kind == 'legacy_link_open':
            tail = original[b:]
            valid = opening.fullmatch(literal) is not None and (labels.match(tail) is not None or
                (literal.startswith('#M12293') and (not tail or tail.startswith('#S') or re.match(r'[ \t]*\n', tail))))
            if valid:
                open_positions.add(a)
        elif kind == 'legacy_link_close':
            nearest = original.rfind('#M', 0, a)
            valid = (literal == '#S' and nearest in open_positions
                     and '\n\n' not in original[nearest:a]
                     and original.find('#S', nearest) == a)
        else:
            valid = False
        if not valid:
            raise ValueError('Удалено неразрешённое содержимое, а не служебный маркер')
        parts.append(original[cursor:a]); cursor = b
    parts.append(original[cursor:])
    return ''.join(parts)

def check(root, report_path):
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    if report.get('schema_version') not in ('v2-preparation-1_4', 'v2-preparation-1_5'):
        raise ValueError('Неизвестная схема отчёта подготовки')
    modern = report['schema_version'] == 'v2-preparation-1_5'
    if modern and report.get('normalization_version') != 'legacy-markers-safe-1':
        raise ValueError('Неизвестная очистка маркеров')
    edit_count = 0
    source = confined(root, report['input'])
    target = confined(root, report['output'])
    if target != (root/'V2/data/chunked').resolve():
        raise ValueError('Неожиданная папка чанков')
    manifest_file = source/'extraction.json'
    if report['extraction_manifest_sha256']:
        if sha(manifest_file.read_bytes()) != report['extraction_manifest_sha256']:
            raise ValueError('Изменился extraction.json')
        records = json.loads(manifest_file.read_text(encoding='utf-8-sig'))['documents']
        manifest_docs = {r.get('document_id') or r['source_file'] for r in records}
        inventory_docs = {r['document'] for r in report['document_inventory']}
        if manifest_docs != inventory_docs or len(records) != len(report['document_inventory']):
            raise ValueError('Не совпадает набор документов')
    expected_files = {confined(root, f['path']) for f in report['files']}
    if expected_files != {p.resolve() for p in target.glob('*.jsonl')}:
        raise ValueError('Не совпадает набор JSONL')
    rows, by_document = {}, {}
    for file in sorted(expected_files):
        for line in file.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['id'] in rows:
                raise ValueError('Повтор ID чанка')
            rows[row['id']] = row
            by_document.setdefault(row['metadata']['Document'], set()).add(row['id'])
            if len(row['content'].encode('utf-8')) > 60000:
                raise ValueError('Превышен размер чанка')
    used, scopes = set(), set()
    for inv in report['document_inventory']:
        file = confined(source, inv['markdown'])
        text = file.read_text(encoding='utf-8-sig')
        if sha(text.encode('utf-8')) != inv['markdown_text_sha256']:
            raise ValueError('Изменился Markdown')
        cursor, doc_ids = 0, set()
        for span in inv['source_spans']:
            start, end = span['start'], span['end']
            if not (cursor <= start < end <= len(text)) or text[cursor:start].strip():
                raise ValueError('Пропуск или перекрытие исходного текста')
            original = text[start:end]
            cursor = end
            def rewrite(m):
                name = m.group(3).strip().strip('<>')
                if name.startswith(('http:', 'https:', 'data:', '#', 'mailto:')):
                    return m.group(0)
                src = confined(root, str(file.parent/name))
                relative = 'assets/' + sha(src.read_bytes()) + src.suffix.lower()
                copied = confined(target, relative)
                if not copied.is_file() or src.read_bytes() != copied.read_bytes():
                    raise ValueError('Ресурс не совпадает с исходным')
                return m.group(1)+'['+m.group(2)+']('+relative+')'
            edits = span['normalization_edits'] if modern else []
            normalized = validate_normalization(original, edits, start) if modern else original
            edit_count += len(edits)
            edits_hash = sha(json.dumps(edits, ensure_ascii=False, sort_keys=True).encode('utf-8'))
            expected = LINK.sub(rewrite, normalized)
            actual = []
            for i, cid in enumerate(span['chunks']):
                if cid in used:
                    raise ValueError('Чанк использован дважды')
                used.add(cid); doc_ids.add(cid)
                row = rows[cid]; meta = row['metadata']
                if modern and (meta.get('normalization_version') != report['normalization_version']
                               or meta.get('normalization_edits_sha256') != edits_hash):
                    raise ValueError('Не совпадает журнал очистки')
                if (meta['Document'] != inv['document'] or meta['Scope'] != span['scope']
                    or meta['Clause'] != span['clause'] or meta['fragment_kind'] != span['kind']
                    or meta['source_char_start'] != start or meta['source_char_end'] != end
                    or meta['source_span_sha256'] != sha(original.encode('utf-8'))
                    or meta['part_index'] != i+1 or meta['part_count'] != len(span['chunks'])
                    or meta['related_chunk_ids'] != span['chunks']
                    or meta['owner_review_status'] != 'structural_candidate_not_reviewed'):
                    raise ValueError('Не совпадают метаданные/границы')
                key = json.dumps([inv['document'], span['scope'], span['clause'] or span['kind']], ensure_ascii=False)
                if meta['ClauseKey'] != (key if span['clause'] else ''):
                    raise ValueError('Не совпадает контекст номера')
                expected_id = 'v2_' + sha((key+'\0'+str(i)+'\0'+row['content']).encode('utf-8'))[:40]
                if cid != expected_id:
                    raise ValueError('Неверный ID чанка')
                actual.append(row['content'])
            if re.sub(r'\s+', '', expected) != re.sub(r'\s+', '', ''.join(actual)):
                raise ValueError('Содержимое чанков не покрывает исходный фрагмент')
            if span['clause']:
                key = (inv['document'], span['scope'], span['clause'])
                if key in scopes:
                    raise ValueError('Номер повторён внутри одного контекста')
                scopes.add(key)
        if text[cursor:].strip() or doc_ids != by_document.get(inv['document'], set()):
            raise ValueError('Неполное покрытие документа')
        if len(doc_ids) != inv['chunks']:
            raise ValueError('Не совпадает число чанков документа')
    if modern and edit_count != report['removed_control_tokens']:
        raise ValueError('Не совпадает число удалённых маркеров')
    if used != set(rows) or len(rows) != report['chunks']:
        raise ValueError('Лишние или отсутствующие чанки')
    if (report['documents_input'] != report['documents_prepared']
        or report['documents_skipped'] != 0 or len(by_document) != report['documents_input']):
        raise ValueError('Документы пропущены')
    return {'status': 'technical_coverage_passed', 'documents': len(by_document),
            'chunks': len(rows), 'documents_skipped': 0,
            'semantic_or_visual_approval': False, 'database_write_performed': False,
            'normalization_deletions_verified': modern, 'removed_control_tokens': edit_count}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', help='Optional preparation.json path relative to project root')
    args = p.parse_args(argv)
    try:
        root = V2.parent.resolve()
        if args.report:
            report_path = confined(root, args.report)
        else:
            folders = [p for p in (V2/'results/retrieval').glob('preparation_*')
                       if p.is_dir() and re.fullmatch(r'preparation_\d{8}_\d{6}_\d{6}', p.name)]
            if not folders:
                raise ValueError('Нет результатов prepare_chunks.py')
            report_path = max(folders).joinpath('preparation.json')
        result = check(root, report_path)
        result['preparation_report'] = str(report_path)
        output = report_path.parent/'coverage_check.json'
        # A check is repeatable and keeps its previous results in distinct files.
        from datetime import datetime
        if output.exists():
            output = report_path.parent/('coverage_check_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
        with output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps({'report': str(output), **result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('COVERAGE ERROR: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
