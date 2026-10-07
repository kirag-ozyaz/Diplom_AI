# -*- coding: utf-8 -*-
"""
Выгрузка формулировок вопросов из билета Tests24 (электробезопасность).

Пример:
  python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
  python scripts/tests24/fetch_bilet.py --url "https://tests24.ru/?iter=4&bil=1&test=996"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import TESTS24_DATA  # noqa: E402

BASE = "https://tests24.ru/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_questions(html: str) -> list[str]:
    """Номерованные вопросы вида «1) …» на странице билета."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\r", "", text)
    lines = [ln.strip() for ln in text.split("\n")]
    blob = "\n".join(ln for ln in lines if ln)

    found: list[tuple[int, str]] = []
    for m in re.finditer(
        r"(?<!\d)(\d{1,2})\)\s+(.+?)(?=\n\d{1,2}\)\s|\Z)",
        blob,
        flags=re.S,
    ):
        num = int(m.group(1))
        q = re.sub(r"\s+", " ", m.group(2)).strip()
        if len(q) > 500:
            q = q[:500].rsplit(" ", 1)[0] + "…"
        if 20 < len(q) < 800:
            found.append((num, q))

    if not found:
        for m in re.finditer(r"(\d{1,2})\)\s+([^?]+\?)", blob):
            found.append((int(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip()))

    by_num: dict[int, str] = {}
    for num, q in found:
        by_num[num] = q
    return [by_num[k] for k in sorted(by_num)]


def build_url(test: int, bilet: int) -> str:
    q = urllib.parse.urlencode({"iter": 4, "bil": bilet, "test": test})
    return f"{BASE}?{q}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Выгрузка вопросов билета Tests24")
    ap.add_argument("--url", help="Полный URL билета (iter=4&bil=&test=)")
    ap.add_argument("--test", type=int, help="ID теста (параметр test=)")
    ap.add_argument("--bilet", type=int, default=1, help="Номер билета (bil=)")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        help="JSON (по умолчанию data/tests24/bilet_<test>_bil_<n>.json)",
    )
    args = ap.parse_args()

    if args.url:
        url = args.url
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        test = int(qs.get("test", ["0"])[0])
        bilet = int(qs.get("bil", ["1"])[0])
    elif args.test:
        test = args.test
        bilet = args.bilet
        url = build_url(test, bilet)
    else:
        ap.error("Укажите --url или --test")

    html = fetch_html(url)
    questions = parse_questions(html)
    if not questions:
        raise SystemExit(f"Не удалось извлечь вопросы из {url}")

    TESTS24_DATA.mkdir(parents=True, exist_ok=True)
    out = args.output or (TESTS24_DATA / f"bilet_{test}_bil_{bilet}.json")
    payload = [
        {
            "num": i + 1,
            "query": q,
            "source": "tests24.ru",
            "test_id": test,
            "bilet": bilet,
            "source_url": url,
        }
        for i, q in enumerate(questions)
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Сохранено {len(payload)} вопросов -> {out}")


if __name__ == "__main__":
    main()
