#!/usr/bin/env python3
"""Оценка поиска V3 на вопросах и qrels V2 (eval_questions_split / eval_qrels_split).
Метрики считает код V2 (retrieval_eval.scoring.evaluate), поэтому числа V3 и V2 сравнимы.
Вопросы, qrels и корпус не меняются; запись только в V3/results.

Запуск из папки V3:
    python scripts/v3_evaluation.py
    python scripts/v3_evaluation.py --variants bm25 bm25+exact
    python scripts/v3_evaluation.py --split development
или через scripts/run_all.ps1 и другие run_*.ps1."""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / 'src'))
from retrieval_v3.hybrid_retriever import HybridRetrieverV3, load_v3_config, parse_variant, ensure, inside, V3Error

# Пошаговая проверка: каждый шаг добавляет одно изменение к предыдущему.
DEFAULT_VARIANTS = ['bm25',                        # 1. только BM25 с морфологией
                    'e5',                          # 2. только E5, как поиск V2 без реранкера
                    'e5+rerank+fullchunk',         # 3. E5 + BGE по целому чанку, повтор схемы V2
                    'bm25_e5',                     # 4. BM25 + E5, RRF
                    'bm25_e5+rerank',              # 5. + BGE по окнам
                    'bm25_e5_clip+rerank',         # 6. + CLIP в RRF
                    'bm25_e5_clip+rerank+exact']   # 7. + пункт по номеру из вопроса
TABLE_KS = (1, 3, 5, 10)


def write_json(path, obj, root):
    ensure(inside(path, root), f'Запись вне V3/results запрещена: {path}')
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')


def summarize(metrics, split):
    ensure(split in metrics['summary'], f'В метриках нет части вопросов {split}')
    s = metrics['summary'][split]
    ensure(all(str(k) in s for k in TABLE_KS), 'В метриках нет нужных k')

    def mean(k, group, name):
        item = s[str(k)][group].get(name)
        return None if item is None else item['mean']
    row = {'questions': s[str(TABLE_KS[0])]['questions']}
    row.update({f'Hit@{k}': mean(k, 'content', 'hit') for k in TABLE_KS})
    row.update({f'Hit_пункт@{k}': mean(k, 'clause', 'hit') for k in TABLE_KS})
    row.update({'MRR@10': mean(10, 'content', 'rr'), 'nDCG@10': mean(10, 'content', 'ndcg_reference_set'),
                'Полнота_фактов@5': mean(5, 'facts', 'text_fact_recall')})
    return row


def get_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', help='по умолчанию V3/configs/v3_config.json')
    p.add_argument('--variants', nargs='+', default=DEFAULT_VARIANTS)
    p.add_argument('--split', default='all', help='all, development или reserved_evaluation')
    p.add_argument('--limit', type=int, default=0, help='Только первые N вопросов для отладки; метрики не считаются')
    return p


def execute(args):
    for v in args.variants:
        parse_variant(v)
    ensure(args.limit >= 0, '--limit не может быть отрицательным')
    cfg = load_v3_config(args.config)
    retr = HybridRetrieverV3(cfg=cfg)
    from retrieval_eval.qrels_io import load_questions, load_qrels
    from retrieval_eval.scoring import evaluate
    from retrieval_eval.common import digest
    questions = load_questions(retr.v2cfg)
    qrels = load_qrels(retr.v2cfg)
    if args.limit:
        questions = questions[:args.limit]
    out = cfg['_results']/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    ensure(inside(out, cfg['_results']), 'Неверная папка результатов')
    out.mkdir(parents=True, exist_ok=False)
    print(f'Вопросов: {len(questions)}; чанков: {len(retr.chunks)}; стеммер: {retr.tokenizer.kind}; результаты: {out}')
    table = []
    for variant in args.variants:
        t0 = time.time()
        runs = retr.search_batch(questions, variant)
        vdir = out/variant.replace('+', '__')
        vdir.mkdir()
        slim = [{**r, 'results': [{k: v for k, v in x.items() if k != 'content'} for x in r['results']]} for r in runs]
        write_json(vdir/'runs.json', {'schema_version': 'v3-search-1', 'variant': variant,
                                      'corpus_sha256': retr.manifest['chunk_set_sha256'],
                                      'questions_sha256': digest(questions), 'runs': slim}, cfg['_results'])
        if args.limit:
            print(f'{variant}: выдача сохранена ({time.time()-t0:.0f} с), метрики пропущены из-за --limit')
            continue
        metrics = evaluate(qrels, runs, retr.v2cfg['k_values'], questions)
        metrics.update({'schema_version': 'v3-metrics-1', 'variant': variant,
                        'corpus_sha256': retr.manifest['chunk_set_sha256'],
                        'qrels_version': qrels.get('artifact_version'), 'questions_sha256': digest(questions),
                        'settings': {k: v for k, v in cfg.items() if not k.startswith('_')},
                        'stemmer': retr.tokenizer.kind})
        write_json(vdir/'metrics.json', metrics, cfg['_results'])
        row = {'Шаг': variant, **summarize(metrics, args.split)}
        table.append(row)
        print(f"{variant}: Hit@1={row['Hit@1']:.4f} Hit@5={row['Hit@5']:.4f} MRR@10={row['MRR@10']:.4f} ({time.time()-t0:.0f} с)")
    if table:
        with (out/f'summary_{args.split}.csv').open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]), delimiter=';')
            w.writeheader()
            for row in table:
                w.writerow({k: str(round(v, 4)).replace('.', ',') if isinstance(v, float) else v for k, v in row.items()})
        write_json(out/f'summary_{args.split}.json', table, cfg['_results'])
        print(f'Сводка: {out/f"summary_{args.split}.csv"}')
    return {'results': str(out), 'variants': len(args.variants), 'status': 'evaluated' if table else 'runs_only'}


def main(argv=None):
    args = get_parser().parse_args(argv)
    try:
        execute(args)
    except V3Error as e:
        print(f'Ошибка V3: {e}')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
