# 시험용 — 손익계산서 계정 이름 보기 (저장 안 함). CODES=종목코드(쉼표)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
cm = C.load_corp_map()
for code in os.environ.get("CODES", "").split(","):
    cc = cm[code.strip()]["corp_code"]
    for y, r in ((2025, "11011"), (2026, "11014")):
        res = C.api_get("fnlttSinglAcntAll.json", {"corp_code": cc, "bsns_year": str(y), "reprt_code": r, "fs_div": "CFS"})
        rows = [x for x in (res or {}).get("list", []) if x.get("sj_div") in ("IS", "CIS")]
        print("=====", code, y, r, len(rows))
        for x in rows[:14]:
            print("  ", x.get("sj_div"), x.get("account_id"), "|", x.get("account_nm"), "|", x.get("thstrm_amount"))
