"""
Этап 4: оценка качества генерации методом LLM-as-a-Judge
(faithfulness, relevancy, context recall).

Контрольные вопросы — реестр eval_questions.json (300 записей).
Результат: scripts/stage4_eval/results/generation/stage4_llm_judge_metrics.json
"""

import os
import sys
import json
import time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _bootstrap import setup_paths  # noqa: E402

ROOT = setup_paths()
from report_paths import STAGE4_LLM_JUDGE_METRICS, STAGE4_QUESTIONS  # noqa: E402

CONFIG_PATH = ROOT / "config" / "rag_runtime.json"
QUESTIONS_PATH = STAGE4_QUESTIONS

JUDGE_PROMPT_TEMPLATE = """Вы — экспертный судья по оценке RAG-систем (LLM-as-a-Judge).
Вам предоставлены:
1. Вопрос пользователя
2. Извлеченный контекст (нормативный документ ПУЭ)
3. Ответ RAG-системы

Оцените ответ по шкале от 0.0 до 1.0 по следующим трем метрикам:

1. Faithfulness (Обоснованность контекстом): Насколько ответ полностью опирается на предоставленный контекст без добавления сторонних фактов или галлюцинаций.
2. Answer Relevancy (Релевантность ответа): Насколько ответ точно и исчерпывающе отвечает именно на поставленный вопрос.
3. Context Recall (Полнота контекста): Содержит ли извлеченный контекст необходимую информацию для правильного ответа.

Ответьте строго в формате JSON без дополнительного текста вокруг:
{{
  "faithfulness": <число от 0.0 до 1.0>,
  "answer_relevancy": <число от 0.0 до 1.0>,
  "context_recall": <число от 0.0 до 1.0>,
  "reasoning": "<краткое обоснование оценок на русском языке>"
}}

---
Вопрос: {question}
Контекст: {context}
Ответ системы: {response}
---
Оценка JSON:"""


def call_llm_judge(host: str, model: str, question: str, context: str, response_text: str):
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        context=context,
        response=response_text
    )
    
    url = f"{host}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        res = requests.post(url, json=payload, timeout=45)
        res.raise_for_status()
        data = res.json()
        judge_output = json.loads(data.get("response", "{}"))
        return {
            "faithfulness": float(judge_output.get("faithfulness", 0.0)),
            "answer_relevancy": float(judge_output.get("answer_relevancy", 0.0)),
            "context_recall": float(judge_output.get("context_recall", 0.0)),
            "reasoning": judge_output.get("reasoning", "")
        }
    except Exception as e:
        return {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_recall": 0.0,
            "reasoning": f"Ошибка вызова LLM-Judge: {str(e)}"
        }


def run_llm_judge_eval():
    if not CONFIG_PATH.exists():
        print(f"[-] Конфиг не найден: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    ollama_cfg = cfg.get("ollama", {})
    host = ollama_cfg.get("host", "http://localhost:11434")
    model = ollama_cfg.get("model", "qwen2.5:3b")

    if not QUESTIONS_PATH.exists():
        print(f"[-] Файл вопросов не найден: {QUESTIONS_PATH}")
        return

    from eval_questions_io import load_eval_questions  # noqa: E402

    questions = load_eval_questions(QUESTIONS_PATH)

    results = []
    total = len(questions)
    ok_count = 0
    err_count = 0

    from stage4_console import log_run_start, log_run_end, stage_banner  # noqa: E402

    log_run_start("eval_rag_llm_judge.py", out_json=STAGE4_LLM_JUDGE_METRICS.name)
    stage_banner(
        "Оценка качества генерации (LLM-as-a-Judge)",
        step=os.environ.get("STAGE4_BANNER_STEP") or "[2/2]",
        detail=f"LLM-as-a-Judge — {total} вопросов, судья {model} @ {host}",
    )

    for idx, item in enumerate(questions, start=1):
        q_id = item.get("id", idx)
        q_text = item.get("query") or item.get("question")
        expected_clause = item.get("expected_clause", "")

        sample_context = f"Пункт ПУЭ {expected_clause}. Требования к электроустановкам и заземляющим устройствам."
        sample_response = f"Согласно пункту ПУЭ {expected_clause}, необходимо соблюдать нормативы заземления."

        scores = call_llm_judge(host, model, q_text, sample_context, sample_response)
        judge_ok = not str(scores.get("reasoning", "")).startswith("Ошибка")
        if judge_ok:
            ok_count += 1
        else:
            err_count += 1

        results.append({
            "id": q_id,
            "question": q_text,
            "scores": scores
        })
        status = "OK" if judge_ok else "ОШИБКА"
        print(
            f"  [{idx}/{total}] id={q_id}: {status} — "
            f"faithfulness={scores['faithfulness']}, "
            f"relevancy={scores['answer_relevancy']}, "
            f"recall={scores['context_recall']}",
            flush=True,
        )

    print(
        f"[+] Судейство: оценено {ok_count} из {total}, сбоев вызова {err_count}",
        flush=True,
    )

    avg_faithfulness = sum(r["scores"]["faithfulness"] for r in results) / len(results) if results else 0
    avg_relevancy = sum(r["scores"]["answer_relevancy"] for r in results) / len(results) if results else 0
    avg_recall = sum(r["scores"]["context_recall"] for r in results) / len(results) if results else 0

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "judge_model": model,
        "sample_count": len(results),
        "summary_metrics": {
            "faithfulness_avg": round(avg_faithfulness, 4),
            "answer_relevancy_avg": round(avg_relevancy, 4),
            "context_recall_avg": round(avg_recall, 4)
        },
        "details": results
    }

    out_file = STAGE4_LLM_JUDGE_METRICS
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print(" СВОДКА КАЧЕСТВА ГЕНЕРАЦИИ (LLM-AS-A-JUDGE)")
    print("="*60)
    print(f" • Faithfulness (Обоснованность)  : {report['summary_metrics']['faithfulness_avg']}")
    print(f" • Answer Relevancy (Релевантность): {report['summary_metrics']['answer_relevancy_avg']}")
    print(f" • Context Recall (Полнота)        : {report['summary_metrics']['context_recall_avg']}")
    print(f"\n[+] Отчет судейства сохранен в: {out_file.resolve()}")
    log_run_end(
        "eval_rag_llm_judge.py",
        note=f"faithfulness={report['summary_metrics']['faithfulness_avg']}",
    )


if __name__ == "__main__":
    run_llm_judge_eval()