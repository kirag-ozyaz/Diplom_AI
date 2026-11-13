#!/usr/bin/env python3
"""LLM-судья V2: оценка ответов из answers.jsonl по 5 критериям набора (evaluation_protocol.content_grading).

Для вопросов с нормативным ответом судья видит вопрос, эталонные обязательные факты, правила отказа,
критические ошибки, пять переданных модели фрагментов и сам ответ. Каждый критерий 0/1/2.
Для вопросов набора без ответа в ПУЭ (answerability = not_in_pue) судья проверяет правильность отказа.
Результат дописывается построчно в judgments.jsonl (можно продолжить --resume), итог — judge_metrics.json.
"""
import argparse, json, re, statistics, sys, time
from pathlib import Path
from gen_common import (ROOT, now, run_dir, in_root, sha256_file, read_json, write_new, read_jsonl,
                        load_questions, progress, ollama, ollama_check, clauses_in)

CRITERIA = [
    ('facts', 'Соответствие вопросу и обязательным фактам'),
    ('numbers', 'Точность чисел, единиц, знаков и условий'),
    ('exceptions', 'Сохранение исключений и области применения'),
    ('sources', 'Подтверждение утверждений источниками'),
    ('refusal', 'Обоснованность отказа либо полнота частичного ответа'),
]
JUDGE_SYSTEM = ('Ты строгий и беспристрастный проверяющий ответов по ПУЭ. Оцениваешь только по переданным материалам, '
                'ничего не додумываешь. Отвечаешь только JSON-объектом без пояснений вне JSON.')
REFUSAL_RE = re.compile(r'(нет (такой |этой |данной )?информаци|не содерж|отсутству|не приведен|не указан|нет ответа|'
                        r'не могу (дать|ответить|сказать)|не найден|не упомина|нет сведений|не располага|не рассматрива|'
                        r'в (приведённом|приведенном|предоставленном|данном) (контексте|тексте|фрагмент)[^.]{0,40}нет)', re.I)


def cut(t, n):
    t = t or ''
    return t if len(t) <= n else t[:n] + ' […]'


def fragments_text(row, snap_runs, max_chars):
    run = snap_runs.get(row['qid'])
    if not run:
        return '(фрагменты недоступны)'
    by_id = {r['chunk_id']: r for r in run['results']}
    out = []
    for c in row['contexts']:
        r = by_id.get(c['chunk_id'])
        if r:
            out.append(f'[Фрагмент {c["rank"]}] глава {c["document"]}' + (f', пункт {c["clause"]}' if c['clause'] else '')
                       + '\n' + cut(r['content'], max_chars))
    return '\n\n'.join(out)


def prompt_answerable(q, row, frags, max_chars):
    facts = '\n'.join(f'- (п. {f.get("source_clause") or "—"}) {cut(f["text"], max_chars)}' for f in q['mandatory_answer_facts'])
    pol = q.get('refusal_policy') or {}
    crit = '\n'.join(f'{i}. {key}: {name}' for i, (key, name) in enumerate(CRITERIA, 1))
    return f'''ВОПРОС:
{q["query"]}

ЭТАЛОН (обязательные факты из ПУЭ, модель их не видела):
{facts}

ПРАВИЛА ОЦЕНКИ ИЗ НАБОРА:
- {q.get("scoring_note", "")}
- Критические ошибки: {"; ".join(q.get("critical_errors") or [])}
- Когда отказ обоснован: {"; ".join(pol.get("refuse_unsubstantiated_part_when") or [])}
- Не отказывать только потому, что: {pol.get("do_not_refuse_only_because", "")}

ФРАГМЕНТЫ, КОТОРЫЕ ПОЛУЧИЛА МОДЕЛЬ:
{frags}

ОТВЕТ МОДЕЛИ:
{row["answer"] or "(пустой ответ)"}

Оцени ответ по каждому критерию баллом 0, 1 или 2:
{crit}
Шкала: 2 — полностью выполнено; 1 — частично (есть пропуски или неточности, не меняющие смысл); 0 — не выполнено или есть ошибка, меняющая смысл.
Пояснения: facts — передан ли смысл всех обязательных фактов, относящихся к вопросу; numbers — совпадают ли с эталоном числа, единицы, знаки неравенства и условия (если чисел в эталоне нет и ответ их не выдумал — 2); exceptions — сохранены ли исключения и область применения (если их нет и ответ не расширил норму — 2); sources — подтверждаются ли утверждения ответа фрагментами и указаны ли верные пункты; refusal — если модель отказалась полностью или частично, обоснован ли отказ содержимым фрагментов; если не отказывалась, полон ли ответ (2 — полный, 1 — неполный, 0 — необоснованный отказ или пустой ответ).

Верни JSON строго такого вида:
{{"facts": 0, "numbers": 0, "exceptions": 0, "sources": 0, "refusal": 0, "refused": false, "critical_error": false, "comment": "одно-два предложения"}}
где refused — модель отказалась отвечать по существу (полностью или частично), critical_error — есть критическая ошибка из правил набора.'''


