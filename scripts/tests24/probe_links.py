# -*- coding: utf-8 -*-
"""Печать ссылок tests24.ru с страницы выбора области электробезопасности."""
from __future__ import annotations

import re
import urllib.request

URL = "https://tests24.ru/?iter=1&s_group=7"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if "iter=2&group=" in href or "iter=3&test=" in href:
            print(href)


if __name__ == "__main__":
    main()
