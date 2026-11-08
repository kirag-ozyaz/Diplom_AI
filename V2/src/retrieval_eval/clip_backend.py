"""Необязательный CLIP-индекс ресурсов; RRF по чанкам, без эталонов в запросах."""
import hashlib
import re
from contextlib import ExitStack
from .common import ensure, path_in, digest
from .backend import _client, _vectors


def asset_rows(config, chunks, locations, manifest, images_only=False):
    rows = {}
    pattern = r'!?\[[^\]]*\]\(([^)]+)\)|<img\b[^>]*?src=["\']([^"\']+)["\']'
    for cid, chunk in chunks.items():
        for match in re.finditer(pattern, chunk['content'], re.IGNORECASE):
            target = (match.group(1) or match.group(2)).strip().strip('<>')
            if re.match(r'^[A-Za-z]+:',target):
                continue
            p = path_in(config['_root'], str((config['_root']/locations[cid]['path']).parent/target))
            if images_only and p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif'):
                continue
            rel = p.relative_to(config['_root']).as_posix()
            info = manifest['assets'].get(rel,{})
            if info.get('status') != 'present':
                continue
            sha = info['sha256']
            # Такой же content-addressed asset_id, как в текущем qrels; qrels здесь не читаются.
            aid = 'asset-' + sha[:20]
            row = rows.setdefault(aid,{'asset_id':aid,'sha256':sha,'path':rel,'chunk_ids':set()})
            row['chunk_ids'].add(cid)
    return {aid:{**row,'chunk_ids':sorted(row['chunk_ids'])} for aid,row in rows.items()}


def signature(config, manifest):
    return digest({'corpus':manifest['chunk_set_sha256'],'assets':manifest['assets_sha256'],
                   'model':config['clip']['model'],'dimension':config['clip']['dimension']})


def clip_encoder(config):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config['clip']['model'],device=config.get('clip_device','cpu'),
                               local_files_only=config['local_files_only'])


def load_clip(config, chunks, locations, manifest, allow_db_write=False):
    ensure(allow_db_write,'CLIP-загрузка требует --allow-db-write')
    name=config['clip']['collection']
    ensure(name in config['allowed_collections'] and name.startswith('diplom_v2_'),'Запрещённая CLIP-коллекция')
    assets=asset_rows(config,chunks,locations,manifest,images_only=True)
    ensure(assets,'Нет локальных изображений для CLIP')
    client=_client(config)
    ensure(not client.has_collection(collection_name=name),'CLIP-коллекция существует; автоматической очистки нет')
    encoder=clip_encoder(config)
    from PIL import Image
    from pymilvus import DataType
    mode={'normalize_embeddings':True,'dimension':config['clip']['dimension']}
    ids=sorted(assets)
    first_vectors=None
    # Первая кодировка до создания коллекции.
    def vectors(group):
        with ExitStack() as stack:
            images=[]
            for aid in group:
                image=stack.enter_context(Image.open(path_in(config['_root'],assets[aid]['path'])))
                rgb=image.convert('RGB')
                stack.callback(rgb.close)
                images.append(rgb)
            return _vectors(encoder,images,mode,config['batch_size'])
    first_vectors=vectors(ids[:config['batch_size']])
    schema=client.create_schema(auto_id=False,enable_dynamic_field=False,description='v2clip:'+signature(config,manifest))
    schema.add_field(field_name='asset_id',datatype=DataType.VARCHAR,max_length=64,is_primary=True)
    schema.add_field(field_name='sha256',datatype=DataType.VARCHAR,max_length=64)
    schema.add_field(field_name='vector',datatype=DataType.FLOAT_VECTOR,dim=mode['dimension'])
    indexes=client.prepare_index_params()
    indexes.add_index(field_name='vector',index_type='AUTOINDEX',metric_type='COSINE')
    client.create_collection(collection_name=name,schema=schema,index_params=indexes,consistency_level='Strong')
    inserted=0
    for start in range(0,len(ids),config['batch_size']):
        group=ids[start:start+config['batch_size']]
        vs=first_vectors if start==0 else vectors(group)
        entities=[{'asset_id':aid,'sha256':assets[aid]['sha256'],'vector':v} for aid,v in zip(group,vs)]
        result=client.insert(collection_name=name,data=entities)
        ensure(result.get('insert_count')==len(entities),'Неполная CLIP-вставка; коллекция не удаляется')
        inserted+=len(entities)
    client.flush(collection_name=name)
    client.load_collection(collection_name=name)
    ensure(int(client.get_collection_stats(collection_name=name)['row_count'])==len(ids),'Неполный CLIP-индекс')
    return {'collection':name,'assets':inserted,'clip_signature':signature(config,manifest),'status':'complete'}


def fuse(config, runs, chunks, locations, manifest):
    from .backend import _vectors
    settings=config['clip'];name=settings['collection']
    ensure(name in config['allowed_collections'] and name.startswith('diplom_v2_'),'Запрещённая коллекция CLIP')
    client=_client(config)
    ensure(client.has_collection(collection_name=name),'Нет CLIP-индекса; search не создаёт его')
    ensure(client.describe_collection(collection_name=name).get('description')=='v2clip:'+signature(config,manifest),'Другая версия CLIP-индекса')
    assets=asset_rows(config,chunks,locations,manifest,images_only=True)
    ensure(int(client.get_collection_stats(collection_name=name)['row_count'])==len(assets),'Неполная CLIP-коллекция')
    client.load_collection(collection_name=name)
    encoder=clip_encoder(config)
    mode={'normalize_embeddings':True,'dimension':settings['dimension']}
    for run in runs:
        vector=_vectors(encoder,[run['query']],mode,1)
        hits=client.search(collection_name=name,data=vector,anns_field='vector',
            search_params={'metric_type':'COSINE','params':{}},limit=settings['candidate_depth'],
            output_fields=['asset_id','sha256'],consistency_level='Strong')[0]
        rows={r['chunk_id']:dict(r) for r in run['results']}
        scores={r['chunk_id']:1/(settings['rrf_k']+n) for n,r in enumerate(run['results'],1)}
        asset_rank={}
        for n,hit in enumerate(hits,1):
            entity=hit['entity'];aid=entity['asset_id']
            ensure(aid in assets and assets[aid]['sha256']==entity['sha256'],'Изменённый ресурс CLIP-индекса')
            for cid in assets[aid]['chunk_ids']:
                asset_rank.setdefault(cid,(n,aid))
        for cid,(n,aid) in asset_rank.items():
            scores[cid]=scores.get(cid,0)+settings['weight']/(settings['rrf_k']+n)
            rows.setdefault(cid,{'chunk_id':cid,'content':chunks[cid]['content'],'metadata':chunks[cid]['metadata']})
            rows[cid]['clip_asset_id']=aid
        ordered=sorted(scores,key=lambda cid:(-scores[cid],cid))[:config['search_depth']]
        run['results']=[{**rows[cid],'rank':n,'fusion_score':scores[cid]} for n,cid in enumerate(ordered,1)]
        run['clip_signature']=signature(config,manifest)
    return runs
