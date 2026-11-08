import re
from .common import tool, ensure
from .corpus_manifest import load_corpus


def validate_chunks(config, strict=False):
    chunks, locations, manifest = load_corpus(config)
    warnings, errors = [], []
    for cid, c in chunks.items():
        meta = c['metadata']
        clause = meta.get('Clause')
        if not isinstance(clause, str) or not re.fullmatch(r'\d+(?:\.\d+){2,}', clause.strip()):
            warnings.append({'chunk_id': cid, 'problem': 'no_unambiguous_own_clause',
                             'note': 'Заголовок/таблица может быть отдельным фрагментом; принадлежность проверить.'})
        if not (meta.get('Document') or meta.get('document_id') or meta.get('source_file')):
            errors.append({'chunk_id': cid, 'problem': 'no_document_or_source'})
        if meta.get('owner_review_status') != 'reviewed':
            warnings.append({'chunk_id': cid, 'problem': 'ownership_not_manually_accepted'})
        if len(c['content'].encode('utf-8')) > 65535:
            errors.append({'chunk_id': cid, 'problem': 'content_exceeds_milvus_varchar_65535_bytes',
                           'note': 'Нужно явно исправить разбиение и перепринять qrels; текст не обрезать.'})
        if len(cid.encode('utf-8')) > 4096:
            errors.append({'chunk_id': cid, 'problem': 'id_exceeds_4096_bytes'})
    for path, info in manifest['assets'].items():
        if info['status'] != 'present':
            warnings.append({'asset': path, 'problem': info['status']})
    if strict and warnings:
        errors.append({'problem': 'strict_validation_rejected_warnings'})
    return {'status': 'failed' if errors else 'passed_with_warnings' if warnings else 'passed',
            'errors': errors, 'warnings': warnings, 'manifest': manifest,
            'semantic_ownership_acceptance': 'not_performed_by_program',
            'note': 'Без strict это техническая совместимость, не доказательство исправления всех границ.'}
