"""Гибридный поиск V3: BM25 + E5 + CLIP, слияние RRF, переранжирование BGE.
Корпус, вопросы и коллекции V2 только читаются; V3 ничего не пишет в V2 и в Milvus."""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

V3 = Path(__file__).resolve().parents[2]
# Номер пункта ПУЭ: 1.7.82, 2.5.1, 1.2 (не менее двух чисел через точку).
CLAUSE_RE = re.compile(r'(?<![\d.])\d{1,2}(?:\.\d{1,3}){1,3}(?![\d])')
WORD_RE = re.compile(r'[а-яёa-z]+', re.IGNORECASE)
NOT_CLAUSE_RE = re.compile(r'(табл\w*|рис\w*)\.?\s*$', re.IGNORECASE)
SOURCES = ('bm25', 'e5', 'clip')
FLAGS = ('rerank', 'fullchunk', 'exact')
DEFAULT = {'schema_version': 'v3-pipeline-1', 'project_root': '../..',
           'v2_config': 'V2/configs/pipeline_manual_merged_split.json',
           'device': 'cuda', 'clip_device': 'cuda', 'results_dir': 'results',
           'search_depth': 20, 'candidate_depth': 50, 'rrf_k': 60,
           'weights': {'bm25': 1.0, 'e5': 1.0, 'clip': 1.0},
           'bm25': {'k1': 1.5, 'b': 0.75, 'stemmer': 'snowball'},
           'exact_clause': {'enabled': True},
           'rerank': {'model': 'BAAI/bge-reranker-v2-m3', 'window_chars': 1500,
                      'window_overlap': 300, 'batch_size': 16}}


class V3Error(ValueError):
    pass


def ensure(test, message):
    if not test:
        raise V3Error(message)


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def load_v3_config(path=None):
    p = Path(path) if path else V3 / 'configs/v3_config.json'
    ensure(p.is_file(), f'Нет файла настроек V3: {p}')
    user = json.loads(p.read_text(encoding='utf-8-sig'))
    ensure(user.get('schema_version', DEFAULT['schema_version']) == DEFAULT['schema_version'],
           'Неизвестная схема v3_config.json')
    c = json.loads(json.dumps(DEFAULT))
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(c.get(key), dict):
            c[key].update(value)
        else:
            c[key] = value
    root = Path(c['project_root'])
    c['_root'] = (root if root.is_absolute() else p.parent / root).resolve()
    ensure((c['_root'] / 'V2/src/retrieval_eval').is_dir(), f'Нет кода V2 в {c["_root"] / "V2"}')
    results = Path(c['results_dir'])
    c['_results'] = (results if results.is_absolute() else V3 / results).resolve()
    ensure(inside(c['_results'], V3), 'Результаты V3 пишутся только внутри папки V3')
    ensure(c['device'] in ('cuda', 'cpu') and c['clip_device'] in ('cuda', 'cpu'), 'device: cuda или cpu')
    ensure(type(c['search_depth']) is int and 1 <= c['search_depth'] <= c['candidate_depth'] <= 1000,
           'Нужно 1 <= search_depth <= candidate_depth <= 1000')
    ensure(type(c['rrf_k']) is int and c['rrf_k'] > 0, 'rrf_k должен быть положительным целым')
    ensure(set(c['weights']) <= set(SOURCES) and all(float(w) >= 0 for w in c['weights'].values()),
           'Веса RRF только для bm25, e5, clip и не отрицательные')
    ensure(c['bm25']['stemmer'] in ('snowball', 'pymorphy', 'none'), 'stemmer: snowball, pymorphy или none')
    r = c['rerank']
    ensure(0 <= r['window_overlap'] < r['window_chars'] or r['window_chars'] == 0, 'Перекрытие окон больше окна')
    return c


