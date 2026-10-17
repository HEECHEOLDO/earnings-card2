#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모든 페이지의 메뉴를 같은 7칸으로 맞춘다 ('비상장 실적' 추가).

  python3 add_tab.py            바꾸기
  python3 add_tab.py --dry      뭐가 바뀌는지만 보기

메뉴가 6칸이 되면서 폭이 빠듯해져, 좁은 화면용 짧은 이름(nav-short)을
모든 칸에 넣는다. 지금은 '연간 수익률'과 '종목 스크리닝'에만 있다.

메뉴 아래 '데이터 상태' 한 줄(health.js)도 모든 화면에 넣는다.

몇 번을 돌려도 결과가 같다 — 매번 <nav> 를 통째로 다시 쓴다.
"""

import os
import re
import sys

PAGES = {
    "index.html":   "index",
    "us.html":      "us",
    "returns.html": "returns",
    "screen.html":  "screen",
    "guru.html":    "guru",
    "buy.html":     "buy",
    "unlisted.html": "unlisted",
    "status.html":  "status",     # 데이터 상태 — 메뉴 칸은 없고 메뉴 아래 한 줄로 들어간다
}

# 모든 화면 메뉴 아래에 '데이터 정상 · 10.18 점검' 한 줄을 붙이는 스크립트
HEALTH_TAG = '<script src="./health.js" defer></script>'

ITEMS = [
    ("index",   "./index.html",
     '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M7 16v-4M12 16V8M17 16v-6"/>',
     "국내 실적", "국내"),
    ("us",      "./us.html",
     '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 010 18M12 3a15 15 0 000 18"/>',
     "해외 실적", "해외"),
    ("unlisted", "./unlisted.html",
     '<path d="M4 21V6l8-3 8 3v15"/><path d="M9 21v-5h6v5"/><path d="M9 9h.01M15 9h.01M9 13h.01M15 13h.01"/>',
     "비상장 실적", "비상장"),
    ("returns", "./returns.html",
     '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
     "연간 수익률", "수익률"),
    ("buy",     "./buy.html",
     '<path d="M3 12a9 9 0 103-6.7"/><path d="M3 4v5h5"/><path d="M12 8v4.5l3 1.8"/>',
     "그때 샀다면", "그때"),
    ("screen",  "./screen.html",
     '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
     "종목 스크리닝", "스크리닝"),
    ("guru",    "./guru.html",
     '<circle cx="12" cy="12" r="9"/><path d="M12 3v9l6.4 6.4"/>',
     "포트폴리오", "포폴"),
]


def nav_html(here):
    out = ['<nav class="nav" aria-label="메뉴">']
    for key, href, svg, full, short in ITEMS:
        on = " on" if key == here else ""
        out.append('    <a href="%s" class="nav-i%s">' % (href, on))
        out.append('      <svg viewBox="0 0 24 24" aria-hidden="true">%s</svg>' % svg)
        out.append('      <span class="nav-full">%s</span><span class="nav-short">%s</span>'
                   % (full, short))
        out.append('    </a>')
    out.append('  </nav>')
    return "\n  ".join(out)


NAV_RE = re.compile(r'<nav class="nav"[^>]*>.*?</nav>', re.S)


def main():
    dry = "--dry" in sys.argv
    hit = miss = same = 0
    for path, here in PAGES.items():
        if not os.path.exists(path):
            print("  건너뜀  %-14s 파일이 없습니다" % path)
            miss += 1
            continue
        s = open(path, encoding="utf-8").read()
        if not NAV_RE.search(s):
            print("  !! %-14s <nav class=\"nav\"> 를 찾지 못했습니다 — 손대지 않습니다" % path)
            miss += 1
            continue
        new = NAV_RE.sub(lambda m: nav_html(here), s, count=1)
        if HEALTH_TAG not in new and "</body>" in new:
            new = new.replace("</body>", HEALTH_TAG + "\n</body>", 1)
        if new == s:
            print("  그대로  %-14s 이미 최신입니다" % path)
            same += 1
            continue
        if dry:
            print("  바뀜    %-14s (%+d자)" % (path, len(new) - len(s)))
        else:
            open(path, "w", encoding="utf-8").write(new)
            print("  고침    %-14s (%+d자)" % (path, len(new) - len(s)))
        hit += 1

    print("\n바꿈 %d · 그대로 %d · 못함 %d" % (hit, same, miss))
    if dry:
        print("--dry 라 파일은 건드리지 않았습니다.")


if __name__ == "__main__":
    main()
