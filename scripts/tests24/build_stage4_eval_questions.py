# -*- coding: utf-8 -*-
"""
Сборка stage4_eval_questions.json из выгрузок Tests24 (только вопросы по ПУЭ).

  python scripts/tests24/build_stage4_eval_questions.py
  python scripts/tests24/build_stage4_eval_questions.py --merge-base  # 38 базовых + tests24
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import TESTS24_DATA  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data" / "extracted"
OUT_DEFAULT = ROOT / "Этапы" / "Reports" / "etap4" / "data" / "stage4_eval_questions.json"
BASE_38 = ROOT / "Этапы" / "Reports" / "etap4" / "data" / "stage4_eval_questions_base38.json"

PUE_MARKER = re.compile(
    r"согласно\s+Правилам\s+устройства\s+электроустановок",
    re.I,
)

# Подстрока в очищенном вопросе -> пункт ПУЭ (порядок: более специфичные выше).
CLAUSE_RULES: list[tuple[str, str]] = [
    (
        "приемником электрической энергии (электроприемником)",
        "1.2.7",
    ),
    ("потребителем электрической энергии", "1.2.8"),
    (
        "заземляющий проводник, присоединяющий заземлитель рабочего (функционального) заземления",
        "1.7.117",
    ),
    (
        "минимальное сечение медных защитных проводников, не входящих в состав кабеля",
        "1.7.127",
    ),
    (
        "минимальное сечение медных проводников основной системы уравнивания потенциалов",
        "1.7.137",
    ),
    (
        "минимальное сечение стальных проводников основной системы уравнивания потенциалов",
        "1.7.137",
    ),
    (
        "минимальное сечение алюминиевых проводников основной системы уравнивания потенциалов",
        "1.7.137",
    ),
    ('термину "глухозаземленная нейтраль"', "1.7.5"),
    ('термину "заземление"', "1.7.28"),
    ('термину "защитное заземление"', "1.7.29"),
    ('термину "заземлитель"', "1.7.15"),
    ('термину "естественный заземлитель"', "1.7.17"),
    ('термину "искусственный заземлитель"', "1.7.16"),
    ('термину "защита от прямого прикосновения"', "1.7.13"),
    ('термину "защита при косвенном прикосновении"', "1.7.14"),
    (
        "классифицируются помещения в отношении опасности поражения людей",
        "1.1.13",
    ),
    ("помещения называются сухими", "1.1.6"),
    ("помещения относятся к влажным", "1.1.7"),
    ("помещения называются сырыми", "1.1.8"),
    (
        "защиты при косвенном прикосновении в цепях, питающих переносные электроприемники",
        "1.7.62",
    ),
    ("освещения безопасности", "6.1.21"),
    (
        "напряжение должно применяться для питания переносных светильников в помещениях с повышенной опасностью",
        "6.1.17",
    ),
    (
        "обозначены нулевые рабочие (нейтральные) проводники",
        "1.1.29",
    ),
    (
        "обозначаются проводники защитного заземления, а также нулевые защитные проводники",
        "1.1.29",
    ),
    (
        "сопротивление должно иметь в любое время года заземляющее устройство",
        "1.7.101",
    ),
    (
        "дополнительные мероприятия при сооружении искусственных заземлителей",
        "1.7.107",
    ),
    (
        "напряжение холостого хода источника сварочного тока установок плазменной обработки",
        "7.6.57",
    ),
    (
        "блокировкой, обеспечивающей при открывании дверей",
        "7.6.27",
    ),
    (
        "отдельному помещению для электросварочных установок",
        "7.6.37",
    ),
    (
        "переносной или передвижной электросварочной установки непосредственно к стационарной",
        "7.6.24",
    ),
    (
        "расстоянии от сварочного поста должен располагаться однопостовой источник",
        "7.6.19",
    ),
    (
        "максимально допустимой длины должен быть гибкий кабель, соединяющий источник сварочного тока",
        "7.6.25",
    ),
    (
        "располагать сварочные посты во взрыво- и пожароопасных зонах",
        "7.6.35",
    ),
]


def clean_tests24_query(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw.strip())
    if "?" in raw:
        stem = raw.split("?", 1)[0].strip() + "?"
        return stem
    # без «?» — обрезка по типичному началу варианта ответа
    m = re.search(
        r"^(.{40,}?)\s+(?:Аппарат,|Помещения,|Заземление|Напряжение|Не далее|Не больше|Обозначаются|Выше \d)",
        raw,
    )
    if m:
        return m.group(1).strip()
    return raw[:280].rsplit(" ", 1)[0] if len(raw) > 280 else raw


def clause_for_question(q: str) -> str | None:
    low = q.lower()
    for needle, clause in CLAUSE_RULES:
        if needle.lower() in low:
            return clause
    return None


def load_bilet_questions() -> list[dict]:
    items: list[dict] = []
    for path in sorted(TESTS24_DATA.glob("bilet_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data:
            raw = row.get("query") or ""
            if not PUE_MARKER.search(raw):
                continue
            q = clean_tests24_query(raw)
            clause = clause_for_question(q)
            if not clause:
                continue
            items.append(
                {
                    "query": q,
                    "expected_clause": clause,
                    "source": "tests24.ru",
                    "test_id": row.get("test_id"),
                    "bilet": row.get("bilet"),
                    "source_url": row.get("source_url"),
                }
            )
    return items


def dedupe_by_query(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        key = re.sub(r"\W+", " ", it["query"].lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def verify_clause_in_extracted(clause: str) -> bool:
    needle = f"{clause}."
    for md in EXTRACTED.glob("*.md"):
        if needle in md.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUT_DEFAULT,
        help="Куда записать stage4_eval_questions.json",
    )
    ap.add_argument(
        "--merge-base",
        action="store_true",
        help="Сохранить первые 38 вопросов из base38 и добавить tests24 без дубликатов",
    )
    args = ap.parse_args()

    from_tests24 = dedupe_by_query(load_bilet_questions())
    for it in from_tests24:
        if not verify_clause_in_extracted(it["expected_clause"]):
            print(
                f"WARN: пункт {it['expected_clause']} не найден в extracted: {it['query'][:80]}…",
                file=sys.stderr,
            )

    payload: list[dict] = []
    if args.merge_base and BASE_38.is_file():
        base = json.loads(BASE_38.read_text(encoding="utf-8"))
        payload.extend(
            {"id": x["id"], "query": x["query"], "expected_clause": x["expected_clause"]}
            for x in base
        )
        base_keys = {
            re.sub(r"\W+", " ", x["query"].lower()).strip() for x in payload
        }
        next_id = max(x["id"] for x in payload) + 1
        for it in from_tests24:
            key = re.sub(r"\W+", " ", it["query"].lower()).strip()
            if key in base_keys:
                continue
            payload.append(
                {
                    "id": next_id,
                    "query": it["query"],
                    "expected_clause": it["expected_clause"],
                }
            )
            base_keys.add(key)
            next_id += 1
    else:
        for i, it in enumerate(from_tests24, start=1):
            payload.append(
                {
                    "id": i,
                    "query": it["query"],
                    "expected_clause": it["expected_clause"],
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Записано {len(payload)} вопросов -> {args.output}")
    print(f"Из tests24 (после дедупа): {len(from_tests24)}")


if __name__ == "__main__":
    main()
