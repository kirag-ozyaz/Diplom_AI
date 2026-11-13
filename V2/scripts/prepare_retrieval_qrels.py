#!/usr/bin/env python3
"""Локальные кандидаты qrels и структурная проверка разметки. Python >= 3.9.

Запускать из корня проекта (Windows: python, Linux: python3):
  python V2/scripts/prepare_retrieval_qrels.py generate --project-root .
  python V2/scripts/prepare_retrieval_qrels.py validate --project-root . \
      --qrels V2/data/rag_eval_questions/retrieval_qrels.json
  python V2/scripts/prepare_retrieval_qrels.py self-test

Архивные каталоги _audit исключаются из корпуса, индекса и кандидатов.
По умолчанию читаются data/chunked и
V2/data/rag_eval_questions/eval_questions.json. Для новых чанков добавьте
--chunks V2/data/chunked. Все относительные пути заданы от --project-root.

generate пишет retrieval_qrels.candidates.json, НЕ проверенный эталон.
Точные совпадения фактов, метки пунктов, упоминания таблиц и соседние чанки
являются только подсказками проверяющему. Семантика, полнота таблиц, формулы,
условия и исключения автоматически не подтверждаются. Отсутствие кандидатов
не доказывает отсутствие ответа. Скрипт не использует LLM, сеть или Milvus,
не загружает зависимости, не изменяет источники и не пишет в репозиторий сам:
место сохранения выходного файла задаётся явно или стандартным путём V2.

validate проверяет кандидаты ЭТОГО скрипта либо выданный формат qrels 1.0:
контрольные суммы, вопросы, ID, цитаты, смещения, ссылки на доказательства и
контрольные суммы зарегистрированных изображений. Это НЕ проверка смысла,
НЕ экспертное принятие разметки и НЕ запуск поиска. Смена версии в JSON не
заменяет повторной проверки. Нельзя просто переименовать кандидаты в эталон.

Существующие выходные файлы не перезаписываются. Для повторного запуска
укажите новый --output. --corpus-version — необязательная метка пользователя,
а не подтверждение Git-коммита; реальная версия фиксируется хешами файлов.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
import unittest
from collections import defaultdict
from datetime import datetime
from pathlib import Path


EXCLUDES_AUDIT = True  # Используется безопасной настройкой конфига V2.


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def within(root, path):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve(root, name):
    path = Path(name)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    require(within(root, path), f'Путь вне корня проекта: {path}')
    return path


def relative(root, path):
    return path.resolve().relative_to(root).as_posix()


def norm(text):
    # Числа, запятые, точки, знаки сравнения и буквы НЕ удаляются.
    text = unicodedata.normalize('NFKC', text).casefold()
    text = text.translate(str.maketrans({'–': '-', '—': '-', '\u00ad': ''}))
    return re.sub(r'\s+', ' ', text).strip()


def load_questions(path):
    data = read_json(path)
    questions = data.get('questions') if isinstance(data, dict) else data
    require(isinstance(questions, list) and questions, 'Пустой/неизвестный набор вопросов')
    ids = set()
    for q in questions:
        require(isinstance(q, dict) and 'id' in q, 'У вопроса нет id')
        qid = str(q['id'])
        require(qid not in ids, f'Повтор id вопроса: {qid}')
        ids.add(qid)
        require(isinstance(q.get('query'), str) and q['query'].strip(), f'Нет query: {qid}')
        facts = q.get('mandatory_answer_facts')
        require(isinstance(facts, list) and facts, f'Нет обязательных фактов: {qid}')
        require(all(isinstance(f, dict) and isinstance(f.get('text'), str)
                    and f['text'].strip() for f in facts), f'Некорректные факты: {qid}')
        for name in ('required_clauses', 'required_tables'):
            require(isinstance(q.get(name, []), list), f'{name} должен быть списком: {qid}')
    return data, questions


def load_corpus(root, folder):
    root, folder = root.resolve(), folder.resolve()
    require(within(root, folder), f'Папка чанков вне проекта: {folder}')
    require(folder.is_dir(), f'Нет папки чанков: {folder}')
    require(not any(part.casefold() == '_audit' for part in folder.relative_to(root).parts),
            'Нельзя использовать архив _audit как активный корпус')
    # _audit содержит исходные и заменённые варианты JSONL, НЕ рабочие чанки.
    # Исключаем каталог ДО обхода, чтобы архив не попадал ни в индекс, ни в qrels.
    # Обычные вложенные каталоги документов по-прежнему поддерживаются.
    paths = []
    for directory, subdirs, filenames in os.walk(folder, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if d.casefold() != '_audit')
        for name in sorted(filenames):
            if not name.lower().endswith('.jsonl'):
                continue
            path = Path(directory) / name
            require(within(root, path), f'Ссылка за пределы проекта: {path}')
            require(not any(part.casefold() == '_audit' for part in path.resolve().relative_to(root).parts),
                    f'Ссылка из рабочего корпуса на архив _audit: {path}')
            paths.append(path)
    paths.sort(key=lambda p: relative(root, p))
    require(bool(paths), f'Нет JSONL: {folder}')
    chunks, locations, files, order = {}, {}, [], defaultdict(list)
    for path in paths:
        require(within(root, path), f'Ссылка за пределы проекта: {path}')
        raw = path.read_bytes()
        rel = relative(root, path)
        files.append({'path': rel, 'sha256': sha(raw)})
        for line, text in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
            if not text.strip():
                continue
            try:
                c = json.loads(text)
            except ValueError as e:
                raise Invalid(f'Некорректный JSON: {rel}:{line}: {e}') from e
            require(isinstance(c, dict), f'Чанк не является объектом: {rel}:{line}')
            cid = c.get('id')
            require(isinstance(cid, str) and cid.strip(), f'Нет строкового id: {rel}:{line}')
            require(cid not in chunks, f'Повтор chunk_id: {cid}')
            require(isinstance(c.get('content'), str) and c['content'].strip(), f'Нет content: {cid}')
            require(isinstance(c.get('metadata'), dict), f'Нет metadata: {cid}')
            chunks[cid] = c
            locations[cid] = {'path': rel, 'line': line}
            order[rel].append(cid)
    require(bool(chunks), 'Корпус не содержит чанков')
    return chunks, locations, files, order


def corpus_info(files, chunks, label):
    return {'label': label or 'local-sha256-snapshot',
            'label_is_user_supplied_not_git_verification': True,
            'jsonl_file_count': len(files), 'chunk_count': len(chunks),
            'files': files, 'chunk_set_sha256': sha(stable(files)),
            'fingerprint_algorithm': 'SHA256 canonical JSON [{path,sha256}], sorted paths',
            'rebuild_rule': 'Изменение текста/ID/метаданных/ресурсов требует перепроверки qrels.'}


def dataset_info(data, questions, path):
    meta = data.get('metadata', {}) if isinstance(data, dict) else {}
    return {'version': meta.get('version'), 'source_basename': path.name,
            'source_file_sha256': sha(path.read_bytes()),
            'questions_canonical_sha256': sha(stable(questions)),
            'question_count': len(questions)}


def clause_values(q):
    return {str(x) for x in q.get('required_clauses', [])} | (
        {str(q['expected_clause'])} if q.get('expected_clause') else set())


def table_number(value):
    found = re.search(r'(?<!\d)(\d+(?:\.\d+){2,})(?!\d)', str(value))
    return found.group(1) if found else str(value).strip()


def generate(root, folder, questions_path, label):
    data, questions = load_questions(questions_path)
    chunks, locations, files, order = load_corpus(root, folder)
    texts = {cid: norm(c['content']) for cid, c in chunks.items()}
    clause_index = defaultdict(set)
    for cid, c in chunks.items():
        clause_index[str(c['metadata'].get('Clause', '')).strip()].add(cid)
    neighbors = {}
    for ids in order.values():
        for i, cid in enumerate(ids):
            neighbors[cid] = ids[max(0, i - 1):i] + ids[i + 1:i + 2]
    candidates, stats = [], {'questions': len(questions), 'candidate_pairs': 0,
                             'questions_without_candidates': 0}
    for q in questions:
        found = defaultdict(lambda: {'reasons': [], 'full_text_fact_indices': [],
                                     'table_mentions': []})
        def reason(cid, text):
            if text not in found[cid]['reasons']:
                found[cid]['reasons'].append(text)
        for clause in clause_values(q):
            for cid in sorted(clause_index.get(clause, ())):
                reason(cid, 'own_clause_metadata:' + clause)
        for index, fact in enumerate(q['mandatory_answer_facts'], 1):
            needle = norm(fact['text'])
            # Короткие заголовки не объявляются содержательным совпадением.
            if len(needle) < 35:
                continue
            for cid, text in texts.items():
                if needle in text:
                    reason(cid, 'normalized_full_fact_text; requires_review')
                    found[cid]['full_text_fact_indices'].append(index)
        for table in q.get('required_tables', []):
            number = table_number(table)
            pattern = re.compile(r'(?<![\d.])' + re.escape(number) + r'(?!\d|\.\d)')
            for cid, text in texts.items():
                if pattern.search(text):
                    reason(cid, 'table_number_mention_only; not_proof_of_table_body')
                    found[cid]['table_mentions'].append(number)
        # Соседи помогают искать тело таблицы, попавшее в чужой пункт.
        for cid in list(found):
            for other in neighbors[cid]:
                reason(other, 'adjacent_to_candidate:' + cid)
        rows = []
        for cid in sorted(found):
            c = chunks[cid]
            rows.append({'chunk_id': cid, **locations[cid], **found[cid],
                         'metadata_clause': c['metadata'].get('Clause'),
                         'content_sha256': sha(c['content'].encode('utf-8')),
                         'metadata_sha256': sha(stable(c['metadata'])),
                         'status': 'unreviewed', 'grade': None})
        candidates.append({'qid': str(q['id']), 'query': q['query'],
                           'question_revision': q.get('question_revision'),
                           'split': q.get('split'), 'candidates': rows})
        stats['candidate_pairs'] += len(rows)
        stats['questions_without_candidates'] += not bool(rows)
    return {'schema_version': 'qrels-candidates-1.0',
            'artifact_version': 'local-candidates-v1', 'status': 'unreviewed_candidates',
            'ready_for_scoring': False, 'created_at': datetime.now().astimezone().isoformat(),
            'corpus_version': corpus_info(files, chunks, label),
            'question_dataset': dataset_info(data, questions, questions_path),
            'qrels': {}, 'clause_qrels': {}, 'questions': candidates, 'summary': stats,
            'review_instructions': [
                'Это отдельный формат кандидатов, не готовые qrels 1.0.',
                'Не индексировать этот файл, вопросы и эталоны в RAG-корпус.',
                'Проверить факты, условия, исключения, строки таблиц, единицы и ресурсы.',
                'Для составного факта указать все необходимые chunk_id одним evidence_set.',
                'Собственный пункт берётся из metadata.Clause, не из перекрёстной ссылки.',
                'Проверить ограничения исходника; не исправлять норму догадкой.',
                'После принятия разметки отдельно сформировать qrels 1.0 с цитатами и доказательствами.',
                'Нельзя превращать кандидаты в эталон одним переименованием или status=true.',
                'Никакой полноты семантического поиска этот подбор кандидатов не гарантирует.']}


def validate(root, folder, questions_path, artifact):
    _, questions = load_questions(questions_path)
    chunks, locations, files, _ = load_corpus(root, folder)
    cv, ds = artifact['corpus_version'], artifact['question_dataset']
    actual = {f['path']: f['sha256'] for f in files}
    expected = {f['path']: f['sha256'] for f in cv['files']}
    require(len(expected) == len(cv['files']), 'Повтор пути в манифесте')
    require(actual == expected, 'Изменён корпус: список JSONL, путь или SHA256 не совпадает')
    canonical_files = [{'path': f['path'], 'sha256': f['sha256']} for f in cv['files']]
    require(sha(stable(canonical_files)) == cv['chunk_set_sha256'], 'Неверный fingerprint корпуса')
    require(cv['chunk_count'] == len(chunks), 'Не совпадает число чанков')
    require(cv['jsonl_file_count'] == len(files), 'Не совпадает число JSONL')
    require(sha(stable(questions)) == ds['questions_canonical_sha256'], 'Изменён набор вопросов')
    require(sha(questions_path.read_bytes()) == ds['source_file_sha256'],
            'Изменены байты файла вопросов (даже если вопросы совпадают); нужна сверка версии')
    question_map = {str(q['id']): q for q in questions}
    rows = artifact['questions']
    require(isinstance(rows, list), 'questions должен быть списком')
    ids = [str(q['qid']) for q in rows]
    require(len(set(ids)) == len(ids) and set(ids) == set(question_map), 'Неполные/повторные qid')
    is_candidate = artifact.get('schema_version') == 'qrels-candidates-1.0'
    require(is_candidate or artifact.get('schema_version') == '1.0', 'Неподдерживаемая схема')
    referenced = set()
    for q in rows:
        source = question_map[str(q['qid'])]
        require(q.get('query') == source['query'], f'Изменён query: {q["qid"]}')
        require(q.get('question_revision') == source.get('question_revision'), 'Изменена ревизия вопроса')
        if is_candidate:
            require(artifact.get('ready_for_scoring') is False and artifact.get('qrels') == {}
                    and artifact.get('clause_qrels') == {}, 'Кандидаты ошибочно выданы за эталон')
            seen = set()
            for c in q['candidates']:
                cid = c['chunk_id']
                require(cid in chunks and cid not in seen, f'Неизвестный/повторный ID: {cid}')
                seen.add(cid)
                require(c['status'] == 'unreviewed' and c['grade'] is None, 'Автооценка не разрешена')
                require(c['path'] == locations[cid]['path'] and c['line'] == locations[cid]['line'],
                        f'Изменено расположение чанка: {cid}')
                require(c['content_sha256'] == sha(chunks[cid]['content'].encode()), 'Изменён текст')
                require(c['metadata_sha256'] == sha(stable(chunks[cid]['metadata'])), 'Изменены метаданные')
                require(c['metadata_clause'] == chunks[cid]['metadata'].get('Clause'), 'Изменён Clause')
                for i in c['full_text_fact_indices']:
                    require(type(i) is int and 1 <= i <= len(source['mandatory_answer_facts']),
                            'Неизвестный индекс факта')
                    require(norm(source['mandatory_answer_facts'][i-1]['text']) in norm(chunks[cid]['content']),
                            'Точное совпадение факта не воспроизводится')
                referenced.add(cid)
    if not is_candidate:
        for name in ('qrels', 'clause_qrels'):
            require(set(artifact[name]) == set(question_map), f'Неполные qid в {name}')
            for qid, mapping in artifact[name].items():
                for cid, grade in mapping.items():
                    require(cid in chunks and type(grade) is int and grade in (0, 1, 2),
                            f'Некорректная пара {qid}/{cid}')
                    referenced.add(cid)
                    if name == 'clause_qrels' and grade > 0:
                        require(str(chunks[cid]['metadata'].get('Clause', '')).strip()
                                in clause_values(question_map[qid]), 'Чужой собственный пункт')
        for cid, c in artifact['chunks'].items():
            require(cid in chunks, f'Неизвестный chunk_id: {cid}')
            require(c['path'] == locations[cid]['path'] and c['line'] == locations[cid]['line'],
                    f'Изменено расположение чанка: {cid}')
            require(c['content_sha256'] == sha(chunks[cid]['content'].encode()), 'Изменён текст')
            require(c['metadata_sha256'] == sha(stable(chunks[cid]['metadata'])), 'Изменены метаданные')
        require(referenced <= set(artifact['chunks']), 'Не все qrels имеют запись chunks')
        for ev in artifact['evidence'].values():
            cid = ev['chunk_id']
            require(cid in chunks, 'У доказательства неизвестный чанк')
            start, end = ev['start_char'], ev['end_char']
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(chunks[cid]['content']),
                    'Некорректные смещения цитаты')
            require(chunks[cid]['content'][start:end] == ev['quote'], 'Цитата не совпадает')
            require(sha(ev['quote'].encode()) == ev['quote_sha256'], 'Неверный SHA256 цитаты')
        for asset in artifact['assets'].values():
            p = resolve(root, asset['path'])
            require(p.is_file() and sha(p.read_bytes()) == asset['sha256'], f'Нет/изменён ресурс: {p}')
        for q in rows:
            facts = question_map[str(q['qid'])]['mandatory_answer_facts']
            judgments = q['fact_judgments']
            indexes = [j['gold_fact_index'] for j in judgments]
            require(sorted(indexes) == list(range(1, len(facts)+1)), 'Неполный/повторный список фактов')
            for fact in judgments:
                require(fact['gold_fact'] == facts[fact['gold_fact_index']-1], 'Изменён эталонный факт')
                for aid in fact.get('requires_asset_ids', []):
                    require(aid in artifact['assets'], 'Неизвестный ресурс факта')
                for evset in fact.get('evidence_sets', []):
                    cids = evset['all_of_chunk_ids']
                    require(bool(cids) and len(set(cids)) == len(cids), 'Пустой/повторный набор чанков')
                    require(set(cids) <= set(chunks), 'Неизвестный чанк в evidence_set')
                    require(bool(evset['evidence_ids']), 'Нет цитат в evidence_set')
                    evs = []
                    for eid in evset['evidence_ids']:
                        require(eid in artifact['evidence'], 'Неизвестная цитата')
                        evs.append(artifact['evidence'][eid]['chunk_id'])
                    require(set(evs) == set(cids), 'Цитаты не соответствуют составному набору')
    return {'structural_validation': 'passed', 'semantic_acceptance': 'not_performed',
            'live_retrieval_run': False, 'candidate_file': is_candidate,
            'question_count': len(questions), 'chunk_count': len(chunks),
            'referenced_chunk_count': len(referenced),
            'note': 'Это проверка структуры/совместимости, не истинности эталонов.'}


def save_new(root, folder, source, output, value):
    require(output != source and not within(folder, output), 'Нельзя писать в исходники/папку чанков')
    require(not within(root / 'data' / 'raw', output), 'Нельзя писать в raw')
    require(output.name != 'retrieval_qrels.json', 'Кандидаты не должны заменять готовый retrieval_qrels.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def self_test():
    class Tests(unittest.TestCase):
        def test_numbers_preserved(self):
            self.assertNotEqual(norm('1,5 мм'), norm('15 мм'))
            self.assertNotEqual(norm('не более 5'), norm('не менее 5'))
        def test_pipeline(self):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td).resolve()
                folder = root / 'data/chunked'
                folder.mkdir(parents=True)
                qpath = root / 'questions.json'
                fact = 'Обязательное требование: напряжение не более 220 В при указанных условиях.'
                qpath.write_text(json.dumps({'questions': [{'id': 1, 'query': 'Какое требование?',
                    'question_revision': 1, 'expected_clause': '1.2.3', 'required_clauses': ['1.2.3'],
                    'required_tables': ['1.2.10'], 'mandatory_answer_facts': [{'text': fact}]}]},
                    ensure_ascii=False), encoding='utf-8')
                corpus = [
                    {'id': 'own', 'content': fact, 'metadata': {'Clause': '1.2.3'}},
                    {'id': 'ref', 'content': 'См. пункт 1.2.3 и таблицу 1.2.10.', 'metadata': {'Clause': '9.9.9'}},
                    {'id': 'table', 'content': '| Условие | Значение |\n| A | 220 В |', 'metadata': {'Clause': '9.9.10'}}]
                path = folder / 'тест.jsonl'
                def write():
                    path.write_text('\n'.join(json.dumps(c, ensure_ascii=False) for c in corpus), encoding='utf-8')
                write()
                a = generate(root, folder, qpath, 'test')
                self.assertFalse(a['ready_for_scoring'])
                self.assertEqual(a['qrels'], {})
                rows = {c['chunk_id']: c for c in a['questions'][0]['candidates']}
                self.assertEqual(rows['ref']['full_text_fact_indices'], [])
                self.assertFalse(any('own_clause_metadata' in r for r in rows['ref']['reasons']))
                self.assertIn('table', rows)  # Сосед тела, не автоматическая оценка 2.
                self.assertEqual(validate(root, folder, qpath, a)['structural_validation'], 'passed')
                out = root / 'V2/candidates.json'
                save_new(root, folder, qpath, out, a)
                with self.assertRaises(FileExistsError):
                    save_new(root, folder, qpath, out, a)
                with self.assertRaises(Invalid):
                    save_new(root, folder, qpath, root/'retrieval_qrels.json', a)
                corpus[0]['content'] += ' Изменение'
                write()
                with self.assertRaises(Invalid):
                    validate(root, folder, qpath, a)
                corpus[0]['content'] = fact
                corpus.append(corpus[0].copy())
                write()
                with self.assertRaises(Invalid):
                    generate(root, folder, qpath, None)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('generate', 'validate'):
        p = sub.add_parser(name)
        p.add_argument('--project-root', required=True)
        p.add_argument('--chunks', default='data/chunked')
        p.add_argument('--questions', default='V2/data/rag_eval_questions/eval_questions.json')
        if name == 'generate':
            p.add_argument('--output', default='V2/data/rag_eval_questions/retrieval_qrels.candidates.json')
            p.add_argument('--corpus-version')
        else:
            p.add_argument('--qrels', required=True)
    sub.add_parser('self-test')
    args = parser.parse_args()
    if args.command == 'self-test':
        return self_test()
    root = Path(args.project_root).resolve()
    require(root.is_dir(), 'Корень проекта не существует')
    folder, qp = resolve(root, args.chunks), resolve(root, args.questions)
    if args.command == 'generate':
        a = generate(root, folder, qp, args.corpus_version)
        report = validate(root, folder, qp, a)
        out = resolve(root, args.output)
        save_new(root, folder, qp, out, a)
        print(json.dumps({'written': str(out), **a['summary'], **report}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(validate(root, folder, qp, read_json(resolve(root, args.qrels))),
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Invalid, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ОШИБКА: {exc}', file=sys.stderr)
        sys.exit(2)
