#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'시총 순위' 탭을 사이트에 붙인다.

  python3 setup_rank.py

1) add_tab.py   메뉴에 '시총 순위' 칸 추가 (시가총액 다음) → 그다음 python3 add_tab.py 로 모든 화면 메뉴를 다시 쓴다
2) check_health.py  데이터 상태 점검에 '시총 순위' 추가
3) .gitignore   키 파일(datago_key.txt · krx_key.txt)이 올라가지 않게
두 번 돌려도 괜찮다.
"""
import os
import re
import sys

ITEM = '''    ("rank",    "./rank.html",
     '<path d="M4 20v-8h5v8M9 20V5h6v15M15 20v-11h5v11"/>',
     "시총 순위", "순위"),
'''


def edit(fn, fix):
    if not os.path.exists(fn):
        print("!! %s 가 없습니다" % fn)
        return False
    s = open(fn, encoding="utf-8").read()
    new = fix(s)
    if new is None:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 이 파일을 보내 주세요." % fn)
        return False
    if new == s:
        print("  그대로  %s" % fn)
    else:
        open(fn, "w", encoding="utf-8").write(new)
        print("  고침    %s" % fn)
    return True


def fix_tab(s):
    if '"rank.html"' in s:
        return s
    a = '    "mcap.html":    "mcap",\n'
    m = re.search(r'    \("screen",', s)
    if s.count(a) != 1 or not m:
        return None
    s = s.replace(a, a + '    "rank.html":    "rank",\n')
    m = re.search(r'    \("screen",', s)
    return s[:m.start()] + ITEM + s[m.start():]


def fix_health(s):
    if '"rank"' in s:
        return s
    line = '    ("rank",     "시총 순위", "rank.html", ["data/rank.json"], 4, 7),\n'
    m = re.search(r'^\s*\("mcap".*\n', s, re.M) or re.search(r'^SOURCES = \[\n', s, re.M)
    if not m:
        return None
    return s[:m.end()] + line + s[m.end():]


def fix_ignore(s):
    for k in ("datago_key.txt", "krx_key.txt"):
        if not re.search(r"^/?%s$" % re.escape(k), s, re.M):
            s = s.rstrip("\n") + "\n/" + k + "\n"
    return s


if __name__ == "__main__":
    if not os.path.exists(".gitignore"):
        open(".gitignore", "a").close()
    ok = all([edit("add_tab.py", fix_tab), edit("check_health.py", fix_health), edit(".gitignore", fix_ignore)])
    sys.exit(0 if ok else 1)