def prompt_unanswerable(q, row, frags):
    return f'''ВОПРОС (заведомо без ответа в ПУЭ: {q.get("why_not_in_pue", "")}):
{q["query"]}

ОЖИДАЕМОЕ ПОВЕДЕНИЕ: {q.get("expected_behavior", "Сообщить, что в ПУЭ (в приведённых фрагментах) ответа нет, не выдумывать норму, число или пункт.")}

ФРАГМЕНТЫ, КОТОРЫЕ ПОЛУЧИЛА МОДЕЛЬ:
{frags}

ОТВЕТ МОДЕЛИ:
{row["answer"] or "(пустой ответ)"}

Оцени:
- refusal_correct: 2 — модель ясно сообщила, что ответа во фрагментах/ПУЭ нет, и не выдала норму; 1 — отказалась, но при этом привела посторонние требования как будто они отвечают на вопрос, или отказ неясен; 0 — ответила по существу, выдав норму, число или пункт, которых нет во фрагментах.
- hallucination: true, если в ответе есть число, требование или номер пункта, которых нет во фрагментах.
Верни JSON строго такого вида:
{{"refusal_correct": 0, "refused": false, "hallucination": false, "comment": "одно-два предложения"}}'''


def parse(text, keys):
    try:
        obj = json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text or '', re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return None
    for k in keys:
        if k not in obj:
            return None
    return obj


def clamp(v):
    try:
        return max(0, min(2, int(round(float(v)))))
    except Exception:
        return None


