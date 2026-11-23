# 시험용 — 감사보고서 원문 표 읽은 값 (당기·전기) 보기. CODES=회사코드(8자리, 쉼표)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
import collect_audit as A
import probe_audit as P
C.API_KEY = C.get_key(); A.BUDGET = 400
for code in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    by = A.list_reports([code], 2019)
    print("=====", code)
    for per in sorted(by):
        r = A.choose(by[per], False)
        doc = P.fetch_doc(r["rcept_no"])
        cur, prev, cfs = A.parse(doc) if doc else (None, None, None)
        f = lambda d: {k: (None if v is None else round(v / 1e8, 1)) for k, v in (d or {}).items()}
        print(per, r["report_nm"], r["rcept_no"], "당기", f(cur), "전기", f(prev))
print("호출", C._call_count)
