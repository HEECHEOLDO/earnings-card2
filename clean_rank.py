#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/rank.json 에서 우선주·신주·뮤추얼펀드를 빼고 옛 이름 띄어쓰기를 고친다 (호출 0회).

  python3 clean_rank.py
collect_rank.py 와 같은 기준을 이미 받아 둔 칸에 다시 적용한다. 두 번 돌려도 괜찮다.
"""
import json

import collect_rank as C

j = json.load(open(C.OUT, encoding="utf-8"))
gone = {}
for k, col in j["cols"].items():
    for mk in ("kospi", "kosdaq", "all"):
        keep = []
        for code, name, cap in col.get(mk, []):
            if C.ordinary(code) and not C.BAD.search(name):
                keep.append([code, C.tidy(name), cap])
            else:
                gone[name] = gone.get(name, 0) + 1
        col[mk] = keep
with open(C.OUT, "w", encoding="utf-8") as f:
    json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
print("뺀 종목 %d개: %s" % (len(gone), ", ".join(sorted(gone)) or "없음"))
