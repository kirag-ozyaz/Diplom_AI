#!/usr/bin/env python3
"""Локальный V2. Любая запись в Milvus требует --allow-db-write. Старые файлы не меняются."""
import argparse
import json
import math
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
# Намеренно не добавляем src проекта: нельзя случайно загрузить его старые модули.
sys.path.insert(0, str(V2 / 'src'))
from retrieval_eval.common import (load_config, ensure, canonical, digest, read_json,
                                   write_json, path_in, run_id, timestamp, V2Error)
from retrieval_eval.corpus_manifest import load_corpus, index_signature
from retrieval_eval.validate_chunks import validate_chunks
from retrieval_eval.qrels_io import load_questions, load_qrels
from retrieval_eval.scoring import evaluate


def check_snapshot(config, snapshot, chunks, manifest, questions):
    ensure(snapshot.get('schema_version') == 'v2-search-1', 'Нужен сохранённый формат v2-search-1')
    ensure(snapshot['manifest']['chunk_set_sha256'] == manifest['chunk_set_sha256'], 'Выдача от другой версии чанков')
    ensure(snapshot['manifest']['assets_sha256'] == manifest['assets_sha256'], 'Изменились ресурсы корпуса')
    ensure(snapshot['questions_sha256'] == digest(questions), 'Выдача от другой версии вопросов')
    mode_name = snapshot['mode']
    ensure(mode_name in config['modes'], 'Неизвестный режим сохранённой выдачи')
    ensure(snapshot['index_signature'] == index_signature(manifest, config['modes'][mode_name]),
           'Выдача от другой модели/профиля индекса')
    ensure(snapshot['search_depth'] >= max(config['k_values']), 'Выдача недостаточной глубины')
    ensure(snapshot.get('rerank_model') == config['modes'][mode_name].get('rerank_model'), 'Изменилась модель rerank')
    if snapshot.get('clip_enabled'):
        from retrieval_eval.clip_backend import signature
        ensure(snapshot.get('search_settings',{}).get('clip') == config.get('clip'), 'Изменились настройки CLIP')
        ensure(all(run.get('clip_signature')==signature(config,manifest) for run in snapshot['runs']), 'Изменился CLIP-индекс/корпус')
    qmap = {str(q['id']): q for q in questions}
    for run in snapshot['runs']:
        qid = str(run['qid'])
        ensure(qid in qmap, 'В выдаче неизвестный вопрос')
        ensure(run.get('question_revision') == qmap[qid].get('question_revision'), 'Изменена ревизия вопроса')
        ensure(len(run['results']) <= snapshot['search_depth'], 'Результатов больше объявленной глубины')
        for row in run['results']:
            cid = row['chunk_id']
            ensure(cid in chunks, 'Выдача с неизвестным ID')
            ensure(row['content'] == chunks[cid]['content'] and row['metadata'] == chunks[cid]['metadata'],
                   'Выдача изменила текст/метаданные чанка')
    return True


def get_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['plan','prepare-documents','prepare','validate','load','load-clip','search','evaluate','report','plot','notebook','all'])
    p.add_argument('--project-root', help='По умолчанию родитель папки V2')
    p.add_argument('--config', help='Относительно корня проекта; только V2/configs')
    p.add_argument('--mode', choices=['base','e5','rerank'], default=None)
    p.add_argument('--allow-db-write', action='store_true')
    p.add_argument('--reuse-collection', action='store_true', help='Только all: искать в существующей совместимой коллекции')
    p.add_argument('--input', help='Для evaluate: сохранённая выдача V2, путь от корня проекта')
    p.add_argument('--from-md', help='Для prepare: папка подготовленных Markdown от корня проекта')
    p.add_argument('--from-raw', nargs='?', const='data/raw', help='Извлечение DOCX/Markdown из read-only raw; не включается скрыто')
    p.add_argument('--with-clip', action='store_true', help='Подключить отдельный CLIP-индекс; он должен быть явно загружен')
    p.add_argument('--with-assets', action='store_true', help='Копировать изображения найденных чанков в результаты и фиксировать доставку')
    p.add_argument('--strict', action='store_true', help='Предупреждения корпуса считать ошибками')
    p.add_argument('--corpus-only', action='store_true', help='Для validate: без проверки совместимости qrels')
    return p


