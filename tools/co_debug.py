# 시험용 — 상장사 한 곳 실적 수집 과정을 자세히 본다 (저장 안 함). CODES=종목코드(쉼표)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key(); C.DEBUG = True
cm = C.load_corp_map()
from datetime import datetime
for code in os.environ.get("CODES", "").split(","):
    code = code.strip()
    if not code:
        continue
    print("=====", code, cm.get(code))
    data, reason = C.collect_company(code, cm, datetime.now().year, None)
    print("결과:", reason, (data or {}).get("quarterly", [])[-3:] if data else None)
print("호출", C._call_count)
