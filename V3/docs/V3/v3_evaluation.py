"""
Автономная оценка RAG V3 (Hit@k, MRR@k, nDCG@k).
"""

import math
from typing import Any, Dict, List, Set


def calculate_hit_at_k(retrieved_clauses: List[str], target_clauses: Set[str], k: int) -> float:
    top_k = retrieved_clauses[:k]
    return 1.0 if any(clause in target_clauses for clause in top_k) else 0.0

def calculate_mrr_at_k(retrieved_clauses: List[str], target_clauses: Set[str], k: int) -> float:
    for rank, clause in enumerate(retrieved_clauses[:k], 1):
        if clause in target_clauses:
            return 1.0 / rank
    return 0.0

def calculate_ndcg_at_k(retrieved_clauses: List[str], target_clauses: Set[str], k: int) -> float:
    dcg = 0.0
    for rank, clause in enumerate(retrieved_clauses[:k], 1):
        if clause in target_clauses:
            dcg += 1.0 / math.log2(rank + 1)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(target_clauses), k) + 1))
    return dcg / idcg if idcg > 0 else 0.0

def evaluate_retrieval_batch(eval_dataset: List[Dict[str, Any]], retriever_fn, k_list: List[int] = [1, 3, 5]) -> Dict[str, float]:
    metrics_sum = {f"Hit@{k}": 0.0 for k in k_list}
    metrics_sum.update({f"MRR@{k}": 0.0 for k in k_list})
    
    total = len(eval_dataset)
    for q_item in eval_dataset:
        query = q_item["query"]
        targets = set(q_item["expected_clauses"])
        retrieved = retriever_fn(query)
        retrieved_clauses = [r.get("metadata", {}).get("Clause") for r in retrieved]
        
        for k in k_list:
            metrics_sum[f"Hit@{k}"] += calculate_hit_at_k(retrieved_clauses, targets, k)
            metrics_sum[f"MRR@{k}"] += calculate_mrr_at_k(retrieved_clauses, targets, k)

    return {metric: round(val / total, 4) for metric, val in metrics_sum.items()}