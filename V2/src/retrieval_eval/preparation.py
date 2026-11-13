"""V2 patch 1_5: loss-aware structural chunk candidates; no semantic approval."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from .common import ensure, inside, path_in

VERSION = 'v2-markdown-scoped-1_5'
HIER = re.compile(r'^\s*(?:#{1,6}\s*)?(\d+\.\d+\.\d+(?:\.\d+)*)(?:\.)?\s+(?=\S)')
SINGLE = re.compile(r'^\s*(?:#{1,6}\s*)?(\d+)\.\s+(?=\S)')
HEADER = re.compile(r'^\s*(?:#{1,6}\s+|(?:[IVXLCDM]+)\.\s+|ПРИЛОЖЕНИ[ЕЯ](?:\s+|$))', re.I)
LINK = re.compile(r'(!?)\[([^\[\]]*)\]\(([^)]+)\)')


def sha(data):
    return hashlib.sha256(data).hexdigest()


# Only observed legacy control forms are recognized. Numeric-only labels are
# ambiguous (the numeric ID and the printed standard number have no delimiter).
LEGACY_OPEN = re.compile(r'#M12293[ \t]+(?:[0-9]{1,10}[ \t]+){9}[0-9]{1,10}(?![0-9])|#M12291[ \t]+[0-9]{1,10}(?![0-9])')
LEGACY_LABEL = re.compile(r'(?:СНиП|ГОСТ|СанПиН|ПУЭ|ПЭЭП|ПТБ|НПБ|Правил[а-я]*|приказ[а-я]*|ГЛ\.|глав[а-я]*|Раздел|Приложения)', re.I)
LEGACY_TOKEN = re.compile(r'#M[0-9]*|#S|#G[0-9]?')
NORMALIZATION_VERSION = 'legacy-markers-safe-1'


def normalize_legacy_markup(text):
    """Delete only whitelisted control tokens; retain original offset ledger.

    A digit-only link label cannot be distinguished from its resource ID, so
    preserve that entire ambiguous link and report it rather than eat a number.
    """
    edits = []
    # Markdown destinations and code are not legacy prose and stay byte-for-byte.
    protected = [(m.start(), m.end()) for pattern in
                 (r'```[\s\S]*?```', r'`[^`\n]*`', r'\]\([^\n)]*\)', r'https?://[^\s<>]+')
                 for m in re.finditer(pattern, text)]
    def blocked(a, b):
        return any(a < y and x < b for x, y in protected)
    for m in LEGACY_OPEN.finditer(text):
        if blocked(m.start(), m.end()):
            continue
        tail = text[m.end():]
        starts_word = bool(LEGACY_LABEL.match(tail))
        empty_long_anchor = m.group().startswith('#M12293') and (
            not tail or tail.startswith('#S') or bool(re.match(r'[ \t]*\n', tail)))
        if not (starts_word or empty_long_anchor):
            continue
        edits.append({'start': m.start(), 'end': m.end(), 'removed': m.group(), 'kind': 'legacy_link_open'})
        # A closing token belongs to this opening only within the same paragraph
        # and before the next opening. Do not steal the end of another link.
        end = len(text)
        for delim in ('\n\n', '#M'):
            j = text.find(delim, m.end())
            if j >= 0:
                end = min(end, j)
        close = text.find('#S', m.end(), end)
        if close >= 0 and not blocked(close, close+2):
            edits.append({'start': close, 'end': close+2, 'removed': '#S', 'kind': 'legacy_link_close'})
    # EXACTLY two characters after '#': #G01) is #G0 + the useful list item 1).
    for m in re.finditer(r'#G[01]', text):
        if not blocked(m.start(), m.end()):
            edits.append({'start': m.start(), 'end': m.end(), 'removed': m.group(), 'kind': 'legacy_format'})
    edits.sort(key=lambda e: e['start'])
    out, cursor = [], 0
    for e in edits:
        ensure(e['start'] >= cursor, 'Перекрытие правок очистки')
        out.append(text[cursor:e['start']]); cursor = e['end']
    out.append(text[cursor:])
    unresolved = [{'offset': m.start(), 'excerpt': text[m.start():m.start()+160]}
                  for m in LEGACY_TOKEN.finditer(text)
                  if not blocked(m.start(), m.end()) and not any(e['start'] <= m.start() < e['end'] for e in edits)]
    return ''.join(out), edits, unresolved


def boundary_view(line):
    # Detection may use the safe cleaned label, but offsets always address the
    # untouched Markdown. No input file is edited in place.
    return normalize_legacy_markup(line)[0].strip()


def segment_document(text):
    """Partition every source character; numbered-list ownership stays unreviewed."""
    lines = text.splitlines(keepends=True)
    hierarchical = any(HIER.match(boundary_view(line)) for line in lines)
    events, offset = [], 0
    for line_index, line in enumerate(lines):
        stripped = boundary_view(line)
        match = HIER.match(stripped) if hierarchical else SINGLE.match(stripped)
        if match:
            events.append((offset, 'clause', match.group(1), stripped))
        elif HEADER.match(stripped) and stripped:
            events.append((offset, 'heading', '', stripped))
        elif stripped in ('Министр', 'УТВЕРЖДЕНЫ'):
            events.append((offset, 'service_block', '', stripped))
        elif stripped == 'ПРАВИЛА ТЕХНИЧЕСКОЙ ЭКСПЛУАТАЦИИ ЭЛЕКТРОУСТАНОВОК ПОТРЕБИТЕЛЕЙ ЭЛЕКТРИЧЕСКОЙ ЭНЕРГИИ':
            events.append((offset, 'heading', '', stripped))
        elif stripped == 'Коэффициенты перегрузки':
            following = next((boundary_view(x) for x in lines[line_index+1:] if boundary_view(x)), '')
            if following.startswith('|'):
                events.append((offset, 'table_block', '', stripped))
        offset += len(line)
    if not events or events[0][0] != 0:
        events.insert(0, (0, 'unassigned', '', ''))
    units, heading, heading_index, run_index, seen, previous = [], '', 0, 0, set(), None
    block_index = 0
    notices = []
    for i, (start, kind, number, title) in enumerate(events):
        end = events[i+1][0] if i+1 < len(events) else len(text)
        if kind == 'heading':
            heading = title
            heading_index += 1
            run_index, seen, previous = 0, set(), None
        if kind == 'clause':
            numeric = tuple(map(int, number.split('.')))
            if number in seen or (previous is not None and numeric <= previous):
                run_index += 1
                seen = set()
                notices.append({'problem': 'numbering_restart_or_repeat_requires_review',
                                'number': number, 'heading': heading, 'offset': start})
            seen.add(number)
            previous = numeric
        scope = f'section_{heading_index:04d}_run_{run_index:04d}'
        if kind in ('service_block', 'table_block'):
            block_index += 1
            scope += f'_block_{block_index:04d}'
            notices.append({'problem': 'detached_nonclause_block_requires_review',
                            'kind': kind, 'title': title, 'offset': start})
        units.append({'start': start, 'end': end, 'text': text[start:end],
                      'kind': kind, 'clause': number, 'scope': scope, 'heading': heading, 'block_title': title if kind != 'clause' else '',
                      'numbering_scheme': 'hierarchical' if hierarchical else 'single_level_candidate'})
    ensure(''.join(u['text'] for u in units) == text, 'Нарушено покрытие текста')
    if not any(u['kind'] == 'clause' for u in units):
        notices.append({'problem': 'no_numbered_clause_preserved_as_unassigned_fragments'})
    if not hierarchical and any(u['kind'] == 'clause' for u in units):
        notices.append({'problem': 'single_level_numbering_or_list_requires_owner_review'})
    return units, notices


def split_text(value, max_bytes):
    """Never cut a paragraph, table row or resource link in half."""
    parts, acc = [], ''
    for block in re.split(r'\n\s*\n', value.strip()):
        ensure(len(block.encode('utf-8')) <= max_bytes,
               'Неделимый абзац/таблица превышает max_chunk_bytes; требуется явное разбиение без обрезки')
        candidate = acc + ('\n\n' if acc else '') + block
        if len(candidate.encode('utf-8')) > max_bytes:
            parts.append(acc)
            acc = block
        else:
            acc = candidate
    if acc:
        parts.append(acc)
    return parts


def input_documents(config, source):
    """Manifest is authoritative; missing or additional Markdown is never hidden."""
    manifest_path = source / 'extraction.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        ensure(manifest.get('schema_version') == 'v2-documents-1', 'Неизвестная схема extraction.json')
        records = manifest['documents']
        ensure(isinstance(records, list) and records, 'Пустой список извлечения')
        items, seen_files, seen_documents = [], set(), set()
        for rec in records:
            file = path_in(config['_root'], rec['markdown'])
            ensure(inside(file, source) and file.is_file(), 'Нет Markdown из extraction.json: ' + str(file))
            ensure(file not in seen_files, 'Повтор Markdown в extraction.json')
            document = rec.get('document_id') or rec['source_file']
            ensure(document not in seen_documents, 'Повтор document_id в extraction.json')
            seen_files.add(file); seen_documents.add(document)
            sidecar = file.parent / 'source.json'
            ensure(sidecar.is_file(), 'Нет source.json: ' + str(file))
            info = json.loads(sidecar.read_text(encoding='utf-8-sig'))
            for key in ('source_file', 'source_sha256', 'document_id', 'markdown'):
                ensure(info.get(key) == rec.get(key), 'source.json не совпадает с extraction.json: ' + key)
            items.append((file, info))
        discovered = {p.resolve() for p in source.rglob('*.md')}
        ensure(discovered == seen_files, 'Набор Markdown не совпадает с extraction.json; лишние файлы не пропускаются')
        return items, sha(manifest_path.read_bytes())
    files = sorted(source.rglob('*.md'))
    ensure(files, 'Нет Markdown')
    items = []
    for file in files:
        info_path = file.parent / 'source.json'
        info = json.loads(info_path.read_text(encoding='utf-8-sig')) if info_path.is_file() else {}
        items.append((file, info))
    return items, None


def prepare_markdown(config, input_path):
    source = path_in(config['_root'], input_path)
    ensure(source.is_dir(), 'Нужна папка подготовленных Markdown')
    target = config['_v2'] / 'data/chunked'
    ensure(inside(target, config['_v2']), 'Выходная папка вне V2')
    ensure(not target.exists() or (target.is_dir() and not any(target.iterdir())),
           'V2/data/chunked не пуста. Существующие чанки не перезаписываются: сначала сохраните их отдельно.')
    ensure(not inside(source, target) and not inside(target, source), 'Источник и выход перекрываются')
    max_bytes = int(config.get('max_chunk_bytes', 60000))
    ensure(1024 <= max_bytes <= 60000, 'max_chunk_bytes должен быть от 1024 до 60000')
    items, manifest_sha = input_documents(config, source)
    outputs, warnings, copies, inventory, used_ids = [], [], {}, [], set()
    removed_tokens, ambiguous_tokens = 0, 0
    for file, info in items:
        ensure(inside(file, source), 'Ссылка Markdown вне источника')
        text = file.read_text(encoding='utf-8-sig')
        ensure(text.strip(), 'Пустой Markdown; документ не пропущен: ' + str(file))
        stem = file.relative_to(source).as_posix()
        document = info.get('document_id', stem)
        source_file = info.get('source_file', file.relative_to(config['_root']).as_posix())
        units, notices = segment_document(text)
        warnings.extend({'document': document, **n} for n in notices)
        entries, source_spans = [], []
        for unit in units:
            if not unit['text'].strip():
                continue
            clause, scope = unit['clause'], unit['scope']
            def resource_link(m):
                name = m.group(3).strip().strip('<>')
                if name.startswith(('http:', 'https:', 'data:', '#', 'mailto:')):
                    warnings.append({'document': document, 'problem': 'external_or_anchor_link_not_fetched', 'path': name})
                    return m.group(0)
                asset = (file.parent / name).resolve()
                ensure(inside(asset, config['_root']) and asset.is_file(), 'Нет локального ресурса или он вне проекта: ' + name)
                payload = asset.read_bytes()
                relative = 'assets/' + sha(payload) + asset.suffix.lower()
                copies[relative] = payload
                return m.group(1) + '[' + m.group(2) + '](' + relative + ')'
            cleaned, edits, unresolved = normalize_legacy_markup(unit['text'])
            removed_tokens += len(edits); ambiguous_tokens += len(unresolved)
            warnings.extend({'document': document, 'problem': 'legacy_markup_unresolved_preserved',
                             'offset': unit['start']+u['offset'], 'excerpt': u['excerpt']} for u in unresolved)
            absolute_edits = [{**e, 'start': unit['start']+e['start'], 'end': unit['start']+e['end']} for e in edits]
            edits_hash = sha(json.dumps(absolute_edits, ensure_ascii=False, sort_keys=True).encode('utf-8'))
            content = LINK.sub(resource_link, cleaned)
            try:
                pieces = split_text(content, max_bytes)
            except ValueError as exc:
                raise ValueError(str(exc) + '; документ=' + document + '; пункт=' + (clause or '(без номера)')) from exc
            key = json.dumps([document, scope, clause or unit['kind']], ensure_ascii=False)
            ids = ['v2_' + sha((key + '\0' + str(n) + '\0' + piece).encode('utf-8'))[:40]
                   for n, piece in enumerate(pieces)]
            for n, (cid, piece) in enumerate(zip(ids, pieces)):
                ensure(cid not in used_ids, 'Повтор ID при подготовке')
                used_ids.add(cid)
                meta = {
                    'Document': document, 'source_file': source_file, 'Clause': clause,
                    'Scope': scope, 'ClauseKey': key if clause else '', 'section_heading': unit['heading'],
                    'fragment_kind': unit['kind'], 'numbering_scheme': unit['numbering_scheme'],
                    'block_title': unit['block_title'],
                    'normalization_version': NORMALIZATION_VERSION, 'normalization_edits_sha256': edits_hash,
                    'document_version_sha256': info.get('source_sha256', sha(text.encode('utf-8'))),
                    'owner_review_status': 'structural_candidate_not_reviewed',
                    'part_index': n+1, 'part_count': len(ids), 'related_chunk_ids': ids,
                    'source_char_start': unit['start'], 'source_char_end': unit['end'],
                    'source_span_sha256': sha(unit['text'].encode('utf-8')),
                    'references': sorted(set(re.findall(r'\b\d+\.\d+\.\d+(?:\.\d+)*\b', piece)) - {clause}),
                    'reference_resolution': 'not_performed',
                    'table_ids': re.findall(r'^\s*(?:#{1,6}\s*)?Таблица\s+(\S+)', piece, re.M | re.I),
                    'contains_tables': '|' in piece, 'contains_images': '![' in piece,
                    'table_ownership': 'requires_review', 'chunking_version': VERSION,
                    'extraction_warnings': info.get('warnings', [])}
                entries.append({'id': cid, 'content': piece, 'metadata': meta})
            source_spans.append({'start': unit['start'], 'end': unit['end'], 'kind': unit['kind'],
                                 'scope': scope, 'clause': clause, 'chunks': ids,
                                 'normalization_edits': absolute_edits})
        ensure(entries, 'Документ без чанков: ' + document)
        name = sha(document.encode('utf-8'))[:16] + '.chunked.jsonl'
        ensure(name not in {x[0] for x in outputs}, 'Коллизия имени документа')
        outputs.append((name, entries))
        inventory.append({'document': document, 'source_file': source_file, 'markdown': stem,
                          'markdown_text_sha256': sha(text.encode('utf-8')),
                          'chunks': len(entries), 'full_source_character_partition_checked': True,
                          'whitespace_only_spans_not_indexed': True, 'source_spans': source_spans})
    ensure(len(outputs) == len(items), 'Не все документы представлены в корпусе')
    # Validate everything first. Commit staged corpus only after all files/resources are written.
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.chunked_', dir=target.parent))
    try:
        for relative, payload in copies.items():
            asset_path = stage / relative
            ensure(inside(asset_path, stage), 'Выход ресурса вне staging')
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(payload)
        for name, entries in outputs:
            with (stage / name).open('x', encoding='utf-8', newline='\n') as f:
                for row in entries:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
        if target.exists():
            target.rmdir()  # only empty directory; never delete an existing corpus
        stage.rename(target)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return {'schema_version': 'v2-preparation-1_5', 'chunking_version': VERSION,
            'status': 'structural_candidates_require_review',
            'input': source.relative_to(config['_root']).as_posix(),
            'extraction_manifest_sha256': manifest_sha,
            'output': target.relative_to(config['_root']).as_posix(),
            'documents_input': len(items), 'documents_prepared': len(outputs), 'documents_skipped': 0,
            'chunks': len(used_ids), 'assets_copied': len(copies),
            'normalization_version': NORMALIZATION_VERSION, 'removed_control_tokens': removed_tokens,
            'unresolved_markup_tokens': ambiguous_tokens,
            'files': [{'path': (target/name).relative_to(config['_root']).as_posix(), 'chunks': len(rows)} for name, rows in outputs],
            'document_inventory': inventory, 'warnings': warnings,
            'ready_for_final_scoring': False, 'ownership_review_required': True,
            'database_write_performed': False,
            'note': 'Все Markdown сохранены как кандидаты. Номера внутри списков, границы, таблицы и ссылки требуют проверки; старые qrels не подтверждены.'}
