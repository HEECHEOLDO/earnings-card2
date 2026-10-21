#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시총 순위 탭에 나오는 회사 중 로고 파일(logo/kr/코드.png)이 없는 곳을 뽑는다.

  python3 list_missing_logos.py           코스피·코스닥·국내 전체
  python3 list_missing_logos.py --no-kosdaq  코스닥 카드는 빼고 (코스피·국내 전체만)
TOP 15 안에 한 번이라도 든 회사만 본다. 결과는 화면과 missing_logos.txt
"""
import json
import os
import sys

j = json.load(open("data/rank.json", encoding="utf-8"))
seen = {}
for k, c in j["cols"].items():
    for mk in (("kospi", "all") if "--no-kosdaq" in sys.argv else ("kospi", "kosdaq", "all")):
        for code, name, cap in c.get(mk, [])[:15]:
            s = seen.setdefault(code, {"names": [], "years": set()})
            if name not in s["names"]:
                s["names"].append(name)
            s["years"].add("현재" if k == "now" else k)
miss = [(c, s) for c, s in seen.items() if not os.path.exists(os.path.join("logo", "kr", c + ".png"))]
miss.sort(key=lambda x: min(x[1]["years"]))
lines = ["로고 없음 %d곳 (TOP 15에 든 회사 %d곳 중)" % (len(miss), len(seen))]
for c, s in miss:
    ys = sorted(s["years"])
    lines.append("%s | %s | %s~%s" % (c, " / ".join(s["names"]), ys[0], ys[-1]))
txt = "\n".join(lines)
print(txt)
open("missing_logos.txt", "w", encoding="utf-8").write(txt)
print("\n저장: missing_logos.txt")