def attach_v2(c):
    """Подключает код V2 и возвращает (настройки V2, чанки, расположения, манифест)."""
    src = str(c['_root'] / 'V2/src')
    if src not in sys.path:
        sys.path.insert(0, src)
    from retrieval_eval.common import load_config
    from retrieval_eval.corpus_manifest import load_corpus
    v2 = load_config(c['_root'] / 'V2', c['_root'], c['v2_config'])
    # Устройство берётся из настроек V3 (cuda), а не из копии V2, где может стоять cpu.
    v2['device'], v2['clip_device'] = c['device'], c['clip_device']
    ensure(max(v2['k_values']) <= c['search_depth'], 'search_depth V3 меньше наибольшего k V2')
    chunks, locations, manifest = load_corpus(v2)
    ensure(chunks, 'Пустой корпус V2')
    return v2, chunks, locations, manifest


def parse_variant(variant):
    parts = variant.split('+')
    sources = parts[0].split('_')
    ensure(sources and len(sources) == len(set(sources)) and set(sources) <= set(SOURCES),
           f'Неизвестный шаг поиска: {variant}')
    flags = set(parts[1:])
    ensure(flags <= set(FLAGS), f'Неизвестная добавка в шаге: {variant}')
    ensure('fullchunk' not in flags or 'rerank' in flags, '+fullchunk имеет смысл только с +rerank')
    return sources, flags


class Tokenizer:
    def __init__(self, stemmer='snowball'):
        self.kind, self._stem = 'none', lambda w: w
        if stemmer == 'snowball':
            try:
                import snowballstemmer
                self._stem, self.kind = snowballstemmer.stemmer('russian').stemWord, 'snowball'
            except ImportError:
                raise V3Error('Нужен snowballstemmer: pip install snowballstemmer') from None
        elif stemmer == 'pymorphy':
            try:
                import pymorphy3
            except ImportError:
                raise V3Error('Нужен pymorphy3: pip install pymorphy3') from None
            morph, cache = pymorphy3.MorphAnalyzer(), {}

            def lemma(w):
                if w not in cache:
                    cache[w] = morph.parse(w)[0].normal_form
                return cache[w]
            self._stem, self.kind = lemma, 'pymorphy3'

    def __call__(self, text):
        text = text.lower().replace('ё', 'е')
        clauses = CLAUSE_RE.findall(text)
        words = WORD_RE.findall(CLAUSE_RE.sub(' ', text))
        return ['#'+x for x in clauses] + [self._stem(w) for w in words if len(w) > 1]


class BM25:
    def __init__(self, docs, tokenizer, k1=1.5, b=0.75):
        ensure(k1 > 0 and 0 <= b <= 1, 'Неверные k1/b для BM25')
        self.tok, self.k1, self.b = tokenizer, k1, b
        self.ids = sorted(docs)
        self.tf = [Counter(tokenizer(docs[cid])) for cid in self.ids]
        df = Counter(t for c in self.tf for t in c)
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len)/len(self.len)
        n = len(self.ids)
        self.idf = {t: math.log(1+(n-f+0.5)/(f+0.5)) for t, f in df.items()}
        self.post = defaultdict(list)
        for i, c in enumerate(self.tf):
            for t in c:
                self.post[t].append(i)

    def search(self, query, limit):
        scores = defaultdict(float)
        for t in set(self.tok(query)):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.post[t]:
                f = self.tf[i][t]
                scores[i] += idf*f*(self.k1+1)/(f+self.k1*(1-self.b+self.b*self.len[i]/self.avg))
        best = sorted(scores, key=lambda i: (-scores[i], self.ids[i]))[:limit]
        return [(self.ids[i], scores[i]) for i in best]


def rrf(runs, weights, k):
    """runs: имя выдачи -> chunk_id по рангу. Возвращает [(chunk_id, оценка)]."""
    score = defaultdict(float)
    for name, ids in runs.items():
        ensure(len(ids) == len(set(ids)), f'Повторный чанк в выдаче {name}')
        for rank, cid in enumerate(ids, 1):
            score[cid] += weights.get(name, 1.0)/(k+rank)
    return sorted(score.items(), key=lambda x: (-x[1], x[0]))