def execute(args):
    config = load_config(V2, args.project_root, args.config)
    requested_mode = args.mode
    args.mode = args.mode or 'base'
    mode = config['modes'][args.mode]
    if args.command == 'plan':
        # Никаких тяжёлых библиотек, загрузки моделей, обращений к Milvus и записи файлов.
        _, _, manifest = load_corpus(config)
        return {'status': 'plan_only_no_writes', 'project_root': str(config['_root']),
                'raw_read_only': str(config['paths']['raw']), 'chunks': str(config['paths']['chunks']),
                'questions': str(config['paths']['questions']), 'qrels': str(config['paths']['qrels']),
                'results': str(config['paths']['results']), 'mode': args.mode, 'model': mode,
                'manifest': manifest, 'live_db_checked': False,
                'warning': 'Модели base/e5 закреплены по исходным runtime и совпадают. Не объявлять режимы разными моделями. CLIP включается только --with-clip; генерация ответа не входит в этап 2.'}
    out = config['paths']['results'] / run_id()
    if args.command in ('report','plot','notebook'):
        ensure(args.input, 'Для оформления требуется --input сохранённых metrics.json')
        from retrieval_eval.reports import build
        return build(config,args.input,args.command)
    if args.command == 'prepare-documents':
        from retrieval_eval.documents import extract_documents
        return extract_documents(config,args.from_raw)
    if args.command == 'prepare':
        ensure(not (args.from_md and args.from_raw), 'Выберите --from-md или --from-raw')
        if args.from_raw:
            from retrieval_eval.documents import extract_documents
            documents = extract_documents(config,args.from_raw)
            args.from_md = documents['output']
        ensure(args.from_md, 'Для prepare требуется --from-md или --from-raw')
        from retrieval_eval.preparation import prepare_markdown
        result = prepare_markdown(config, args.from_md)
        write_json(out/'preparation.json', result, V2)
        return {'report': str(out/'preparation.json'), **result}
    validation = validate_chunks(config, strict=args.strict or config.get('strict_chunks', False))
    ensure(not validation['errors'], f'Корпус отклонён: {validation["errors"][:3]}')
    if args.command == 'validate':
        if not args.corpus_only:
            qrels = load_qrels(config)
            validation['qrels_version'] = qrels.get('artifact_version')
            validation['qrels_compatibility'] = 'passed'
        write_json(out/'validation.json', validation, V2)
        return {'report': str(out/'validation.json'), 'status': validation['status'],
                'warnings': len(validation['warnings']), 'live_db_checked': False}
    chunks, locations, manifest = load_corpus(config)
    if args.command == 'load-clip':
        from retrieval_eval.clip_backend import load_clip
        result = load_clip(config,chunks,locations,manifest,args.allow_db_write)
        write_json(out/'load_clip.json',result,V2)
        return result
    if args.command in ('load','all') and not (args.command == 'all' and args.reuse_collection):
        # Для полного запуска убедиться в совместимости эталона до изменения базы.
        if args.command == 'all':
            load_qrels(config)
        from retrieval_eval.backend import load
        loaded = load(config, args.mode, chunks, manifest, args.allow_db_write)
        if args.command == 'all' and args.with_clip:
            from retrieval_eval.clip_backend import load_clip
            loaded['clip'] = load_clip(config,chunks,locations,manifest,args.allow_db_write)
        write_json(out/'load.json', {'created_at': timestamp(), 'manifest': manifest, **loaded}, V2)
        if args.command == 'load':
            return {'report': str(out/'load.json'), **loaded}
    questions = load_questions(config)
    if args.command in ('search','all'):
        from retrieval_eval.backend import search_extended
        runs = search_extended(config,args.mode,questions,chunks,locations,manifest,args.with_clip)
        asset_delivery = {}
        if args.with_assets:
            from retrieval_eval.resources import export_assets
            asset_delivery = export_assets(config,runs,chunks,locations,manifest,out)
        snapshot = {'schema_version': 'v2-search-1', 'created_at': timestamp(),
                    'mode': args.mode, 'search_depth': config['search_depth'],
                    'index_signature': index_signature(manifest, mode),
                    'manifest': manifest, 'questions_sha256': digest(questions),
                    'runs': runs, 'resources_mode': 'with_linked_assets' if args.with_assets else 'text_only',
                    'asset_delivery':asset_delivery, 'clip_enabled':args.with_clip,
                    'search_settings':{'mode':mode,'clip':config.get('clip') if args.with_clip else None},
                    'rerank_model': mode.get('rerank_model'),
                    'note': 'Изображения экспортируются только --with-assets. CLIP сам по себе не доказывает содержательную релевантность/чтение формулы.'}
        write_json(out/'retrieval.json', snapshot, V2)
        if args.command == 'search':
            return {'report': str(out/'retrieval.json'), 'questions': len(runs)}
    elif args.command == 'evaluate':
        ensure(args.input, 'evaluate требует --input сохранённой выдачи')
        snapshot = read_json(path_in(config['_root'], args.input))
        ensure(requested_mode is None or snapshot.get('mode') == requested_mode, 'Режим --mode не совпадает с сохранённой выдачей')
    else:
        raise V2Error('Неподдерживаемая комбинация этапов')
    check_snapshot(config, snapshot, chunks, manifest, questions)
    qrels = load_qrels(config)
    ensure(snapshot.get('resources_mode') in ('text_only','with_linked_assets'), 'Неизвестный режим ресурсов')
    verified_assets = None
    if snapshot.get('resources_mode') == 'with_linked_assets':
        from retrieval_eval.resources import verify_assets
        verified_assets = verify_assets(config,snapshot,chunks,locations,manifest)
    result = evaluate(qrels,snapshot['runs'],config['k_values'],questions,verified_assets=verified_assets)
    result.update({'created_at': timestamp(), 'schema_version': 'v2-metrics-1',
                   'mode': snapshot['mode'], 'corpus_sha256': manifest['chunk_set_sha256'],
                   'qrels_version': qrels.get('artifact_version'),
                   'questions_sha256':digest(questions), 'resources_mode':snapshot['resources_mode'],
                   'search_settings':snapshot.get('search_settings'), 'clip_enabled':snapshot.get('clip_enabled',False)})
    write_json(out/'metrics.json', result, V2)
    write_json(out/'validation.json', validation, V2)
    return {'report': str(out/'metrics.json'), 'status': 'evaluated_saved_retrieval',
            'live_search_performed_this_call': args.command == 'all'}


def main(argv=None):
    args = get_parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        print('ОШИБКА V2: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
