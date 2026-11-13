#!/usr/bin/env python3
"""Поиск по набору вопросов без ответа в ПУЭ (eval_questions_refusal.json) той же конфигурацией, что опыт 4.

Нужны Milvus с готовой коллекцией diplom_v2_rerank и видеокарта (как для run_pipeline.py). Коллекция только читается.
Результат — retrieval.json в формате выдачи V2 (runs[]), его принимает generate.py.
Пишется в новую папку V2/results/generation/refusal_retrieval/<время>_<метка>/, старые файлы не меняются.
"""
import argparse, json, sys
from gen_common import V2, ROOT, now, run_dir, in_root, sha256_file, read_json, write_new

sys.path.insert(0, str(V2 / 'src'))
from retrieval_eval.common import load_config, ensure            # noqa: E402
from retrieval_eval.corpus_manifest import load_corpus, index_signature  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='V2/configs/pipeline_manual_merged_split_extra.json')
    p.add_argument('--mode', default='rerank')
    p.add_argument('--questions', default='V2/data/rag_eval_questions/eval_questions_refusal.json')
    p.add_argument('--label', default='refusal')
    a = p.parse_args()

    config = load_config(V2, str(ROOT), a.config)
    mode = config['modes'][a.mode]
    qpath = in_root(a.questions)
    data = read_json(qpath)
    qs = data['questions']
    ensure(qs and all(q.get('id') and q.get('query') and q.get('answerability') == 'not_in_pue' for q in qs),
           'В наборе нужны id, query и answerability = not_in_pue у каждого вопроса')
    ensure(len({q['id'] for q in qs}) == len(qs), 'Повторяющиеся id вопросов')
    print(f'Конфиг: {a.config}, режим {a.mode}, коллекция {mode["collection"]}, кандидатов {mode.get("candidate_depth")}, '
          f'устройство {config.get("device")}; вопросов: {len(qs)}', flush=True)

    chunks, _locations, manifest = load_corpus(config)
    from retrieval_eval.backend import search
    runs = search(config, a.mode, qs, chunks, manifest)

    out = run_dir('refusal_retrieval', a.label)
    snap = {'schema_version': 'v2-search-1', 'created_at': now(), 'mode': a.mode,
            'search_depth': config['search_depth'], 'index_signature': index_signature(manifest, mode),
            'manifest': manifest, 'questions': str(qpath.relative_to(ROOT)), 'questions_sha256_file': sha256_file(qpath),
            'config': a.config, 'runs': runs, 'resources_mode': 'text_only', 'clip_enabled': False,
            'search_settings': {'mode': mode, 'clip': None}, 'rerank_model': mode.get('rerank_model'),
            'note': 'Выдача по набору без ответа в ПУЭ; метрики Hit@k для него не считаются (эталона нет).'}
    write_new(out / 'retrieval.json', snap)
    rel = (out / 'retrieval.json').relative_to(ROOT)
    print(json.dumps({'retrieval': str(rel), 'questions': len(runs),
                      'next': f'python V2/scripts/generation/generate.py --input {rel} --questions {a.questions} --label refusal'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
