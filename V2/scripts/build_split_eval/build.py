#!/usr/bin/env python3
"""Сборка разбитого набора вопросов и qrels 1.0 из проверенного Excel. Python >= 3.9.

Запуск из корня проекта (Windows: python, Linux: python3):
  python V2/scripts/build_split_eval/build.py --project-root .
  python V2/scripts/build_split_eval/build.py --project-root . --overwrite

Вход (не изменяется):
  V2/data/rag_eval_questions/Вопросы_разбиение_все_главы.xlsx  — лист «Вопросы»
  V2/data/rag_eval_questions/eval_questions.json               — исходные 268 вопросов
  V2/data/chunked_merged_manual                                — активный корпус (без _audit)
Выход (рядом с xlsx):
  eval_questions_split.json   — 720 вопросов: исходные 268 + части X.1, X.2 ...
  eval_qrels_split.json       — qrels схемы 1.0 по точному совпадению текста эталона с чанками
  split_build_report.md       — что не совпало, дубли, ресурсы

Как строятся qrels: каждый абзац эталонного ответа (дословный текст корпуса)
ищется как подстрока в content чанков. Найденный чанк получает content-оценку 2
и цитату со смещениями. clause_qrels = 1 для чанков, чей metadata.Clause входит
в пункты вопроса. LLM, сеть и Milvus не используются. Старые eval_questions.json
и retrieval_qrels.json не изменяются. Смысловую проверку эталонов делает человек.
"""
import argparse
import importlib.util
import json
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

QDIR = 'V2/data/rag_eval_questions'
COLS = {'new': 'Новый №', 'orig': 'Исходный №', 'query': 'Вопрос',
        'answer': 'Эталонный ответ (дословно из корпуса)', 'clauses': 'Пункт ПУЭ',
        'tables': 'Таблицы и рисунки', 'orig_query': 'Исходная формулировка вопроса',
        'notes': 'Замечания', 'marks': 'Ваши пометки'}
INHERIT = ('section', 'refusal_policy', 'critical_errors', 'scoring_note',
           'split_group', 'split', 'split_status', 'source_paths')


