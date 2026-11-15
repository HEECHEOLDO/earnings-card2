#!/usr/bin/env python3
"""1회용 점검: 비상장(감사보고서) 매출 구분·판관비 세부 읽기"""
import json, glob
import collect as C
import flow_audit as FA
C.API_KEY = C.get_key()
codes = []
for f in sorted(glob.glob("data/unlisted/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if d.get("source") == "audit":
        codes.append((d["code"], d["name"]))
for code, name in codes[:24]:
    try:
        x = FA.flow(code)
    except Exception as e:
        print(code, name, "ERR", e); continue
    if not x:
        print(code, name, "없음", FA.WHY); continue
    e = lambda v: None if v is None else round(v / 1e8)
    print(code, name, x["period"], "매출", e(x["rev"]), "원가", e(x["cogs"]), "판관", e(x["sga"]), "영업", e(x["op"]),
          "| 부문", [(n, e(v)) for n, v in x["segs"]], "| 비용", [(n, e(v)) for n, v in x["items"]], flush=True)
