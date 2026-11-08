"""Изолированный текстовый адаптер Milvus; тяжёлые библиотеки импортируются только при load/search."""
import hashlib
import json
import math
from .common import ensure, digest
from .corpus_manifest import index_signature


def _client(config):
    try:
        from pymilvus import MilvusClient
    except ImportError as e:
        raise ValueError('Установите зависимости из V2/requirements.txt в отдельном окружении') from e
    return MilvusClient(uri=config['milvus_uri'])


def _encoder(config, mode):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ValueError('Нужен sentence-transformers из V2/requirements.txt') from e
    return SentenceTransformer(mode['model'], device=config['device'],
                               local_files_only=config['local_files_only'])


def _vectors(encoder, texts, mode, batch):
    values = encoder.encode(texts, batch_size=batch, normalize_embeddings=mode['normalize_embeddings'],
                            show_progress_bar=False)
    vectors = values.tolist() if hasattr(values, 'tolist') else values
    ensure(len(vectors) == len(texts), 'Модель вернула неверное число векторов')
    ensure(all(len(v) == mode['dimension'] and all(math.isfinite(float(x)) for x in v)
               for v in vectors), 'Размерность/значения эмбеддингов не соответствуют конфигурации')
    return vectors


def load(config, mode_name, chunks, manifest, allow_db_write=False, client=None, encoder=None):
    ensure(allow_db_write, 'Загрузка требует явного --allow-db-write; по умолчанию база не меняется')
    mode = config['modes'][mode_name]
    name = mode['collection']
    ensure(name in config['allowed_collections'] and name.startswith('diplom_v2_'), 'Запрещённая коллекция')
    # Проверить лимиты всех строк ДО подключения и создания коллекции.
    for cid, c in chunks.items():
        ensure(len(cid.encode()) <= 4096 and len(c['content'].encode()) <= 65535,
               'Текст/ID не помещается в схему Milvus; молча обрезать нельзя')
        ensure(len(json.dumps(c['metadata'], ensure_ascii=False).encode()) <= 60000,
               'Слишком большой объект метаданных')
    client = client if client is not None else _client(config)
    ensure(not client.has_collection(collection_name=name),
           f'Коллекция {name} уже существует. Автоматической очистки/добавления/перезаписи нет. Выберите новое разрешённое имя.')
    encoder = encoder if encoder is not None else _encoder(config, mode)
    # Загрузка модели/первая кодировка должна пройти прежде, чем создаём пустую коллекцию.
    ids = sorted(chunks)
    batch = config['batch_size']
    first = _vectors(encoder, [mode['passage_prefix'] + chunks[c]['content'] for c in ids[:batch]], mode, batch)
    from pymilvus import DataType
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False,
                                  description='v2:' + index_signature(manifest, mode))
    schema.add_field(field_name='chunk_key', datatype=DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field(field_name='chunk_id', datatype=DataType.VARCHAR, max_length=4096)
    schema.add_field(field_name='content', datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name='metadata', datatype=DataType.JSON)
    schema.add_field(field_name='corpus_sha', datatype=DataType.VARCHAR, max_length=64)
    schema.add_field(field_name='vector', datatype=DataType.FLOAT_VECTOR, dim=mode['dimension'])
    indexes = client.prepare_index_params()
    indexes.add_index(field_name='vector', index_type='AUTOINDEX', metric_type='COSINE')
    client.create_collection(collection_name=name, schema=schema, index_params=indexes,
                             consistency_level='Strong')
    total = 0
    for start in range(0, len(ids), batch):
        group = ids[start:start+batch]
        vectors = first if start == 0 else _vectors(encoder, [mode['passage_prefix']+chunks[c]['content'] for c in group], mode, batch)
        entities = [{'chunk_key': hashlib.sha256(cid.encode()).hexdigest(), 'chunk_id': cid,
                     'content': chunks[cid]['content'], 'metadata': chunks[cid]['metadata'],
                     'corpus_sha': manifest['chunk_set_sha256'], 'vector': v}
                    for cid, v in zip(group, vectors)]
        result = client.insert(collection_name=name, data=entities)
        ensure(result.get('insert_count') == len(entities), 'Неполная вставка в Milvus')
        total += len(entities)
    client.flush(collection_name=name)
    client.load_collection(collection_name=name)
    count = int(client.get_collection_stats(collection_name=name)['row_count'])
    ensure(count == len(chunks), 'Количество записей после загрузки не совпадает с корпусом')
    return {'collection': name, 'inserted': total, 'index_signature': index_signature(manifest, mode),
            'status': 'complete', 'note': 'Сбой после создания может оставить неполную коллекцию; она не очищается автоматически.'}


def search(config, mode_name, questions, chunks, manifest, client=None, encoder=None, reranker=None):
    mode = config['modes'][mode_name]
    name = mode['collection']
    ensure(name in config['allowed_collections'] and name.startswith('diplom_v2_'), 'Запрещённая коллекция')
    client = client if client is not None else _client(config)
    ensure(client.has_collection(collection_name=name), 'Нет выбранной коллекции; поиск не создаёт её')
    description = client.describe_collection(collection_name=name)
    ensure(description.get('description') == 'v2:' + index_signature(manifest, mode),
           'Коллекция создана для другой версии корпуса/модели/префиксов/ресурсов')
    ensure(int(client.get_collection_stats(collection_name=name)['row_count']) == len(chunks),
           'Неполная или изменённая коллекция')
    client.load_collection(collection_name=name)
    encoder = encoder if encoder is not None else _encoder(config, mode)
    if mode.get('rerank_model') and reranker is None:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder(mode['rerank_model'], device=config['device'],
                                local_files_only=config['local_files_only'])
    depth = config['search_depth']
    candidate_depth = max(depth, mode.get('candidate_depth', depth))
    ensure(candidate_depth <= 1000, 'Слишком большая глубина кандидатов')
    runs = []
    for q in questions:
        vectors = _vectors(encoder, [mode['query_prefix']+q['query']], mode, 1)
        data = client.search(collection_name=name, data=vectors, anns_field='vector',
                             search_params={'metric_type': 'COSINE', 'params': {}},
                             limit=candidate_depth,
                             output_fields=['chunk_id','content','metadata','corpus_sha'],
                             consistency_level='Strong')[0]
        results = []
        seen = set()
        for hit in data:
            entity = hit['entity']
            cid = entity['chunk_id']
            ensure(cid in chunks and cid not in seen, 'Неизвестный/повторный чанк в Milvus')
            seen.add(cid)
            ensure(entity['corpus_sha'] == manifest['chunk_set_sha256'], 'Чужая версия записи Milvus')
            ensure(entity['content'] == chunks[cid]['content'] and entity['metadata'] == chunks[cid]['metadata'],
                   'Содержимое/метаданные Milvus отличаются от локального корпуса')
            score = float(hit['distance'])
            ensure(math.isfinite(score), 'Некорректная оценка поиска')
            results.append({'chunk_id': cid, 'retrieval_score': score, 'content': entity['content'],
                            'metadata': entity['metadata']})
        if reranker is not None and results:
            scores = reranker.predict([(q['query'], r['content']) for r in results])
            ensure(len(scores) == len(results), 'Неполное переранжирование')
            for r, score in zip(results, scores):
                r['rerank_score'] = float(score)
                ensure(math.isfinite(r['rerank_score']), 'Некорректная оценка переранжирования')
            results.sort(key=lambda r: (-r['rerank_score'], r['chunk_id']))
        results = results[:depth]
        for rank, r in enumerate(results, 1):
            r['rank'] = rank
        runs.append({'qid': str(q['id']), 'query': q['query'],
                     'question_revision': q.get('question_revision'),
                     'results': results, 'delivered_asset_ids': []})
    return runs



def search_extended(config, mode_name, questions, chunks, locations, manifest, with_clip=False):
    if not with_clip:
        return search(config,mode_name,questions,chunks,manifest)
    from copy import deepcopy
    from .clip_backend import fuse
    temporary=deepcopy(config)
    mode=temporary['modes'][mode_name]
    rerank_model=mode.pop('rerank_model',None)
    temporary['search_depth']=max(config['search_depth'],config['clip']['candidate_depth'],mode.get('candidate_depth',0))
    runs=search(temporary,mode_name,questions,chunks,manifest)
    runs=fuse(temporary,runs,chunks,locations,manifest)
    reranker=None
    if rerank_model:
        from sentence_transformers import CrossEncoder
        reranker=CrossEncoder(rerank_model,device=config['device'],local_files_only=config['local_files_only'])
    for run in runs:
        if reranker is not None and run['results']:
            scores=reranker.predict([(run['query'],r['content']) for r in run['results']])
            ensure(len(scores)==len(run['results']),'Неполное финальное переранжирование')
            for row,score in zip(run['results'],scores):
                row['rerank_score']=float(score)
                ensure(math.isfinite(row['rerank_score']),'Некорректная оценка rerank')
            run['results'].sort(key=lambda r:(-r['rerank_score'],r['chunk_id']))
        run['results']=run['results'][:config['search_depth']]
        for n,row in enumerate(run['results'],1):
            row['rank']=n
    return runs
