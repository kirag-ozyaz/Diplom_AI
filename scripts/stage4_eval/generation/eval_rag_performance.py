"""
Этап 4: эксплуатационные метрики RAG-контура (задержка, TTFT, пропускная способность).

Контрольные вопросы — реестр eval_questions.json (300 записей).
Результат: scripts/stage4_eval/results/generation/stage4_performance_metrics.json
"""

import os
import sys
import time
import json
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _bootstrap import setup_paths  # noqa: E402

ROOT = setup_paths()
from report_paths import (  # noqa: E402
    STAGE4_PERF_METRICS,
    STAGE4_QUESTIONS,
    ensure_stage4_result_dirs,
    rel_from_root,
)

CONFIG_PATH = ROOT / "config" / "rag_runtime.json"
QUESTIONS_PATH = STAGE4_QUESTIONS


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "ollama": {"host": "http://localhost:11434", "model": "qwen2.5:3b"},
        "vector_db": {"host": "localhost", "port": 19530}
    }


def load_questions():
    if QUESTIONS_PATH.exists():
        from eval_questions_io import load_eval_questions  # noqa: E402

        return load_eval_questions(QUESTIONS_PATH)
    return [{"id": 1, "query": "Какие требования предъявляются к заземлению электроустановок?"}]


def measure_single_stream_request(ollama_host: str, model: str, prompt: str):
    url = f"{ollama_host}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True
    }
    
    start_time = time.perf_counter()
    first_token_time = None
    tokens_count = 0
    full_text = ""

    try:
        response = requests.post(url, json=payload, stream=True, timeout=60)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            if not first_token_time:
                first_token_time = time.perf_counter()
            
            if "response" in chunk:
                full_text += chunk["response"]
                tokens_count += 1
            
            if chunk.get("done", False):
                if "eval_count" in chunk and chunk["eval_count"] > 0:
                    tokens_count = chunk["eval_count"]

        end_time = time.perf_counter()
        
        ttft = (first_token_time - start_time) if first_token_time else (end_time - start_time)
        total_latency = end_time - start_time
        gen_duration = (end_time - first_token_time) if (first_token_time and end_time > first_token_time) else total_latency
        tps = (tokens_count / gen_duration) if gen_duration > 0 else 0.0

        return {
            "success": True,
            "ttft_sec": round(ttft, 4),
            "total_latency_sec": round(total_latency, 4),
            "tps": round(tps, 2),
            "tokens_generated": tokens_count,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "ttft_sec": 0.0,
            "total_latency_sec": round(time.perf_counter() - start_time, 4),
            "tps": 0.0,
            "tokens_generated": 0,
            "error": str(e)
        }


def run_load_test(questions, cfg, concurrency=3):
    total = len(questions)
    ollama_cfg = cfg.get("ollama", {})
    host = ollama_cfg.get("host", "http://localhost:11434")
    model = ollama_cfg.get("model", "qwen2.5:3b")

    print(
        f"[*] Этап: нагрузочный тест — {total} вопросов, "
        f"параллельность {concurrency}, Ollama {model} @ {host}",
        flush=True,
    )

    def task(q_item):
        q = q_item.get("query") or q_item.get("question", "")
        prompt = f"Контекст: Правила устройства электроустановок.\nВопрос: {q}\nОтвет:"
        return measure_single_stream_request(host, model, prompt)

    results = []
    ok_count = 0
    err_count = 0
    done = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_q = {executor.submit(task, q): q for q in questions}
        for future in as_completed(future_to_q):
            q_item = future_to_q[future]
            r = future.result()
            results.append(r)
            done += 1
            q_id = q_item.get("id", done)
            if r["success"]:
                ok_count += 1
                print(
                    f"  [{done}/{total}] id={q_id}: OK — "
                    f"TTFT {r['ttft_sec']} с, latency {r['total_latency_sec']} с, "
                    f"TPS {r['tps']}",
                    flush=True,
                )
            else:
                err_count += 1
                err = (r.get("error") or "неизвестная ошибка")[:120]
                print(f"  [{done}/{total}] id={q_id}: ОШИБКА — {err}", flush=True)

    print(
        f"[+] Нагрузочный тест: успешно {ok_count} из {total}, ошибок {err_count}",
        flush=True,
    )

    successful_requests = [r for r in results if r["success"]]

    latencies = [r["total_latency_sec"] for r in successful_requests]
    ttfts = [r["ttft_sec"] for r in successful_requests]
    tps_list = [r["tps"] for r in successful_requests]
    total_tokens = sum(r["tokens_generated"] for r in successful_requests)

    availability = (len(successful_requests) / len(questions)) * 100 if questions else 0.0
    total_duration = sum(latencies) / concurrency if latencies else 1.0
    rps = len(questions) / total_duration if total_duration > 0 else 0.0

    latencies_sorted = sorted(latencies) if latencies else [0]
    def percentile(data, p):
        idx = int(len(data) * p)
        return data[min(idx, len(data) - 1)]

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_requests": len(questions),
        "successful_requests": len(successful_requests),
        "failed_requests": len(questions) - len(successful_requests),
        "concurrency": concurrency,
        "rps": round(rps, 2),
        "availability_pct": round(availability, 2),
        "metrics": {
            "ttft_avg_sec": round(statistics.mean(ttfts), 4) if ttfts else 0.0,
            "tps_avg": round(statistics.mean(tps_list), 2) if tps_list else 0.0,
            "latency_avg_sec": round(statistics.mean(latencies), 4) if latencies else 0.0,
            "latency_p50_sec": round(percentile(latencies_sorted, 0.50), 4),
            "latency_p95_sec": round(percentile(latencies_sorted, 0.95), 4),
            "latency_p99_sec": round(percentile(latencies_sorted, 0.99), 4),
            "total_tokens_generated": total_tokens,
            "cost_usd_est": 0.0
        }
    }

    return summary


def main():
    print("=" * 60, flush=True)
    print("[1/2] Оценка производительности и нагрузочное тестирование", flush=True)
    print("=" * 60, flush=True)

    cfg = load_config()
    questions = load_questions()

    summary = run_load_test(questions, cfg, concurrency=3)
    summary["source"] = "eval_rag_performance.py"
    summary["questions_path"] = rel_from_root(QUESTIONS_PATH)
    summary["pipeline_note"] = (
        "Нагрузочный тест Ollama (упрощённый промпт); не latency полного RAG (Milvus+LLM)."
    )

    ensure_stage4_result_dirs()
    out_file = STAGE4_PERF_METRICS

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print(" РЕЗУЛЬТАТЫ ЭКСПЛУАТАЦИОННЫХ И НАГРУЗОЧНЫХ МЕТРИК RAG")
    print("="*60)
    print(f" • Процент успешности (Availability) : {summary['availability_pct']}%")
    print(f" • Производительность (RPS)           : {summary['rps']} req/sec")
    print(f" • Время до 1-го токена (TTFT Avg)   : {summary['metrics']['ttft_avg_sec']} сек")
    print(f" • Скорость генерации (TPS Avg)       : {summary['metrics']['tps_avg']} ток/сек")
    print(f" • Средняя задержка (Latency Avg)     : {summary['metrics']['latency_avg_sec']} сек")
    print(f" • Задержка P95 / P99                 : {summary['metrics']['latency_p95_sec']}s / {summary['metrics']['latency_p99_sec']}s")
    print(f" • Всего сгенерировано токенов        : {summary['metrics']['total_tokens_generated']}")
    print(f"\n[+] Метрики сохранены в: {out_file.resolve()}")


if __name__ == "__main__":
    main()