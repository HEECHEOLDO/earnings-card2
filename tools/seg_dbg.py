# 시험: 돈의 흐름 doc_fallback 안에서 매출 구분 표가 어떻게 읽히는지 (FA._tables)
import os, sys, re
sys.argv = ['x']; sys.path.insert(0, os.getcwd())
import collect as C, collect_flow as CF, flow_audit as FA, probe_audit as P
C.API_KEY = C.get_key(); cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "054040").split(","):
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20260101", "pblntf_ty": "A", "page_count": 10})
    r0 = sorted(res["list"], key=lambda r: r["rcept_dt"], reverse=True)[0]
    doc = P.fetch_doc(r0["rcept_no"]); tabs = FA._tables(doc) if doc else []
    print("==", code, r0["report_nm"], "tabs", len(tabs))
    for rows, u, ctx in tabs:
        if rows and rows[0] and re.match(r"사업부문|매출유형|구분", re.sub(r"\s+", "", rows[0][0])):
            print("  u", u, "|", str(ctx)[-60:]); [print("    ", r[:7]) for r in rows[:8]]
            print("  ->", CF.seg_table([(rows, u, ctx)], 260369e6), CF.seg_table([(rows, u, ctx)], 160844e6))
