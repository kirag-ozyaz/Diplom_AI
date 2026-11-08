import hashlib
import re
from .common import tool, canonical, digest, path_in


def load_corpus(config):
    t = tool(config['_v2'])
    chunks, locations, files, order = t.load_corpus(config['_root'], config['paths']['chunks'])
    # Ресурсы, на которые действительно ссылаются JSONL. Отсутствующие не скрываются.
    assets = {}
    for cid, c in chunks.items():
        pattern = r'!?\[[^\]]*\]\(([^)]+)\)|<img\b[^>]*?src=[\"\']([^\"\']+)[\"\']'
        for match in re.finditer(pattern, c['content'], re.IGNORECASE):
            target = (match.group(1) or match.group(2)).strip().strip('<>')
            if target.startswith(('http:', 'https:', 'data:')):
                assets[target] = {'status': 'external_not_fetched'}
                continue
            # Ссылки Markdown разрешаются относительно файла чанков.
            path = (config['_root'] / locations[cid]['path']).parent / target
            try:
                path = path_in(config['_root'], str(path))
                rel = path.relative_to(config['_root']).as_posix()
                assets[rel] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': 'present'} if path.is_file() else {'status': 'missing'}
            except ValueError:
                assets[target] = {'status': 'outside_project'}
    corpus_sha = digest([{'path': f['path'], 'sha256': f['sha256']} for f in files])
    manifest = {'chunk_set_sha256': corpus_sha, 'files': files,
                'jsonl_file_count': len(files), 'chunk_count': len(chunks),
                'assets': assets, 'assets_sha256': digest(assets),
                'warning': 'Хеши и структура не доказывают правильность собственного пункта/таблицы.'}
    return chunks, locations, manifest


def index_signature(manifest, mode):
    fields = ('model', 'dimension', 'passage_prefix', 'query_prefix', 'normalize_embeddings')
    return digest({'chunks': manifest['chunk_set_sha256'], 'assets': manifest['assets_sha256'],
                   'embedding': {k: mode[k] for k in fields}})