def load_tool(root):
    p = root / 'V2/scripts/prepare_retrieval_qrels.py'
    spec = importlib.util.spec_from_file_location('v2_qrels_tool', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_rows(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, read_only=True)['Вопросы']
    it = ws.iter_rows(values_only=True)
    head = [str(h or '').strip() for h in next(it)]
    idx = {k: head.index(v) for k, v in COLS.items() if v in head}
    for need in ('new', 'orig', 'query', 'answer', 'clauses'):
        if need not in idx:
            sys.exit(f'В листе «Вопросы» нет столбца «{COLS[need]}»')
    rows = []
    for r in it:
        if not r or r[idx['new']] in (None, ''):
            continue
        row = {k: ('' if r[i] is None else str(r[i]).strip()) for k, i in idx.items()}
        row['answer'] = str(r[idx['answer']] or '').replace('\r\n', '\n')
        rows.append(row)
    return rows


HEAD = re.compile(r'^(ПУЭ|табл\.)\s*([\d.]+):\s*$')


def answer_facts(answer):
    """Блоки «ПУЭ X:» / «табл. X:» → абзацы; строки таблицы Markdown — один абзац."""
    facts = []
    for block in re.split(r'\n\s*\n', answer.strip()):
        lines = block.split('\n')
        m = HEAD.match(lines[0].strip())
        kind, ref = (m.group(1), m.group(2)) if m else (None, None)
        body = lines[1:] if m else lines
        buf = []
        for ln in body:
            if ln.startswith('|') and buf and buf[-1].startswith('|'):
                buf[-1] += '\n' + ln
            elif ln.strip():
                buf.append(ln)
        for t in buf:
            facts.append({'source_clause': ref if kind == 'ПУЭ' else None,
                          'source_table': ref if kind == 'табл.' else None, 'text': t})
    return facts


def split_list(s):
    return [x.strip() for x in re.split(r'[,;]\s*', s or '') if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-root', default='.')
    ap.add_argument('--xlsx', default=f'{QDIR}/Вопросы_разбиение_все_главы.xlsx')
    ap.add_argument('--questions', default=f'{QDIR}/eval_questions.json')
    ap.add_argument('--chunks', default='V2/data/chunked_merged_manual')
    ap.add_argument('--out-dir', default=QDIR)
    ap.add_argument('--overwrite', action='store_true')
    a = ap.parse_args()
    root = Path(a.project_root).resolve()
    T = load_tool(root)
    src_path, out = T.resolve(root, a.questions), T.resolve(root, a.out_dir)
    f_q, f_r, f_m = out/'eval_questions_split.json', out/'eval_qrels_split.json', out/'split_build_report.md'
    for f in (f_q, f_r, f_m):
        if f.exists() and not a.overwrite:
            sys.exit(f'Уже существует {f}; удалите или запустите с --overwrite')
    src_data, src_qs = T.load_questions(src_path)
    orig = {str(q['id']): q for q in src_qs}
    rows = read_rows(T.resolve(root, a.xlsx))
    folder = T.resolve(root, a.chunks)
    chunks, locations, files, order = T.load_corpus(root, folder)

    # --- проверки Excel ---
    ids = [r['new'] for r in rows]
    dup_ids = sorted({i for i in ids if ids.count(i) > 1})
    if dup_ids:
        sys.exit(f'Повтор номеров в Excel: {dup_ids}')
    missing = [i for i in orig if i not in ids]
    if missing:
        sys.exit(f'В Excel нет исходных вопросов: {missing}')
    changed = [r['new'] for r in rows if r['new'] in orig and r['query'] != orig[r['new']]['query']]
    unknown_orig = [r['new'] for r in rows if r['orig'] not in orig]
    if unknown_orig:
        sys.exit(f'Неизвестный исходный № у строк: {unknown_orig}')

    # --- вопросы ---
    by_clause = defaultdict(list)
    for cid, c in chunks.items():
        by_clause[str(c['metadata'].get('Clause', '')).strip()].append(cid)
    questions, report_nomatch, report_multi, dups, img_facts = [], [], [], [], []
    qrels, clause_qrels, chunk_rec, evidence, qrows = {}, {}, {}, {}, []
    for r in rows:
        o = orig[r['orig']]
        is_orig = r['new'] == r['orig']
        facts = answer_facts(r['answer'])
        if not facts:
            sys.exit(f'Пустой эталон: {r["new"]}')
        clauses = split_list(r['clauses'])
        tabfig = split_list(r.get('tables', ''))
        tables = [t.split()[-1] for t in tabfig if t.startswith('табл')]
        figures = [t.split()[-1] for t in tabfig if t.startswith('рис')]
        q = OrderedDict()
        q['id'] = r['new']
        q['source_question_id'] = r['orig']
        q['is_original_question'] = is_orig
        q['registry_id'] = o.get('registry_id') if is_orig else None
        q['query'] = r['query']
        q['expected_clause'] = clauses[0] if clauses else o.get('expected_clause')
        q['required_clauses'] = clauses
        q['required_tables'] = tables
        q['required_figures'] = figures
        q['question_revision'] = o.get('question_revision', 1) if is_orig else 1
        q['dataset_version'] = 'split-720-v1'
        q['reference_answer'] = r['answer']
        q['mandatory_answer_facts'] = facts
        for k in INHERIT:
            if k in o:
                q[k] = o[k]
        q['duplicate_of'] = None  # заполняется ниже по совпадению эталонов
        q['review_notes'] = r.get('notes', '')
        q['reviewer_marks'] = r.get('marks', '')
        if is_orig and o.get('reference_answer') != r['answer']:
            q['original_reference_answer'] = o.get('reference_answer')
        questions.append(q)

        # --- qrels ---
        qid = r['new']
        cvals = set(clauses) | ({q['expected_clause']} if q['expected_clause'] else set())
        content, judgments, all_ok = {}, [], True
        for i, f in enumerate(facts, 1):
            pool = by_clause.get(f['source_clause'] or '', [])
            # В части чанков строки таблиц разделены CRLF: ищем оба варианта,
            # цитата берётся точно в том виде, как в content.
            variants = [f['text']] + ([f['text'].replace('\n', '\r\n')] if '\n' in f['text'] else [])
            hits, quote = [], f['text']
            for v in variants:
                hits = [cid for cid in pool if v in chunks[cid]['content']] or \
                       [cid for cid in chunks if v in chunks[cid]['content']]
                if hits:
                    quote = v
                    break
            if len(hits) > 1:
                own = [h for h in hits if str(chunks[h]['metadata'].get('Clause', '')).strip() in cvals]
                report_multi.append((qid, i, len(hits)))
                hits = own[:1] or hits[:1]
            if 'assets/' in f['text'] and '.png' in f['text']:
                img_facts.append((qid, i))
            ev_sets = []
            if hits:
                cid = hits[0]
                st = chunks[cid]['content'].index(quote)
                eid = f'{qid}#f{i}'
                evidence[eid] = {'chunk_id': cid, 'start_char': st, 'end_char': st+len(quote),
                                 'quote': quote, 'quote_sha256': T.sha(quote.encode())}
                ev_sets.append({'all_of_chunk_ids': [cid], 'evidence_ids': [eid],
                                'text_only_complete': True, 'with_linked_assets_complete': False})
                content[cid] = 2
            else:
                all_ok = False
                report_nomatch.append((qid, i, f['source_clause'] or f['source_table'], f['text'][:90]))
            judgments.append({'gold_fact_index': i, 'gold_fact': f, 'evidence_sets': ev_sets,
                              'required_for_coverage': True, 'requires_asset_ids': []})
        own = {cid: 1 for cl in cvals for cid in by_clause.get(cl, [])}
        qrels[qid], clause_qrels[qid] = content, own
        for cid in list(content) + list(own):
            chunk_rec[cid] = {'path': locations[cid]['path'], 'line': locations[cid]['line'],
                              'content_sha256': T.sha(chunks[cid]['content'].encode()),
                              'metadata_sha256': T.sha(T.stable(chunks[cid]['metadata']))}
        qrows.append({'qid': qid, 'query': r['query'], 'question_revision': q['question_revision'],
                      'split': q.get('split', 'unspecified'), 'required_clauses': clauses,
                      'source_question_id': r['orig'], 'duplicate_of': None,
                      'fact_judgments': judgments,
                      'full_answer_scoring_eligible_text_only': all_ok,
                      'full_answer_scoring_eligible_with_linked_assets': False,
                      'issues': [] if all_ok else ['не все абзацы эталона найдены в чанках']})

    # Дубли: одинаковый эталон. Исходные вопросы никогда не помечаются дублями;
    # часть помечается ссылкой на исходный вопрос либо на первую часть с тем же эталоном.
    def key(x):
        return [int(v) for v in x.split('.')]
    groups = defaultdict(list)
    for q in questions:
        groups[q['reference_answer'].strip()].append(q)
    qrow_by = {x['qid']: x for x in qrows}
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda q: (not q['is_original_question'], key(q['id'])))
        for q in g[1:]:
            if q['is_original_question']:
                dups.append((q['id'], g[0]['id'] + ' (оба исходные, оставлены оба)'))
                continue
            q['duplicate_of'] = qrow_by[q['id']]['duplicate_of'] = g[0]['id']
            dups.append((q['id'], g[0]['id']))

    now = datetime.now().astimezone().isoformat(timespec='seconds')
    qdata = OrderedDict()
    qdata['title'] = 'Вопросы ПУЭ: 268 исходных + разбиение на одно требование'
    qdata['source_file'] = Path(a.xlsx).name
    qdata['n_questions'] = len(questions)
    qdata['metadata'] = {'version': 'split-720-v1', 'created_at': now,
                         'base_dataset': (src_data.get('metadata') or {}).get('version'),
                         'base_file_sha256': T.sha(src_path.read_bytes()),
                         'original_questions': len(orig),
                         'split_parts': sum(1 for q in questions if not q['is_original_question']),
                         'rules': ['Исходные вопросы сохранены с прежними номерами и формулировками.',
                                   'Части X.1, X.2 … — одно требование из одного пункта.',
                                   'Эталонный ответ — дословные абзацы корпуса chunked_merged_manual.',
                                   'Каждый абзац эталона — отдельный обязательный факт.']}
    for k in ('evaluation_protocol',):
        if k in src_data:
            qdata[k] = src_data[k]
    qdata['questions'] = questions
    out.mkdir(parents=True, exist_ok=True)
    f_q.write_text(json.dumps(qdata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    _, qs_loaded = T.load_questions(f_q)
    art = OrderedDict()
    art['schema_version'] = '1.0'
    art['artifact_version'] = 'split-720-exact-text-v1'
    art['status'] = 'exact_text_match_from_reviewed_answers'
    art['ready_for_scoring'] = True
    art['created_at'] = now
    art['method'] = ('Абзацы эталонных ответов, проверенных человеком в Excel, найдены как точные '
                     'подстроки в content чанков. content=2 — чанк содержит абзац эталона; '
                     'clause=1 — собственный пункт чанка (metadata.Clause) входит в пункты вопроса. '
                     'Неразмеченные чанки не доказаны нерелевантными.')
    art['corpus_version'] = T.corpus_info(files, chunks, None)
    art['question_dataset'] = T.dataset_info(qdata, qs_loaded, f_q)
    art['qrels'], art['clause_qrels'] = qrels, clause_qrels
    art['chunks'], art['evidence'], art['assets'] = chunk_rec, evidence, {}
    art['questions'] = qrows
    art['summary'] = {'questions': len(qrows), 'facts': sum(len(q['fact_judgments']) for q in qrows),
                      'facts_without_chunk': len(report_nomatch),
                      'questions_fully_matched': sum(q['full_answer_scoring_eligible_text_only'] for q in qrows),
                      'content_pairs': sum(len(v) for v in qrels.values()),
                      'clause_pairs': sum(len(v) for v in clause_qrels.values())}
    f_r.write_text(json.dumps(art, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    res = T.validate(root, folder, f_q, json.loads(f_r.read_text(encoding='utf-8')))

    L = ['# Отчёт сборки eval_questions_split / eval_qrels_split', '',
         f'Создано: {now}', '',
         f'- Вопросов: {len(questions)} (исходных {len(orig)}, частей {qdata["metadata"]["split_parts"]})',
         f'- Абзацев эталона (фактов): {art["summary"]["facts"]}; без найденного чанка: {len(report_nomatch)}',
         f'- Вопросов, где найдены все абзацы: {art["summary"]["questions_fully_matched"]}',
         f'- Пар content: {art["summary"]["content_pairs"]}; пар clause: {art["summary"]["clause_pairs"]}',
         f'- Структурная проверка prepare_retrieval_qrels.validate: {res["structural_validation"]}', '']
    if changed:
        L += ['## Исходные вопросы с изменённой формулировкой', '', ', '.join(changed), '']
    L += ['## Абзацы без найденного чанка', '']
    L += [f'- {q} факт {i} ({c}): {t}' for q, i, c, t in report_nomatch] or ['нет']
    L += ['', '## Абзац найден в нескольких чанках (взят чанк собственного пункта)', '']
    L += [f'- {q} факт {i}: {n} чанков' for q, i, n in report_multi] or ['нет']
    L += ['', '## Дубли (duplicate_of)', '']
    L += [f'- {a_} совпадает с {b}' for a_, b in dups] or ['нет']
    L += ['', '## Абзацы со ссылками на изображения (ресурсы не регистрировались, засчитывается только текст)', '']
    L += [', '.join(sorted({q for q, _ in img_facts}, key=lambda x: [int(v) for v in x.split('.')]))] or ['нет']
    f_m.write_text('\n'.join(L) + '\n', encoding='utf-8')
    print(json.dumps({'questions': len(questions), **art['summary'],
                      'validation': res['structural_validation'],
                      'outputs': [str(f_q), str(f_r), str(f_m)]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
