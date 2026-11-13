#!/usr/bin/env python3
"""Prepare structural candidates from latest completed extraction; never write to a database."""
import argparse
import json
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2 / 'src'))
from retrieval_eval.common import load_config, write_json, run_id
from retrieval_eval.preparation import prepare_markdown
from check_extraction import select_input, audit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', help='Optional extraction folder relative to project root')
    p.add_argument('--config', help='Optional configuration under V2/configs')
    args = p.parse_args(argv)
    output = V2 / 'results/retrieval' / ('preparation_' + run_id())
    try:
        config = load_config(V2, config=args.config)
        source, selection = select_input(config['_root'], args.input)
        checked = audit(config['_root'], source, config['paths']['raw'])
        checked['input_selection'] = selection
        write_json(output / 'extraction_audit.json', checked, V2)
        if checked['counts']['errors']:
            raise ValueError('Извлечение содержит ошибки; чанки не созданы. См. ' + str(output/'extraction_audit.json'))
        result = prepare_markdown(config, str(source))
        result['input_selection'] = selection
        result['extraction_audit_counts'] = checked['counts']
        write_json(output / 'preparation.json', result, V2)
        summary = {'report': str(output/'preparation.json'), 'input': str(source),
                   'output': result['output'], 'status': result['status'],
                   'documents_input': result['documents_input'],
                   'documents_prepared': result['documents_prepared'], 'documents_skipped': 0,
                   'chunks': result['chunks'], 'assets_copied': result['assets_copied'],
                   'extraction_review': checked['counts']['review'],
                   'removed_control_tokens': result['removed_control_tokens'],
                   'unresolved_markup_tokens': result['unresolved_markup_tokens'],
                   'database_write_performed': False, 'ready_for_final_scoring': False}
        write_json(output / 'console.json', summary, V2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        error = {'status': 'failed', 'error': str(exc),
                 'note': 'Ничего не загружалось в базу. Проверяйте наличие корпуса и отчётов перед повторным запуском.'}
        try:
            write_json(output/'error.json', error, V2)
        except OSError:
            pass
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
