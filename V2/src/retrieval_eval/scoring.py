"""Единая оценка: ни один поиск номера в тексте не участвует в зачёте."""
import math
from .common import ensure


def ranked_metrics(ids, grades, k, threshold):
    ensure(type(k) is int and k > 0, 'k должен быть положительным целым')
    positives = {cid for cid, g in grades.items() if g >= threshold}
    seen = set()
    effective, unknown, duplicates = [], 0, 0
    for cid in ids[:k]:
        if cid in seen:
            duplicates += 1
            effective.append(0)
            continue
        seen.add(cid)
        unknown += cid not in grades
        effective.append(grades.get(cid, 0))
    rank = next((i for i, g in enumerate(effective, 1) if g >= threshold), None)
    dcg = sum((2**g-1)/math.log2(i+1) for i,g in enumerate(effective, 1))
    ideal = sum((2**g-1)/math.log2(i+1) for i,g in enumerate(sorted(grades.values(), reverse=True)[:k],1))
    return {'hit': int(rank is not None) if positives else None,
            'rr': 1/rank if rank else 0.0 if positives else None,
            'ndcg_reference_set': dcg/ideal if ideal else None,
            'unjudged_at_k': unknown, 'duplicates_at_k': duplicates}


def fact_coverage(question, ids, delivered_assets):
    found = set(ids)
    texts, with_assets, required = 0, 0, 0
    for fact in question['fact_judgments']:
        if not fact.get('required_for_coverage', True):
            continue
        required += 1
        text_ok = asset_ok = False
        for ev in fact.get('evidence_sets', []):
            if not set(ev['all_of_chunk_ids']) <= found:
                continue
            text_ok |= bool(ev.get('text_only_complete', False))
            # Доступность ресурсов недостаточна: потребителю должны реально быть переданы эти asset_id.
            asset_ok |= bool(ev.get('with_linked_assets_complete', False)) and (
                set(fact.get('requires_asset_ids', [])) <= set(delivered_assets))
        texts += text_ok
        with_assets += asset_ok
    return {'required_facts': required, 'text_facts': texts, 'asset_facts': with_assets,
            'text_fact_recall': texts/required if required else None,
            'asset_fact_recall': with_assets/required if required else None,
            'all_text_facts': texts == required if required else None,
            'all_asset_facts': with_assets == required if required else None,
            'full_text_answer': texts == required if required and question.get('full_answer_scoring_eligible_text_only') else None,
            'full_asset_answer': with_assets == required if required and question.get('full_answer_scoring_eligible_with_linked_assets') else None}


def evaluate(qrels, runs, k_values, expected_questions, verified_assets=None):
    expected = {str(q['id']): q for q in expected_questions}
    by_q = {str(q['qid']): q for q in qrels['questions']}
    ensure(set(by_q) == set(expected), 'В qrels иной набор вопросов')
    ensure(len(runs) == len(expected), 'Выдача должна содержать все вопросы без пропусков')
    seen = set()
    rows = []
    for run in runs:
        qid = str(run['qid'])
        ensure(qid in expected and qid not in seen, 'Неизвестный/повторный qid в выдаче')
        seen.add(qid)
        ensure(run.get('query') == expected[qid]['query'], 'Изменён текст запроса в выдаче')
        available = set((verified_assets or {}).get(qid, []))
        ensure(set(run.get('delivered_asset_ids', [])) <= available, 'Передача изображений не подтверждена файлами и хешами')
        results = run['results']
        ensure(all(r.get('rank') == i for i,r in enumerate(results,1)), 'Непоследовательные ранги')
        ids = [r['chunk_id'] for r in results]
        metrics = {}
        for k in k_values:
            content = ranked_metrics(ids, qrels['qrels'][qid], k, 2)
            clause = ranked_metrics(ids, qrels['clause_qrels'][qid], k, 1)
            own = {r.get('metadata', {}).get('Clause') for r in results[:k]}
            required = set(by_q[qid].get('required_clauses', []))
            clause['required_clause_recall'] = len(own & required)/len(required) if required else None
            metrics[str(k)] = {'content': content, 'clause': clause,
                               'facts': fact_coverage(by_q[qid], ids[:k], set().union(*(set(r.get('delivered_asset_ids',[])) & available for r in results[:k])))}
        rows.append({'qid': qid, 'split': by_q[qid].get('split', 'unspecified'),
                     'metrics': metrics, 'issues': by_q[qid].get('issues', [])})
    summary = {}
    for split in ['all'] + sorted({r['split'] for r in rows}):
        subset = [r for r in rows if split == 'all' or r['split'] == split]
        summary[split] = {}
        for k in k_values:
            item = {'questions': len(subset)}
            for group in ('content', 'clause', 'facts'):
                names = sorted({n for r in subset for n in r['metrics'][str(k)][group]})
                item[group] = {}
                for name in names:
                    vals = [r['metrics'][str(k)][group][name] for r in subset
                            if r['metrics'][str(k)][group][name] is not None]
                    item[group][name] = {'mean': sum(vals)/len(vals) if vals else None,
                                         'denominator': len(vals)}
            summary[split][str(k)] = item
    return {'summary': summary, 'questions': rows,
            'interpretation': 'Неразмеченные пары получают нулевой зачёт только в эталонной области; это не доказанная нерелевантность. reserved_evaluation не новый слепой тест. Ресурсы засчитываются только после проверки файлов выдачи. Наличие CLIP-попадания не доказывает правильность формулы.'}
