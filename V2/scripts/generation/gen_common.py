"""Общие функции генерации и LLM-судьи V2 (только стандартная библиотека Python)."""
import hashlib, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

V2 = Path(__file__).resolve().parents[2]
ROOT = V2.parent

# Системная подсказка первого проекта (src/rag/rag_service.py, PUE_SYSTEM) — без изменений,
# чтобы генерация V2 была сопоставима с v5.
PUE_SYSTEM = ("Ты помощник по Правилам устройства электроустановок (ПУЭ). "
              "Отвечай только на основе приведённого контекста. "
              "Если ответа нет в контексте — так и скажи. "
              "Указывай номера пунктов ПУЭ из контекста.")


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def run_dir(kind, label):
    base = V2 / 'results' / 'generation' / kind
    d = base / (datetime.now().strftime('%Y%m%d_%H%M%S') + ('_' + label if label else ''))
    d.mkdir(parents=True, exist_ok=False)
    return d


def in_root(value):
    p = Path(value)
    p = (ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.exists():
        sys.exit(f'ОШИБКА: нет файла {p}')
    return p


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def write_new(p, obj):
    with open(p, 'x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def read_jsonl(p):
    rows = []
    if Path(p).exists():
        for line in open(p, encoding='utf-8'):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_questions(p):
    d = read_json(p)
    qs = d['questions'] if isinstance(d, dict) else d
    return {str(q['id']): q for q in qs}


def doc_name(meta):
    src = meta.get('Document') or meta.get('source_file') or ''
    return Path(src.replace('\\', '/')).stem


def format_context(results, top_k, max_chars):
    parts, used = [], []
    for i, r in enumerate(results[:top_k], 1):
        meta = r.get('metadata') or {}
        text = r['content']
        cut = len(text) > max_chars
        if cut:
            text = text[:max_chars] + ' […фрагмент обрезан…]'
        clause = meta.get('Clause') or ''
        head = f'[Фрагмент {i}] ПУЭ, глава {doc_name(meta)}' + (f', пункт {clause}' if clause else '')
        parts.append(head + '\n' + text)
        used.append({'rank': i, 'chunk_id': r['chunk_id'], 'clause': clause, 'document': doc_name(meta),
                     'chars': len(r['content']), 'truncated': cut})
    return '\n\n'.join(parts), used


def progress(label, done, total, started):
    el = time.monotonic() - started
    eta = el / done * (total - done) if done else 0
    print(f'[{datetime.now():%H:%M:%S}] {label}: {done}/{total}, прошло {el/60:.1f} мин, осталось ~{eta/60:.1f} мин', flush=True)


def ollama(host, payload, timeout, retries=2):
    url = host.rstrip('/') + '/api/generate'
    data = json.dumps(payload).encode('utf-8')
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'Ollama не ответила: {last}')


def ollama_check(host, model):
    try:
        with urllib.request.urlopen(host.rstrip('/') + '/api/tags', timeout=10) as r:
            names = [m.get('name') for m in json.loads(r.read().decode('utf-8')).get('models', [])]
    except Exception as e:
        sys.exit(f'ОШИБКА: Ollama недоступна по {host}: {e}. Запустите Ollama (python scripts/infra_start_system/start_ollama.py).')
    if model not in names:
        sys.exit(f'ОШИБКА: в Ollama нет модели {model}. Есть: {names}. Выполните: ollama pull {model}')


CLAUSE_RE = re.compile(r'(?<![\d.])(\d{1,2}\.\d{1,2}\.\d{1,3})(?![\d])')


def clauses_in(text):
    return set(CLAUSE_RE.findall(text or ''))
