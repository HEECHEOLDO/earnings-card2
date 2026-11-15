#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""포트폴리오 탭 — 상장사가 아닌 운용사(뱅가드·피델리티 등) 로고 → logo/fund/{키}.png
찾는 순서는 find_logos.py 와 같다: 영어 위키백과 문서의 로고 → 위키미디어 공용 → 홈페이지 아이콘.
상장된 운용사(블랙록 BLK 등)는 logo/us 의 로고를 그대로 쓴다."""
import os
import sys

from find_logos import from_page, from_commons, from_site, get
from make_old_logos import round_logo

DIR = os.path.join("logo", "fund")
LIST = {
    "vanguard":   ("The Vanguard Group", ["Vanguard Group logo", "Vanguard logo"], "vanguard.com"),
    "fidelity":   ("Fidelity Investments", ["Fidelity Investments logo"], "fidelity.com"),
    "geode":      ("Geode Capital Management", ["Geode Capital Management logo"], "geodecapital.com"),
    "wellington": ("Wellington Management Company", ["Wellington Management logo"], "wellington.com"),
}


def main():
    os.makedirs(DIR, exist_ok=True)
    only = set(sys.argv[1:])
    for key, (en, words, domain) in LIST.items():
        dst = os.path.join(DIR, key + ".png")
        if (only and key not in only) or (not only and os.path.exists(dst)):
            continue
        got = None
        for step in (lambda: from_page("en", en), lambda: from_commons(words), lambda: from_site(domain)):
            try:
                r = step()
                if not r:
                    continue
                raw = get(r[0])
                if len(raw) < 300:
                    continue
                open(dst, "wb").write(round_logo(raw))
                got = r[1]
                break
            except Exception as e:            # noqa: BLE001
                print("   ", key, repr(e)[:80])
        print("  %-11s %s" % (key, got or "못 찾음"))


if __name__ == "__main__":
    main()
