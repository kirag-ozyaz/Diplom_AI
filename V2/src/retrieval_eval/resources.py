"""Экспорт реально доступных изображений рядом с выдачей; проверка хешей при оценке."""
import hashlib
from .common import ensure, inside, path_in
from .clip_backend import asset_rows


def export_assets(config, runs, chunks, locations, manifest, output):
    ensure(inside(output, config['_v2']/'results/retrieval'),'Ресурсы вне папки результатов')
    assets=asset_rows(config,chunks,locations,manifest)
    by_chunk={}
    for aid,row in assets.items():
        for cid in row['chunk_ids']:
            by_chunk.setdefault(cid,[]).append(aid)
    exported={}
    for run in runs:
        used=set()
        for result in run['results']:
            linked=sorted(by_chunk.get(result['chunk_id'],[]))
            result['delivered_asset_ids']=linked
            used.update(linked)
            for aid in linked:
                if aid in exported:
                    continue
                row=assets[aid]
                source=path_in(config['_root'],row['path'])
                data=source.read_bytes()
                ensure(hashlib.sha256(data).hexdigest()==row['sha256'],'Ресурс изменился во время экспорта')
                target=output/'assets'/(row['sha256']+source.suffix.lower())
                ensure(inside(target,config['_v2']),'Ресурс ссылается вне V2')
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(data)
                exported[aid]={'source_path':row['path'],'path':target.relative_to(config['_root']).as_posix(),'sha256':row['sha256']}
        run['delivered_asset_ids']=sorted(used)
    return exported


def verify_assets(config, snapshot, chunks, locations, manifest):
    assets=asset_rows(config,chunks,locations,manifest)
    delivery=snapshot.get('asset_delivery',{})
    for aid,row in delivery.items():
        ensure(aid in assets and row['source_path']==assets[aid]['path'] and row['sha256']==assets[aid]['sha256'],'Неизвестный/изменённый ресурс выдачи')
        p=path_in(config['_root'],row['path'])
        ensure(inside(p,config['_v2']/'results/retrieval'),'Ресурс выдачи вне V2/results/retrieval')
        ensure(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'Экспортированное изображение отсутствует/изменено')
    verified={}
    for run in snapshot['runs']:
        used=set()
        for result in run['results']:
            linked=set(result.get('delivered_asset_ids',[]))
            ensure(linked<=set(delivery),'Для изображения нет файла в выдаче')
            ensure(all(result['chunk_id'] in assets[aid]['chunk_ids'] for aid in linked),'Изображение не принадлежит найденному чанку')
            used.update(linked)
        ensure(used==set(run.get('delivered_asset_ids',[])),'Расходятся списки ресурсов вопроса и результатов')
        verified[str(run['qid'])]=used
    return verified
