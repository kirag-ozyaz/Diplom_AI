from pathlib import Path
import sys

def bootstrap():
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'src/retrieval_eval').is_dir():
            sys.path.insert(0,str(root/'src'))
            return root
    raise RuntimeError('Не найдена папка V2')

bootstrap()
from retrieval_eval.api import RetrievalClient

class RAG(RetrievalClient):
    """Совместимость только с новым RetrievalClient; генерации ответа нет."""
    def __init__(self,project_root=None,config=None):
        super().__init__('rerank',project_root,config)

def create_retriever(project_root=None,config=None):
    return RAG(project_root,config)
