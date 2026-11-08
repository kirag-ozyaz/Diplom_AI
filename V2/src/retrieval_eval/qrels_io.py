from .common import ensure, read_json, tool


def load_questions(config):
    return tool(config['_v2']).load_questions(config['paths']['questions'])[1]


def load_qrels(config):
    obj = read_json(config['paths']['qrels'])
    ensure(obj.get('schema_version') == '1.0', 'Нужна принятая схема qrels 1.0, не кандидаты')
    ensure(obj.get('ready_for_scoring') is not False, 'Файл явно запрещён для итоговой оценки')
    # Созданные скриптом кандидаты не превращаются в эталон сменой имени файла.
    ensure(obj.get('status') != 'unreviewed_candidates', 'Кандидаты не приняты')
    result = tool(config['_v2']).validate(config['_root'], config['paths']['chunks'],
                                         config['paths']['questions'], obj)
    ensure(result['structural_validation'] == 'passed', 'Несовместимая разметка')
    return obj
