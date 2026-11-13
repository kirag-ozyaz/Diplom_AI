#!/usr/bin/env python3
"""Генерация ответов по сохранённой выдаче V2 (retrieval.json). Milvus не нужен, только Ollama.

Модели передаются только вопрос (query) и первые top-k фрагментов выдачи; эталон не передаётся.
Ответы дописываются построчно в answers.jsonl, поэтому прерванный прогон можно продолжить (--resume).
"""
import argparse, json, sys, time
from pathlib import Path
from gen_common import (V2, ROOT, PUE_SYSTEM, now, run_dir, in_root, sha256_file, read_json, write_new,
                        read_jsonl, load_questions, format_context, progress, ollama, ollama_check)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='retrieval.json опыта (путь от корня проекта)')
    p.add_argument('--questions', default='V2/data/rag_eval_questions/eval_questions_split.json')
    p.add_argument('--label', default='', help='метка в имени папки результата, например rerank50')
    p.add_argument('--top-k', type=int, default=5)
    p.add_argument('--max-chars', type=int, default=4000, help='обрезка одного фрагмента, символов')
    p.add_argument('--host', default='http://localhost:11434')
    p.add_argument('--model', default='qwen2.5:14b-instruct-q4_K_M')
    p.add_argument('--temperature', type=float, default=0.2)
    p.add_argument('--num-predict', type=int, default=512)
    p.add_argument('--num-ctx', type=int, default=8192, help='окно контекста Ollama, токенов')
    p.add_argument('--timeout', type=int, default=300)
    p.add_argument('--limit', type=int, default=0, help='только первые N вопросов (пробный запуск)')
    p.add_argument('--only-originals', action='store_true', help='только 268 исходных вопросов')
    p.add_argument('--resume', help='папка прерванного прогона: дописать недостающие ответы')
    a = p.parse_args()

    inp = in_root(a.input); qpath = in_root(a.questions)
    snap = read_json(inp)
    questions = load_questions(qpath)
    runs = snap['runs']
    if a.only_originals:
        runs = [r for r in runs if '.' not in str(r['qid'])]
    if a.limit:
        runs = runs[:a.limit]
    missing = [r['qid'] for r in runs if str(r['qid']) not in questions]
    if missing:
        sys.exit(f'ОШИБКА: вопросов из выдачи нет в наборе: {missing[:5]}')
    ollama_check(a.host, a.model)

    if a.resume:
        out = in_root(a.resume)
        settings = read_json(out / 'run.json')['settings']
        if settings['input_sha256'] != sha256_file(inp):
            sys.exit('ОШИБКА: --resume указывает на прогон по другой выдаче')
    else:
        out = run_dir('answers', a.label)
        settings = {'input': str(inp.relative_to(ROOT)), 'input_sha256': sha256_file(inp),
                    'questions': str(qpath.relative_to(ROOT)), 'questions_sha256': sha256_file(qpath),
                    'retrieval_mode': snap.get('mode'), 'search_settings': snap.get('search_settings'),
                    'clip_enabled': snap.get('clip_enabled'), 'retrieval_created_at': snap.get('created_at'),
                    'top_k': a.top_k, 'max_chars': a.max_chars, 'model': a.model, 'host': a.host,
                    'temperature': a.temperature, 'num_predict': a.num_predict, 'num_ctx': a.num_ctx,
                    'system_prompt': PUE_SYSTEM, 'only_originals': a.only_originals, 'limit': a.limit,
                    'supplied_to_model': ['query', 'top-k fragments'], 'started_at': now()}
        write_new(out / 'run.json', {'settings': settings})
    done = {str(r['qid']) for r in read_jsonl(out / 'answers.jsonl') if not r.get('error')}
    todo = [r for r in runs if str(r['qid']) not in done]
    print(f'Папка: {out}\nВсего {len(runs)}, уже есть {len(done)}, осталось {len(todo)}', flush=True)

    started = time.monotonic()
    with open(out / 'answers.jsonl', 'a', encoding='utf-8', newline='\n') as f:
        for i, r in enumerate(todo):
            if i % 10 == 0:
                progress('генерация', i, len(todo), started)
            qid = str(r['qid']); q = questions[qid]
            context, used = format_context(r['results'], a.top_k, a.max_chars)
            prompt = f'Контекст из ПУЭ:\n\n{context}\n\nВопрос: {q["query"]}\n\nОтвет:'
            row = {'qid': qid, 'is_original': '.' not in qid, 'query': q['query'], 'contexts': used}
            t0 = time.monotonic()
            try:
                body = ollama(a.host, {'model': a.model, 'system': PUE_SYSTEM, 'prompt': prompt, 'stream': False,
                                       'options': {'temperature': a.temperature, 'num_predict': a.num_predict,
                                                   'num_ctx': a.num_ctx}}, a.timeout)
                row['answer'] = (body.get('response') or '').strip()
                row['prompt_tokens'] = body.get('prompt_eval_count')
                row['answer_tokens'] = body.get('eval_count')
                ed = body.get('eval_duration') or 0
                row['tokens_per_s'] = round(body['eval_count'] / (ed / 1e9), 2) if ed and body.get('eval_count') else None
                row['context_may_be_cut'] = bool(row['prompt_tokens'] and row['prompt_tokens'] >= a.num_ctx - 16)
                row['answer_hit_limit'] = bool(row['answer_tokens'] and row['answer_tokens'] >= a.num_predict)
            except Exception as e:
                row['answer'] = ''; row['error'] = str(e)
            row['elapsed_s'] = round(time.monotonic() - t0, 2)
            row['created_at'] = now()
            f.write(json.dumps(row, ensure_ascii=False) + '\n'); f.flush()
    progress('генерация', len(todo), len(todo), started)
    rows = read_jsonl(out / 'answers.jsonl')
    errors = [r['qid'] for r in rows if r.get('error')]
    print(json.dumps({'folder': str(out.relative_to(ROOT)), 'answers': len(rows), 'errors': errors[:20],
                      'next': 'python V2/scripts/generation/judge.py --answers ' + str((out / 'answers.jsonl').relative_to(ROOT))},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
