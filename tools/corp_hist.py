# 시험용 — 회사의 최근 공시 목록과 회사 개황(형태·이름 변경) 보기. CODES=8자리 회사코드(쉼표)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
for cc in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    info = C.api_get("company.json", {"corp_code": cc}) or {}
    print("=====", cc, info.get("corp_name"), "|", info.get("corp_cls"), "| 법인형태?", info.get("jurir_no"), "| 설립", info.get("est_dt"), "| 결산월", info.get("acc_mt"))
    res = C.api_get("list.json", {"corp_code": cc, "bgn_de": "20200101", "end_de": "20261123", "page_count": "100"}) or {}
    for r in (res.get("list") or [])[:12]:
        print("   ", r.get("rcept_dt"), r.get("report_nm"))
    print("   총", res.get("total_count"))
