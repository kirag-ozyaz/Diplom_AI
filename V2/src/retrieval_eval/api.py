"""Новый API V2; совместимость со старыми классами не предполагается."""
from pathlib import Path
from .common import load_config
from .corpus_manifest import load_corpus
from .backend import load, search_extended


class RetrievalClient:
    def __init__(self, mode='base', project_root=None, config=None):
        v2=Path(__file__).resolve().parents[2]
        self.config=load_config(v2,project_root,config)
        self.mode=mode

    def load(self, allow_db_write=False, with_clip=False):
        chunks,locations,manifest=load_corpus(self.config)
        result=load(self.config,self.mode,chunks,manifest,allow_db_write)
        if with_clip:
            from .clip_backend import load_clip
            result['clip']=load_clip(self.config,chunks,locations,manifest,allow_db_write)
        return result

    def search(self, query, limit=5, with_clip=False):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('limit должен быть от 1 до 1000')
        chunks,locations,manifest=load_corpus(self.config)
        config={**self.config,'search_depth':limit}
        runs=search_extended(config,self.mode,[{'id':'adhoc','query':query}],chunks,locations,manifest,with_clip)
        return runs[0]['results']
