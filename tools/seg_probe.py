"""시험용 — 국내 회사 최근 보고서 XBRL 의 매출 차원(부문·지역) 값을 기간별로 출력 (저장 안 함)"""
import os, sys, re
sys.argv = ['x']
sys.path.insert(0, os.getcwd())
import collect as C, collect_flow as CF
import xbrl_dims as XD
C.API_KEY = C.get_key()
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "257720").split(","):
    info = cmap[code]
    res = C.api_get("list.json", {"corp_code": info["corp_code"], "bgn_de": "20260101", "pblntf_ty": "A", "page_count": 10})
    r0 = [r for r in res["list"] if "보고서" in r["report_nm"]][0]
    print("==", code, info["name"], r0["report_nm"], r0["rcept_no"])
    files = XD.unzip(C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": "11014"}, raw=True))
    inst = [n for n in files if n.endswith(".xbrl")][0]
    lab = [n for n in files if "lab-ko" in n]
    L = XD.labels(files[lab[0]]) if lab else {}
    ctx, facts = XD.parse(files[inst])
    for n, c, v in facts:
        if n in ("ifrs-full:Revenue", "ifrs-full:RevenueFromContractsWithCustomers") and ctx[c]["dims"]:
            p = ctx[c]
            print("  ", p["start"], p["end"], [(a.split(":")[-1], m.split(":")[-1], L.get(m, "")) for a, m in p["dims"]], round(v / 1e8, 1))
