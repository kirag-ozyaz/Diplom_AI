#!/usr/bin/env python3
"""Создать отдельный конфиг V2 для уже подготовленного ручного корпуса.
Не копирует чанки, не меняет старые конфиги и не обращается к базе/моделям.
Python 3.9+, стандартная библиотека. Запускать из корня проекта.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def configure(v2, source='V2/configs/pipeline_manual.json',
              chunks='V2/data/chunked_merged_manual',
              output='V2/configs/pipeline_manual_merged.json'):
    v2 = Path(v2).resolve()
    root = v2.parent
    def resolve(value):
        path = (root / value).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Путь вне проекта: ' + str(path))
        return path
    src, dest, corpus = resolve(source), resolve(output), resolve(chunks)
    if not src.is_relative_to(v2 / 'configs') or not dest.is_relative_to(v2 / 'configs'):
        raise ValueError('Конфиги должны находиться в V2/configs')
    if dest.exists():
        raise ValueError('Конфиг уже существует; выберите новый --output-config: ' + str(dest))
    config = json.loads(src.read_text(encoding='utf-8-sig'))
    if config.get('schema_version') != 'v2-pipeline-1':
        raise ValueError('Неизвестная схема конфига')
    spec = importlib.util.spec_from_file_location('configured_qrels_tool', v2 / 'scripts/prepare_retrieval_qrels.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not getattr(module, 'EXCLUDES_AUDIT', False):
        raise ValueError('Сначала установите исправленный prepare_retrieval_qrels.py из этого архива')
    rows, _, files, _ = module.load_corpus(root, corpus)
    # Меняется только путь корпуса; модели, вопросы и параметры остаются пользовательскими.
    config['paths']['chunks'] = corpus.relative_to(root).as_posix()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'status': 'new_config_created', 'config': str(dest),
            'chunks_folder': config['paths']['chunks'], 'documents_jsonl': len(files),
            'chunks': len(rows), 'audit_excluded': True, 'old_config_unchanged': True,
            'database_write_performed': False,
            'note': 'Новые коллекции и совместимые qrels настраиваются отдельно до поиска/оценки.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-config', default='V2/configs/pipeline_manual.json')
    parser.add_argument('--chunks', default='V2/data/chunked_merged_manual')
    parser.add_argument('--output-config', default='V2/configs/pipeline_manual_merged.json')
    args = parser.parse_args()
    try:
        result = configure(Path(__file__).resolve().parents[1], args.from_config, args.chunks, args.output_config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc), 'database_write_performed': False}, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    sys.exit(main())
