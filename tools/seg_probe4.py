# 시험용 — 원문에서 지역·부문 매출 표 후보 (3개월·누적 칸 포함)를 모두 보여 준다
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import probe_audit as P
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "030000").split(","):
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20260901", "pblntf_ty": "A", "page_count": 10})
    r0 = sorted([r for r in res["list"] if "분기보고서" in r["report_nm"]], key=lambda r: r["rcept_dt"], reverse=True)[0]
    doc = P.fetch_doc(r0["rcept_no"])
    print("==", code, cm[code]["name"], r0["report_nm"], len(doc or ""))
    for i, m in enumerate(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc or "", re.S | re.I)):
        rows = P.rows_of(m.group(1))
        names = " ".join(r[0] for r in rows if r)
        if len(rows) >= 4 and re.search(r"국내|해외|중국|유럽|미주|북미|아시아|부문|사업", names) and re.search(r"매출|수익|3개월|누적", " ".join(" ".join(r) for r in rows[:4]) + re.sub(r"<[^>]+>", " ", (doc or "")[max(0, m.start() - 300):m.start()])):
            print("  -- 표", i, "|", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (doc or "")[max(0, m.start() - 300):m.start()]))[-150:])
            for r in rows[:16]:
                print("     ", r[:7])
