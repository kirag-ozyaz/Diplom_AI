"""Оформление только сохранённых метрик V2. Ни модели, ни Milvus не вызываются."""
import csv
import html
import json
from pathlib import Path
from .common import ensure, inside, path_in, read_json, run_id, write_json


def rows_for(data):
    rows=[]
    for split,ks in data['summary'].items():
        for k,groups in ks.items():
            for group in ('content','clause','facts'):
                for name,value in groups.get(group,{}).items():
                    rows.append({'split':split,'k':int(k),'group':group,'metric':name,
                                 'mean':value['mean'],'denominator':value['denominator']})
    return rows


def build(config, input_path, kind='report'):
    source=path_in(config['_root'],input_path)
    ensure(inside(source,config['_v2']/'results/retrieval'),'Метрики должны лежать в V2/results/retrieval')
    data=read_json(source)
    ensure(data.get('schema_version')=='v2-metrics-1','Нужен файл метрик V2, не старый Hit@k')
    out=config['paths']['results']/('report_'+run_id())
    ensure(inside(out,config['_v2']),'Отчёт вне V2')
    out.mkdir(parents=True,exist_ok=False)
    rows=rows_for(data)
    if kind=='notebook':
        relative=source.relative_to(config['_root']).as_posix()
        cells=[{'cell_type':'markdown','metadata':{},'source':['# Анализ сохранённых метрик V2\n','Ноутбук не выполнялся при подготовке исходников. Не обращается к базе.']},
               {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],
                'source':['from pathlib import Path\n','import json\n','roots = [Path.cwd(), *Path.cwd().parents]\n',
                          'root = next(p for p in roots if (p / "V2").is_dir())\n',
                          'data = json.loads((root / '+repr(relative)+').read_text(encoding="utf-8"))\n',
                          'print(json.dumps(data["summary"], ensure_ascii=False, indent=2))\n']}]
        write_json(out/'retrieval.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells},config['_v2'])
    elif kind=='plot':
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        for group in ('content','clause'):
            fig,ax=plt.subplots()
            for metric in ('hit','rr','ndcg_reference_set'):
                selected=sorted((r for r in rows if r['split']=='all' and r['group']==group and r['metric']==metric and r['mean'] is not None),key=lambda r:r['k'])
                if selected:
                    ax.plot([r['k'] for r in selected],[r['mean'] for r in selected],marker='o',label=metric)
            ax.set(xlabel='k / cutoff',ylabel='Mean',title=str(data.get('mode'))+' / '+group,ylim=(0,1.05))
            ax.legend();ax.grid(True,alpha=.3)
            fig.savefig(out/(group+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)
    else:
        with (out/'metrics.csv').open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['split','k','group','metric','mean','denominator']);writer.writeheader();writer.writerows(rows)
        lines=['# Проверка поиска V2','', 'Источник: `'+source.relative_to(config['_root']).as_posix()+'`','',
               'Режим: '+str(data.get('mode')),'Версия qrels: '+str(data.get('qrels_version')),
               'Корпус SHA256: '+str(data.get('corpus_sha256')),'',data.get('interpretation',''),'',
               '| Split | k | Шкала | Метрика | Среднее | Знаменатель |','|---|---:|---|---|---:|---:|']
        for r in rows:
            lines.append('| '+' | '.join(str(r[key]) if r[key] is not None else 'не применимо' for key in ('split','k','group','metric','mean','denominator'))+' |')
        lines.extend(['','## Ограничения по вопросам',''])
        lines.extend('- '+str(q['qid'])+': '+json.dumps(q.get('issues',[]),ensure_ascii=False) for q in data.get('questions',[]) if q.get('issues'))
        with (out/'report.md').open('x',encoding='utf-8') as stream:
            stream.write('\n'.join(lines)+'\n')
        heading='<tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in ('split','k','group','metric','mean','denominator'))+'</tr>'
        body=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('split','k','group','metric','mean','denominator'))+'</tr>' for r in rows)
        with (out/'report.html').open('x',encoding='utf-8') as stream:
            stream.write('<!doctype html><meta charset="utf-8"><title>Проверка поиска V2</title><style>body{font:16px system-ui;margin:32px}td,th{padding:7px;border:1px solid #ddd}table{border-collapse:collapse}</style><h1>Проверка поиска V2</h1><p>'+html.escape(data.get('interpretation',''))+'</p><table>'+heading+body+'</table><h2>Происхождение</h2><pre>'+html.escape(json.dumps({k:data.get(k) for k in ('mode','qrels_version','corpus_sha256','questions_sha256','created_at','resources_mode')},ensure_ascii=False,indent=2))+'</pre>')
    write_json(out/'source.json',{'metrics_path':source.relative_to(config['_root']).as_posix(),'kind':kind,'note':'Никаких новых измерений; оформление сохранённых результатов.'},config['_v2'])
    return {'status':'written','output':str(out),'kind':kind}
