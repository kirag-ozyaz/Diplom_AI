"""Консервативная подготовка новых чанков из уже извлечённых Markdown.
DOCX, формулы и merged cells здесь не угадываются; используется прежнее извлечение отдельно.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path
from .common import ensure, inside, path_in, write_json, run_id


def prepare_markdown(config, input_path):
    source = path_in(config['_root'], input_path)
    ensure(source.is_dir(), 'Нужна папка подготовленных Markdown')
    target = config['_v2'] / 'data/chunked'
    ensure(inside(target, config['_v2']), 'Выходная папка чанков ссылается за пределы V2')
    ensure(not target.exists() or not any(target.iterdir()),
           'V2/data/chunked не пуста. Подготовка не перезаписывает существующие чанки.')
    ensure(not inside(source, target) and not inside(target, source), 'Источник и выход не должны перекрываться')
    files = sorted(source.rglob('*.md'))
    ensure(bool(files), 'Нет Markdown')
    prepared, warnings = [], []
    resource_copies = {}
    max_bytes = int(config.get('max_chunk_bytes', 60000))
    ensure(1024 <= max_bytes <= 60000, 'max_chunk_bytes должен быть от 1024 до 60000')
    def split_clause(value):
        # Таблицы не дробятся посередине строки. Неделимый большой блок требует ручного решения.
        parts, acc = [], ''
        for block in re.split(r'\n\s*\n', value):
            ensure(len(block.encode()) <= max_bytes, 'Неделимый блок/таблица слишком велик: требуется осмысленное ручное разбиение')
            candidate = acc + ('\n\n' if acc else '') + block
            if len(candidate.encode()) > max_bytes:
                parts.append(acc); acc = block
            else:
                acc = candidate
        if acc:
            parts.append(acc)
        return parts

    # Только начало отдельной строки; строка «см. пункт 1.2.3» не становится владельцем.
    owner = re.compile(r'^\s*(?:#{1,6}\s*)?(\d+\.\d+\.\d+(?:\.\d+)*)(?:\.)?\s+(?=\S)', re.MULTILINE)
    outputs, used_ids = [], set()
    for file in files:
        ensure(inside(file, source), 'Ссылка Markdown вне источника')
        text = file.read_text(encoding='utf-8-sig')
        matches = list(owner.finditer(text))
        if not matches:
            warnings.append({'source': str(file.relative_to(source)), 'problem': 'no_numbered_clause; not_chunked'})
            continue
        if text[:matches[0].start()].strip():
            warnings.append({'source': str(file.relative_to(source)), 'problem': 'preamble_not_indexed; inspect'})
        entries = []
        for i, match in enumerate(matches):
            content = text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
            clause = match.group(1)

            # Постоянные копии ресурсов имеют content-addressed имена: ID чанка не зависит от времени извлечения.
            def resource_link(m):
                name = m.group(2).strip().strip('<>')
                if name.startswith(('http:', 'https:', 'data:', '#')):
                    warnings.append({'clause':clause,'problem':'external_or_anchor_resource_not_copied','path':name})
                    return m.group(0)
                asset = (file.parent/name).resolve()
                ensure(inside(asset,config['_root']), 'Ссылка на ресурс вне проекта')
                if not asset.is_file():
                    warnings.append({'clause':clause,'problem':'missing_resource','path':name})
                    return m.group(0)
                payload=asset.read_bytes()
                relative='assets/'+hashlib.sha256(payload).hexdigest()+asset.suffix.lower()
                resource_copies[relative]=payload
                return m.group(1)+'('+relative+')'
            content=re.sub(r'(!?\[[^\]]*\])\(([^)]+)\)',resource_link,content)
            stem = file.relative_to(source).as_posix()
            source_info = file.parent/'source.json'
            info = json.loads(source_info.read_text(encoding='utf-8')) if source_info.is_file() else {}
            pieces = split_clause(content)
            ids = ['v2_' + clause + '_' + hashlib.sha256((stem+'\0'+str(n)+'\0'+piece).encode()).hexdigest()[:24] for n,piece in enumerate(pieces)]
            for n,(cid,piece) in enumerate(zip(ids,pieces)):
                ensure(cid not in used_ids, 'Повтор идентификатора при подготовке')
                used_ids.add(cid)
                table_ids = re.findall(r'^\s*(?:#{1,6}\s*)?Таблица\s+(\d+(?:\.\d+)*)',piece,re.MULTILINE|re.IGNORECASE)
                entries.append({'id': cid, 'content': piece, 'metadata': {
                    'Document': info.get('document_id',stem),
                    'source_file': info.get('source_file',file.relative_to(config['_root']).as_posix()),
                    'Clause': clause, 'document_version_sha256': info.get('source_sha256',hashlib.sha256(text.encode()).hexdigest()),
                    'owner_review_status': 'structural_candidate_not_reviewed',
                    'part_index': n+1, 'part_count': len(ids), 'related_chunk_ids': ids,
                    'references': sorted(set(re.findall(r'\b\d+\.\d+\.\d+(?:\.\d+)*\b',piece))-{clause}),
                    'table_ids':table_ids, 'contains_tables': '|' in piece, 'contains_images': '![' in piece,
                    'table_ownership': 'requires_review', 'chunking_version': 'v2-markdown-clause-2',
                    'extraction_warnings':info.get('warnings',[])}})
        name = hashlib.sha256(file.relative_to(source).as_posix().encode()).hexdigest()[:16]+'.chunked.jsonl'
        outputs.append((target/name, entries))
    ensure(bool(outputs), 'Не удалось выделить ни одного пункта')
    # Сначала подготовить всё в памяти, чтобы ранняя ошибка не оставляла частичный корпус.
    target.mkdir(parents=True, exist_ok=True)
    for relative,payload in resource_copies.items():
        asset_path=target/relative
        ensure(inside(asset_path,target), 'Выход ресурса вне целевого корпуса')
        asset_path.parent.mkdir(parents=True,exist_ok=True)
        with asset_path.open('xb') as stream:
            stream.write(payload)
    for path, entries in outputs:
        with path.open('x', encoding='utf-8') as f:
            for row in entries:
                f.write(json.dumps(row, ensure_ascii=False)+'\n')
        prepared.append({'path': path.relative_to(config['_root']).as_posix(), 'chunks': len(entries)})
    return {'files': prepared, 'warnings': warnings,
            'ready_for_final_scoring': False, 'ownership_review_required': True,
            'note': 'Новый корпус не активирован. Требуется проверка границ, таблиц, ресурсов, новая разметка и явная смена paths.chunks/qrels.'}
