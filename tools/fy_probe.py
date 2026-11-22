# 시험용 — 결산월이 다른 회사의 DART 사업연도·보고서 번호가 실제 어느 기간인지 확인
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
cm = C.load_corp_map() if hasattr(C, "load_corp_map") else None
for code in (os.environ.get("CODES") or "032800").split(","):
    corp = None
    try:
        corp = json.load(open("data/flow/%s.json" % code)).get("corp") 
    except Exception:
        pass
    if not corp and cm:
        corp = (cm.get(code) or {}).get("corp_code")
    co = C.api_get("company.json", {"corp_code": corp}) or {}
    print("==", code, co.get("corp_name"), "결산월", co.get("acc_mt"), corp)
    for y in (2025, 2026, 2027):
        for rc in ("11013", "11012", "11014", "11011"):
            res = C.api_get("fnlttSinglAcntAll.json", {"corp_code": corp, "bsns_year": str(y), "reprt_code": rc, "fs_div": "OFS"}) or {}
            L = res.get("list") or []
            if not L:
                res = C.api_get("fnlttSinglAcntAll.json", {"corp_code": corp, "bsns_year": str(y), "reprt_code": rc, "fs_div": "CFS"}) or {}
                L = res.get("list") or []
            r = next((x for x in L if x.get("sj_div") in ("IS", "CIS") and ("매출" in (x.get("account_nm") or "") or "수익" in (x.get("account_nm") or ""))), None)
            print("  ", y, rc, (L[0].get("rcept_no") if L else None), r and (r.get("account_nm"), r.get("thstrm_nm"), r.get("thstrm_amount"), r.get("thstrm_add_amount")))
