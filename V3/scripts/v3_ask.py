#!/usr/bin/env python3
"""Вопрос к V3: гибридный поиск и ответ Qwen2.5 со ссылками на пункты ПУЭ.

Запуск из папки V3:
    python scripts/v3_ask.py "Какие испытания перечислены в п. 1.8.16?"
    python scripts/v3_ask.py "..." --variant bm25_e5+rerank --top-k 5 --no-llm"""
import argparse
import json
import sys
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3 / 'src'))
from retrieval_v3.hybrid_retriever import HybridRetrieverV3, parse_variant, V3Error
from retrieval_v3.rag_pipeline import V3RAGPipeline


def get_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('question')
    p.add_argument('--config', help='по умолчанию V3/configs/v3_config.json')
    p.add_argument('--variant', default='bm25_e5_clip+rerank+exact')
    p.add_argument('--top-k', type=int, default=5)
    p.add_argument('--no-llm', action='store_true', help='Только поиск, без ответа LLM')
    p.add_argument('--ollama-url', default='http://localhost:11434')
    p.add_argument('--model', default='qwen2.5:14b-instruct-q4_K_M')
    return p


def execute(args):
    parse_variant(args.variant)
    retr = HybridRetrieverV3(args.config)
    if args.no_llm:
        for r in retr.search(args.question, variant=args.variant, limit=args.top_k):
            mark = ' | по номеру' if r['exact_clause'] else ''
            print(f"{r['rank']}. {r['metadata'].get('Clause')}{mark} | {r['content'][:200].replace(chr(10), ' ')}")
        return {'status': 'search_only'}
    rag = V3RAGPipeline(ollama_url=args.ollama_url, model_name=args.model)
    result = rag.ask(args.question, retr, variant=args.variant, top_k=args.top_k)
    print(json.dumps(result['retrieved'], ensure_ascii=False, indent=1))
    print(result['answer'])
    return result


def main(argv=None):
    args = get_parser().parse_args(argv)
    try:
        result = execute(args)
    except V3Error as e:
        print(f'Ошибка V3: {e}')
        return 2
    return 1 if result.get('status') == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
