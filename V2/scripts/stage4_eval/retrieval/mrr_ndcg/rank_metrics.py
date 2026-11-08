from pathlib import Path
import sys

def bootstrap():
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'src/retrieval_eval').is_dir():
            sys.path.insert(0,str(root/'src'))
            return root
    raise RuntimeError('Не найдена папка V2')

bootstrap()
from retrieval_eval.scoring import ranked_metrics, fact_coverage, evaluate
__all__=['ranked_metrics','fact_coverage','evaluate']
