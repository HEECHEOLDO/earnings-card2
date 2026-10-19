#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""업종·테마마다 어떤 이모지가 붙는지 전부 보여준다 (mcap.html 의 MCAP_EMOJI 표 기준).

  python3 list_mcap_emoji.py        → 화면과 mcap_emoji.txt
📈(기본값)이 붙은 테마는 맞는 낱말이 없던 것. 고치고 싶은 줄을 알려주면 표를 고친다.
"""
import json
import re

s = open("mcap.html", encoding="utf-8").read()
m = re.search(r"var MCAP_EMOJI = \{ upjong: (\{.*?\}),\s*theme: (\[.*?\]\]), other: '([^']*)' \};", s, re.S)
if not m:
    raise SystemExit("!! mcap.html 에 MCAP_EMOJI 표가 없습니다. patch_mcap_emoji.py 를 먼저 돌리세요.")
up, th, other = json.loads(m.group(1)), json.loads(m.group(2)), m.group(3)
j = json.load(open("data/mcap.json", encoding="utf-8"))


def pick(kind, g):
    key = re.sub(r"\s", "", g["name"])
    if kind == "industry" and key in up:
        return up[key], "표"
    for pat, e in th:
        if re.search(pat, g["name"]) or re.search(pat, g.get("short") or ""):
            return e, pat.split("|")[0] + "…"
    return other, "기본값"


out = []
for kind, label in (("industry", "업종"), ("theme", "테마")):
    gs = j.get("groups", {}).get(kind, [])
    out.append("\n[%s] %d개" % (label, len(gs)))
    for g in gs:
        e, why = pick(kind, g)
        out.append("  %s  %-28s (%s)" % (e, g.get("short") or g["name"], why))
    n = sum(1 for g in gs if pick(kind, g)[1] == "기본값")
    out.append("  → 기본값(%s) %d개" % (other, n))
text = "\n".join(out)
print(text)
open("mcap_emoji.txt", "w", encoding="utf-8").write(text)
print("\n저장: mcap_emoji.txt")
