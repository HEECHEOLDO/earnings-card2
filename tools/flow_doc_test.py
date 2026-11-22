"""돈의 흐름 — 보고서 원문 대체(doc_fallback) 시험: 몇 회사를 읽어 매출 구분·판관비 세부를 출력만 한다 (저장 안 함)"""
import os, sys
sys.argv = ['x']
sys.path.insert(0, os.getcwd())
import collect as C, collect_flow as CF
C.API_KEY = C.get_key()
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "306620,004650,199730,191410,005930").split(","):
    info = cmap.get(code)
    if not info:
        print(code, "코드 없음"); continue
    v = CF.kr_xbrl(info["corp_code"])
    if not v or v == "SAME":
        print(code, "없음", CF.FX.WHY); continue
    e = lambda x: round(x / 1e8, 1)
    s_items = sum(x for _, x in v.get("items") or [])
    print(code, "rev", e(v["rev"]), "sga", e(v.get("sga") or 0), "op", e(v["op"]),
          "| segs", [(n, e(x)) for n, x in v.get("segs") or []][:7], v.get("seg_note"),
          "| items", [(n, e(x)) for n, x in v.get("items") or []], "합", e(s_items), v.get("items_from"), v.get("mix_err"), v.get("doc_err"), "| seg_from", v.get("seg_from"), v.get("seg_err"), "cum", e(v.get("cum_rev") or 0), flush=True)
