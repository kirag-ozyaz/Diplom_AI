import hashlib
import json
import re
import sys
from pathlib import Path
from datetime import datetime


class V2Error(ValueError):
    pass


def ensure(test, message):
    if not test:
        raise V2Error(message)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def path_in(root, value):
    p = Path(value)
    p = (root / p).resolve() if not p.is_absolute() else p.resolve()
    ensure(inside(p, root), f'Путь вне проекта: {p}')
    return p


def write_json(path, obj, v2):
    ensure(inside(path, v2), f'Запись вне V2 запрещена: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Никакого автоматического перезаписывания даже своих результатов.
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def timestamp():
    return datetime.now().astimezone().isoformat()


def run_id():
    return datetime.now().strftime('%Y%m%d_%H%M%S_%f')


def tool(v2):
    # Импорт исключительно переданного файла V2, не одноимённого модуля проекта.
    import importlib.util
    p = v2 / 'scripts/prepare_retrieval_qrels.py'
    spec = importlib.util.spec_from_file_location('v2_qrels_tool', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_config(v2, project_root=None, config=None):
    v2 = v2.resolve()
    root = Path(project_root).resolve() if project_root else v2.parent
    ensure(v2.parent == root, 'Папка V2 должна находиться непосредственно в корне проекта')
    p = path_in(root, config) if config else v2 / 'configs/pipeline.json'
    ensure(inside(p, v2 / 'configs'), 'Конфигурация должна находиться в V2/configs')
    c = read_json(p)
    ensure(c.get('schema_version') == 'v2-pipeline-1', 'Неизвестная схема pipeline.json')
    for name in ('raw', 'chunks', 'questions', 'qrels', 'results'):
        c['paths'][name] = path_in(root, c['paths'][name])
    ensure(inside(c['paths']['results'], v2 / 'results/retrieval'), 'Неверная папка результатов')
    ensure(c['paths']['chunks'].is_dir(), 'Нет папки активных чанков')
    ensure(c['paths']['questions'].is_file(), 'Нет файла вопросов')
    allow = c.get('allowed_collections', [])
    ensure(allow and len(allow) == len(set(allow)), 'Нужен явный список коллекций V2 без повторов')
    ensure(all(re.fullmatch(r'diplom_v2_[A-Za-z0-9_]+', x) for x in allow),
           'Разрешены только коллекции с префиксом diplom_v2_')
    for name, mode in c['modes'].items():
        ensure(mode['collection'] in allow, f'Неразрешённая коллекция режима {name}')
        ensure(int(mode['dimension']) > 0, 'Неверная размерность')
    ensure(type(c['batch_size']) is int and c['batch_size'] > 0, 'batch_size должен быть положительным целым')
    ensure(isinstance(c['k_values'], list) and c['k_values'] and all(type(k) is int and k > 0 for k in c['k_values']), 'Нужен непустой список положительных целых k')
    ensure(type(c['search_depth']) is int and c['search_depth'] >= max(c['k_values']) > 0, 'Глубина поиска меньше требуемого k')
    ensure(c['search_depth'] <= 1000, 'Глубина поиска должна быть не больше 1000')
    profile_name = c.get('model_selection',{}).get('profile')
    if profile_name:
        profiles = read_json(v2/'configs/model_profiles.json')['profiles']
        selected = next((x for x in profiles if x['name']==profile_name),None)
        ensure(selected is not None, 'Неизвестное имя профиля моделей')
        dimensions = read_json(v2/'configs/embedding_config.json')['text_model_dim']
        model_name = selected['text_model']
        ensure(model_name in dimensions, 'Для модели профиля не задана размерность')
        c['modes']['base'].update({'model':model_name,'dimension':dimensions[model_name],
             'query_prefix':'query: ' if 'e5' in model_name.lower() else '',
             'passage_prefix':'passage: ' if 'e5' in model_name.lower() else ''})
    c['_root'], c['_v2'], c['_config_path'] = root, v2, p
    return c


def progress(label, done, total, started, unit='батч'):
    """Строка прогресса в stderr: сделано/всего, прошло, осталось (оценка)."""
    import sys
    import time
    from datetime import timedelta
    spent = time.monotonic() - started
    left = spent / done * (total - done) if done else 0
    fmt = lambda s: str(timedelta(seconds=int(s)))
    print(f'[{datetime.now():%H:%M:%S}] {label}: {unit} {done}/{total} ({done*100//max(total,1)}%), '
          f'прошло {fmt(spent)}, осталось ~{fmt(left)}', file=sys.stderr, flush=True)