def windows(text, size, overlap):
    if size <= 0 or len(text) <= size:
        return [text]
    step = size-overlap
    return [text[i:i+size] for i in range(0, max(len(text)-overlap, 1), step)]


class HybridRetrieverV3:
    """Шаги: bm25, e5, clip, bm25_e5, bm25_e5_clip; добавки +rerank (BGE по окнам),
    +fullchunk (BGE по целому чанку, как в V2), +exact (пункт по номеру из вопроса)."""

    def __init__(self, config_path=None, cfg=None):
        self.cfg = cfg or load_v3_config(config_path)
        self.v2cfg, self.chunks, self.locations, self.manifest = attach_v2(self.cfg)
        self.tokenizer = Tokenizer(self.cfg['bm25']['stemmer'])
        self.bm25 = BM25({c: v['content'] for c, v in self.chunks.items()}, self.tokenizer,
                         self.cfg['bm25']['k1'], self.cfg['bm25']['b'])
        self.clause_index = defaultdict(list)
        for cid in sorted(self.chunks):
            clause = str(self.chunks[cid]['metadata'].get('Clause', '')).strip()
            if clause:
                self.clause_index[clause].append(cid)
        self._reranker = self._milvus = self._e5 = self._clip = None

    def run_bm25(self, query, limit):
        return [cid for cid, _ in self.bm25.search(query, limit)]

    def _client(self):
        if self._milvus is None:
            from retrieval_eval.backend import _client
            self._milvus = _client(self.v2cfg)
        return self._milvus

    def run_e5_batch(self, questions, limit):
        # Поиск V2 сам сверяет подпись коллекции, число записей и тексты чанков.
        from retrieval_eval.backend import search, _encoder
        mode = {k: v for k, v in self.v2cfg['modes']['e5'].items() if k != 'rerank_model'}
        if self._e5 is None:
            self._e5 = _encoder(self.v2cfg, mode)
        cfg = {**self.v2cfg, 'search_depth': limit, 'modes': {**self.v2cfg['modes'], 'e5': mode}}
        runs = search(cfg, 'e5', questions, self.chunks, self.manifest, client=self._client(), encoder=self._e5)
        ensure(len(runs) == len(questions), 'E5 вернул неполную выдачу')
        return {r['qid']: [x['chunk_id'] for x in r['results']] for r in runs}

    def run_clip_batch(self, questions, limit):
        from retrieval_eval.backend import _vectors
        from retrieval_eval.clip_backend import asset_rows, clip_encoder, signature
        cfg, s = self.v2cfg, self.v2cfg['clip']
        name, client = s['collection'], self._client()
        ensure(name in cfg['allowed_collections'] and name.startswith('diplom_v2_'), 'Запрещённая коллекция CLIP')
        ensure(client.has_collection(collection_name=name), 'Нет CLIP-коллекции V2; поиск её не создаёт')
        ensure(client.describe_collection(collection_name=name).get('description') == 'v2clip:'+signature(cfg, self.manifest),
               'CLIP-коллекция собрана для другой версии корпуса')
        assets = asset_rows(cfg, self.chunks, self.locations, self.manifest, images_only=True)
        ensure(int(client.get_collection_stats(collection_name=name)['row_count']) == len(assets), 'Неполная CLIP-коллекция')
        client.load_collection(collection_name=name)
        if self._clip is None:
            self._clip = clip_encoder(cfg)
        mode = {'normalize_embeddings': True, 'dimension': s['dimension']}
        out = {}
        for q in questions:
            hits = client.search(collection_name=name, data=_vectors(self._clip, [q['query']], mode, 1),
                                 anns_field='vector', search_params={'metric_type': 'COSINE', 'params': {}},
                                 limit=limit, output_fields=['asset_id', 'sha256'], consistency_level='Strong')[0]
            ids = []
            for h in hits:
                aid = h['entity']['asset_id']
                ensure(aid in assets and assets[aid]['sha256'] == h['entity']['sha256'], 'Изменённый ресурс CLIP-индекса')
                ids += [cid for cid in assets[aid]['chunk_ids'] if cid not in ids]
            out[str(q['id'])] = ids
        return out

    def exact_clause_ids(self, query):
        ids = []
        for m in CLAUSE_RE.finditer(query):
            # «таблица 1.7.5», «рис. 2.5.1» - номер таблицы или рисунка, а не пункта.
            if NOT_CLAUSE_RE.search(query[max(0, m.start()-12):m.start()]):
                continue
            ids += [cid for cid in self.clause_index.get(m.group(0), []) if cid not in ids]
        return ids

    def rerank(self, query, ids, use_windows=True):
        r = self.cfg['rerank']
        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder(r['model'], device=self.cfg['device'],
                                          local_files_only=self.v2cfg['local_files_only'])
        size = r['window_chars'] if use_windows else 0
        pairs, owner = [], []
        for cid in ids:
            for w in windows(self.chunks[cid]['content'], size, r['window_overlap']):
                pairs.append((query, w))
                owner.append(cid)
        scores = self._reranker.predict(pairs, batch_size=r['batch_size'], show_progress_bar=False) if pairs else []
        ensure(len(scores) == len(pairs), 'Неполное переранжирование')
        best = {}
        for cid, s in zip(owner, scores):
            ensure(math.isfinite(float(s)), 'Некорректная оценка переранжирования')
            best[cid] = max(best.get(cid, -math.inf), float(s))
        return sorted(best.items(), key=lambda x: (-x[1], x[0]))

    def search_batch(self, questions, variant):
        """questions: [{'id', 'query'}]; variant, например 'bm25_e5_clip+rerank+exact'."""
        sources, flags = parse_variant(variant)
        ensure(len({str(q['id']) for q in questions}) == len(questions), 'Повторный id вопроса')
        depth, cand = self.cfg['search_depth'], self.cfg['candidate_depth']
        per_source = cand if ('rerank' in flags or len(sources) > 1) else depth
        pre = {}
        if 'e5' in sources:
            pre['e5'] = self.run_e5_batch(questions, per_source)
        if 'clip' in sources:
            pre['clip'] = self.run_clip_batch(questions, per_source)
        out = []
        for q in questions:
            qid = str(q['id'])
            runs = {s: self.run_bm25(q['query'], per_source) if s == 'bm25' else pre[s][qid] for s in sources}
            fused = rrf(runs, self.cfg['weights'], self.cfg['rrf_k'])
            exact = self.exact_clause_ids(q['query']) if 'exact' in flags and self.cfg['exact_clause']['enabled'] else []
            ids = exact + [c for c, _ in fused[:cand] if c not in exact]
            scored = dict(fused)
            if 'rerank' in flags:
                ranked = self.rerank(q['query'], ids, 'fullchunk' not in flags)
                scored = dict(ranked)
                # Найденный по номеру пункт остаётся первым и после BGE.
                ids = exact + [c for c, _ in ranked if c not in exact]
            results = [{'rank': n, 'chunk_id': c, 'score': scored.get(c), 'exact_clause': c in exact,
                        'content': self.chunks[c]['content'], 'metadata': self.chunks[c]['metadata']}
                       for n, c in enumerate(ids[:depth], 1)]
            out.append({'qid': qid, 'query': q['query'], 'question_revision': q.get('question_revision'),
                        'results': results, 'delivered_asset_ids': []})
        return out

    def search(self, query, variant='bm25_e5_clip+rerank+exact', limit=5):
        ensure(type(limit) is int and 1 <= limit <= self.cfg['search_depth'], 'limit от 1 до search_depth')
        return self.search_batch([{'id': 'adhoc', 'query': query}], variant)[0]['results'][:limit]
