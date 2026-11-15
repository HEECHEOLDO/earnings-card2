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
for code, name in codes[24:56]:
    try:
        x = FA.flow(code)
    except Exception as e:
        import traceback; print(code, name, "ERR", traceback.format_exc()[-500:]); continue
    if not x:
        print(code, name, "없음", FA.WHY); continue
    e = lambda v: None if v is None else round(v / 1e8)
    print(code, name, x["period"], "매출", e(x["rev"]), "원가", e(x["cogs"]), "판관", e(x["sga"]), "영업", e(x["op"]),
          "| 부문", [(n, e(v)) for n, v in x["segs"]], "| 비용", [(n, e(v)) for n, v in x["items"]], flush=True)
    if not x["items"]:                      # 판관비 표 후보를 보여 준다
        doc = FA.P.fetch_doc(x["src"])
        for rows, u, ctx in FA._tables(doc):
            names = [FA.P.acct(r[0]) for r in rows if r]
            if sum(1 for n in names if FA.re.search(r"급여|지급수수료|감가상각|광고|임차료|복리후생", n)) >= 3:
                vals = [(FA.P.acct(r[0]), FA.P.first_amount(r)) for r in rows if r][:14]
                print("    후보 단위", u, [(a, None if b is None else round(b * u / 1e8)) for a, b in vals])
