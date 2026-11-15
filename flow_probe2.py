#!/usr/bin/env python3
"""1회용 점검: 사업보고서(연간) XBRL 에 판관비 세부가 어떻게 들어 있는지 (data/flow/_probe2/)"""
import json, os, re
import collect as C
import xbrl_dims as XD
OUT = "data/flow/_probe2"
os.makedirs(OUT, exist_ok=True)
C.API_KEY = C.get_key()
cm = C.load_corp_map()
for code in ["005930", "000660", "005380", "035420", "000270"]:
    o = {}
    try:
        corp = cm[code]["corp_code"]
        res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20250101", "pblntf_ty": "A", "page_count": 40})
        rows = [r for r in (res or {}).get("list", []) if "사업보고서" in r.get("report_nm", "")]
        rows.sort(key=lambda r: r["rcept_dt"], reverse=True)
        r0 = rows[0]
        blob = C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": "11011"}, raw=True)
        files = XD.unzip(blob)
        inst = [n for n in files if n.endswith(".xbrl")][0]
        lab = [n for n in files if "lab-ko" in n]
        ctx, facts = XD.parse(files[inst])
        L = XD.labels(files[lab[0]]) if lab else {}
        end = max(ctx[c]["end"] for n, c, v in facts)
        o["report"] = r0["report_nm"]
        o["rows"] = [[n, L.get(n, ""), ctx[c]["start"], [(L.get(a, a), L.get(m, m)) for a, m in ctx[c]["dims"] if "ConsolidatedAndSeparate" not in a], v]
                     for n, c, v in facts if ctx[c]["end"] == end and ctx[c]["start"][5:] == "01-01" and abs(v) >= 1e10
                     and any(m.endswith("ConsolidatedMember") for a, m in ctx[c]["dims"])
                     and re.search(r"급여|광고|수수료|연구|감가|상각|운반|판매|복리|물류|임차|용역|보증|원재료|종업원|Expense|Salar|Wage|Advert|Commission|Research|Depreci", n + L.get(n, ""))]
    except Exception as e:
        import traceback; o["err"] = traceback.format_exc()[-600:]
    json.dump(o, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(code, len(o.get("rows", [])))
