from pathlib import Path
import sys

def bootstrap():
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'src/retrieval_eval').is_dir():
            sys.path.insert(0,str(root/'src'))
            return root
    raise RuntimeError('Не найдена папка V2')

V2=bootstrap()
from retrieval_eval.common import read_json

def select_profile(name):
    config=read_json(V2/'configs/model_profiles.json')
    for profile in config['profiles']:
        if profile['name']==name:
            return dict(profile)
    raise ValueError('Неизвестный профиль: '+str(name))

def available_profiles():
    return read_json(V2/'configs/model_profiles.json')['profiles']
