"""Генерация ответа V3: Qwen2.5:14b-instruct через Ollama со ссылками на пункты ПУЭ.
LLM участвует только в ответе; поиск выполняет retrieval_v3.hybrid_retriever."""
import requests
from retrieval_v3.hybrid_retriever import ensure

PUE_SYSTEM_PROMPT = ('Ты эксперт-помощник по Правилам устройства электроустановок (ПУЭ). '
                     'Отвечай строго на основе предоставленного контекста. '
                     'Если ответа нет в контексте - явно сообщи об этом. '
                     'Обязательно указывай точные номера пунктов ПУЭ из контекста.')


class V3RAGPipeline:
    def __init__(self, ollama_url='http://localhost:11434', model_name='qwen2.5:14b-instruct-q4_K_M'):
        self.ollama_url, self.model_name = ollama_url, model_name

    def generate_answer(self, query, retrieved_chunks, top_k=5):
        ensure(type(top_k) is int and top_k > 0, 'top_k должен быть положительным целым')
        chunks = retrieved_chunks[:top_k]
        blocks = [f"[{i}] Фрагмент (Пункт {c.get('metadata', {}).get('Clause') or 'ПУЭ'}):\n{c.get('content', '').strip()}"
                  for i, c in enumerate(chunks, 1)]
        prompt = 'Контекст из ПУЭ:\n' + '\n\n'.join(blocks) + f'\n\nВопрос пользователя: {query}\nОтвет:'
        payload = {'model': self.model_name, 'system': PUE_SYSTEM_PROMPT, 'prompt': prompt, 'stream': False,
                   'options': {'temperature': 0.2, 'num_predict': 512, 'num_ctx': 8192}}
        try:
            resp = requests.post(f'{self.ollama_url}/api/generate', json=payload, timeout=120)
            resp.raise_for_status()
            answer = resp.json().get('response', '').strip()
        except (requests.RequestException, ValueError) as e:
            return {'answer': f'Ошибка генерации: {e}', 'sources': [], 'status': 'error'}
        return {'answer': answer, 'sources': [c.get('metadata', {}).get('Clause') for c in chunks],
                'status': 'success'}

    def ask(self, query, retriever, variant='bm25_e5_clip+rerank+exact', top_k=5):
        """Поиск (HybridRetrieverV3) и ответ со ссылками на пункты ПУЭ."""
        chunks = retriever.search(query, variant=variant, limit=top_k)
        result = self.generate_answer(query, chunks, top_k=top_k)
        result['retrieved'] = [{'rank': c['rank'], 'clause': c['metadata'].get('Clause'), 'chunk_id': c['chunk_id'],
                                'exact_clause': c['exact_clause']} for c in chunks]
        return result
