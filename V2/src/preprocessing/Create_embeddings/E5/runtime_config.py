from pathlib import Path
import sys

def bootstrap():
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'src/retrieval_eval').is_dir():
            sys.path.insert(0,str(root/'src'))
            return root
    raise RuntimeError('Не найдена папка V2')

V2=bootstrap()
from retrieval_eval.common import load_config

def load_runtime_config(project_root=None,config=None):
    return load_config(V2,project_root,config)