def summarize(rows):
    def agg(sel):
        if not sel:
            return None
        res = {'n': len(sel)}
        ok = [r for r in sel if r.get('scores')]
        res['judged'] = len(ok)
        for k, _ in CRITERIA:
            v = [r['scores'][k] for r in ok if r['scores'].get(k) is not None]
            res[k] = round(statistics.mean(v) / 2, 4) if v else None
        tot = [sum(r['scores'][k] for k, _ in CRITERIA) / 10 for r in ok if all(r['scores'].get(k) is not None for k, _ in CRITERIA)]
        res['total'] = round(statistics.mean(tot), 4) if tot else None
        res['all_criteria_ge1'] = round(sum(all(r['scores'][k] >= 1 for k, _ in CRITERIA) for r in ok if all(r['scores'].get(k) is not None for k, _ in CRITERIA)) / len(ok), 4) if ok else None
        res['all_criteria_2'] = round(sum(all(r['scores'][k] == 2 for k, _ in CRITERIA) for r in ok if all(r['scores'].get(k) is not None for k, _ in CRITERIA)) / len(ok), 4) if ok else None
        res['critical_error_rate'] = round(sum(bool(r['judge'].get('critical_error')) for r in ok) / len(ok), 4) if ok else None
        res['refused_rate_judge'] = round(sum(bool(r['judge'].get('refused')) for r in ok) / len(ok), 4) if ok else None
        res['refused_rate_regex'] = round(sum(r['auto']['refusal_phrase'] for r in sel) / len(sel), 4)
        res['clause_in_answer'] = round(sum(r['auto']['required_clause_in_answer'] for r in sel) / len(sel), 4)
        res['clause_in_context'] = round(sum(r['auto']['required_clause_in_context'] for r in sel) / len(sel), 4)
        return res

    ans = [r for r in rows if r['kind'] == 'answerable']
    un = [r for r in rows if r['kind'] == 'not_in_pue']
    out = {'answerable': {'all': agg(ans), 'originals': agg([r for r in ans if r['is_original']]),
                          'parts': agg([r for r in ans if not r['is_original']]),
                          'development': agg([r for r in ans if r.get('split') == 'development']),
                          'reserved_evaluation': agg([r for r in ans if r.get('split') == 'reserved_evaluation'])}}
    if un:
        ok = [r for r in un if r.get('judge')]
        out['not_in_pue'] = {
            'n': len(un), 'judged': len(ok),
            'refusal_correct_mean': round(statistics.mean(r['judge']['refusal_correct'] for r in ok) / 2, 4) if ok else None,
            'correct_refusal_rate': round(sum(r['judge']['refusal_correct'] == 2 for r in ok) / len(ok), 4) if ok else None,
            'answered_instead_rate': round(sum(r['judge']['refusal_correct'] == 0 for r in ok) / len(ok), 4) if ok else None,
            'hallucination_rate': round(sum(bool(r['judge'].get('hallucination')) for r in ok) / len(ok), 4) if ok else None,
            'refused_rate_regex': round(sum(r['auto']['refusal_phrase'] for r in un) / len(un), 4),
            'by_category': {c: {'n': len(g), 'correct_refusal_rate': round(sum(r['judge']['refusal_correct'] == 2 for r in g if r.get('judge')) / max(1, len([r for r in g if r.get('judge')])), 4)}
                            for c in sorted({r.get('category') for r in un}) for g in [[r for r in un if r.get('category') == c]]}}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--answers', required=True, help='answers.jsonl после generate.py')
    p.add_argument('--label', default='')
    p.add_argument('--host', default='http://localhost:11434')
    p.add_argument('--model', default='qwen2.5:14b-instruct-q4_K_M')
    p.add_argument('--num-ctx', type=int, default=8192)
    p.add_argument('--max-chars', type=int, default=1500, help='обрезка фрагмента и факта в подсказке судьи')
    p.add_argument('--timeout', type=int, default=300)
    p.add_argument('--resume', help='папка прерванной оценки')
    p.add_argument('--summary-only', action='store_true', help='только пересчитать judge_metrics по готовой папке --resume')
    a = p.parse_args()

    apath = in_root(a.answers); adir = apath.parent
    gen = read_json(adir / 'run.json')['settings']
    qpath = in_root(gen['questions']); questions = load_questions(qpath)
    snap = read_json(in_root(gen['input']))
    if sha256_file(in_root(gen['input'])) != gen['input_sha256']:
        sys.exit('ОШИБКА: retrieval.json изменился после генерации')
    snap_runs = {str(r['qid']): r for r in snap['runs']}
    latest = {}
    for r in read_jsonl(apath):
        latest[r['qid']] = r
    answers = [r for r in latest.values() if not r.get('error')]

    if a.resume:
        out = in_root(a.resume)
    else:
        out = run_dir('judge', a.label)
        write_new(out / 'run.json', {'settings': {'answers': str(apath.relative_to(ROOT)), 'answers_sha256_at_start': sha256_file(apath),
                                                  'generation': gen, 'judge_model': a.model, 'temperature': 0, 'num_ctx': a.num_ctx,
                                                  'max_chars': a.max_chars, 'criteria': CRITERIA, 'started_at': now(),
                                                  'limitation': 'Судья — та же модель, что генерировала ответы (решение автора 12.11.2026); оценки вспомогательные.'}})
    done = {r['qid'] for r in read_jsonl(out / 'judgments.jsonl') if r.get('judge')}
    todo = [] if a.summary_only else [r for r in answers if r['qid'] not in done]
    if todo:
        ollama_check(a.host, a.model)
    print(f'Папка: {out}\nОтветов {len(answers)}, уже оценено {len(done)}, осталось {len(todo)}', flush=True)
    started = time.monotonic()
    with open(out / 'judgments.jsonl', 'a', encoding='utf-8', newline='\n') as f:
        for i, row in enumerate(todo):
            if i % 10 == 0:
                progress('оценка', i, len(todo), started)
            q = questions[row['qid']]
            kind = 'not_in_pue' if q.get('answerability') == 'not_in_pue' else 'answerable'
            frags = fragments_text(row, snap_runs, a.max_chars)
            if kind == 'answerable':
                prompt, keys = prompt_answerable(q, row, frags, a.max_chars), [k for k, _ in CRITERIA]
            else:
                prompt, keys = prompt_unanswerable(q, row, frags), ['refusal_correct']
            req = set(q.get('required_clauses') or [])
            ctx_clauses = {c['clause'] for c in row['contexts']}
            res = {'qid': row['qid'], 'kind': kind, 'is_original': row['is_original'], 'split': q.get('split'),
                   'category': q.get('category'),
                   'auto': {'refusal_phrase': bool(REFUSAL_RE.search(row['answer'] or '')),
                            'required_clause_in_answer': bool(req & clauses_in(row['answer'])) if req else False,
                            'required_clause_in_context': bool(req & ctx_clauses) if req else False,
                            'clauses_in_answer_not_in_context': sorted(clauses_in(row['answer']) - ctx_clauses - clauses_in(frags))}}
            t0 = time.monotonic(); obj = None; raw = ''
            for attempt in range(2):
                try:
                    body = ollama(a.host, {'model': a.model, 'system': JUDGE_SYSTEM, 'prompt': prompt, 'stream': False, 'format': 'json',
                                           'options': {'temperature': 0, 'num_predict': 400, 'num_ctx': a.num_ctx}}, a.timeout)
                    raw = body.get('response') or ''
                    obj = parse(raw, keys)
                    res['prompt_tokens'] = body.get('prompt_eval_count')
                    if obj:
                        break
                except Exception as e:
                    res['error'] = str(e)
            res['elapsed_s'] = round(time.monotonic() - t0, 2)
            if obj:
                res.pop('error', None)
                res['judge'] = obj
                if kind == 'answerable':
                    res['scores'] = {k: clamp(obj.get(k)) for k, _ in CRITERIA}
                else:
                    obj['refusal_correct'] = clamp(obj.get('refusal_correct')) or 0
            else:
                res.setdefault('error', 'судья вернул не JSON'); res['raw'] = raw[:500]
            res['created_at'] = now()
            f.write(json.dumps(res, ensure_ascii=False) + '\n'); f.flush()
    progress('оценка', len(todo), len(todo), started)
    latest_j = {}
    for r in read_jsonl(out / 'judgments.jsonl'):
        if r.get('judge') or r['qid'] not in latest_j:
            latest_j[r['qid']] = r
    rows = list(latest_j.values())
    metrics = {'created_at': now(), 'answers': str(apath.relative_to(ROOT)), 'judge_model': a.model,
               'n_answers': len(answers), 'n_judged': sum(1 for r in rows if r.get('judge')),
               'failed_qids': [r['qid'] for r in rows if not r.get('judge')],
               'generation_errors': [r['qid'] for r in latest.values() if r.get('error')],
               'generation_mean_elapsed_s': round(statistics.mean(r['elapsed_s'] for r in answers), 2) if answers else None,
               'generation_mean_tokens_per_s': round(statistics.mean(r['tokens_per_s'] for r in answers if r.get('tokens_per_s')), 2) if any(r.get('tokens_per_s') for r in answers) else None,
               'context_may_be_cut': sum(bool(r.get('context_may_be_cut')) for r in answers),
               'answer_hit_limit': sum(bool(r.get('answer_hit_limit')) for r in answers),
               'scale': 'средний балл критерия / 2, от 0 до 1', **summarize(rows)}
    name = 'judge_metrics.json'
    k = 1
    while (out / name).exists():
        k += 1; name = f'judge_metrics_{k}.json'
    write_new(out / name, metrics)
    print(json.dumps({'folder': str(out.relative_to(ROOT)), 'metrics': name, 'judged': metrics['n_judged'],
                      'failed': metrics['failed_qids'][:20], 'answerable_all': metrics['answerable']['all'],
                      'not_in_pue': metrics.get('not_in_pue')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
