#!/usr/bin/env python3
"""Новый CLI V2; исходная версия проекта не импортируется."""
from pathlib import Path
import importlib.util
import sys


def entrypoint(argv=None):
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'scripts/run_pipeline.py').is_file():
            spec=importlib.util.spec_from_file_location('v2_standalone_pipeline',root/'scripts/run_pipeline.py')
            runner=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
            return runner.main(['evaluate', '--mode', 'e5'] + (list(argv) if argv is not None else sys.argv[1:]))
    raise RuntimeError('Не найдена папка V2')


if __name__ == '__main__':
    raise SystemExit(entrypoint())
