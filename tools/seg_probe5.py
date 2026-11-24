# 시험용 — 분기보고서에서 '매출' 이 들어간 표를 모두 보여 준다 (매출 구조 세분화 확인)
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import probe_audit as P
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "252990").split(","):
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20250101", "pblntf_ty": "A", "page_count": 20})
    reps = sorted([r for r in res["list"] if re.search("분기보고서|사업보고서|반기보고서", r["report_nm"])], key=lambda r: r["rcept_dt"], reverse=True)
    for r0 in reps[:2]:
        doc = P.fetch_doc(r0["rcept_no"])
        print("==", code, cm[code]["name"], r0["report_nm"], r0["rcept_no"], len(doc or ""))
        for i, m in enumerate(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc or "", re.S | re.I)):
            rows = P.rows_of(m.group(1))
            ctx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (doc or "")[max(0, m.start() - 400):m.start()]))[-160:]
            txt = " ".join(" ".join(r) for r in rows)
            if len(rows) >= 3 and re.search(r"매출|판매", ctx + " ".join(" ".join(r) for r in rows[:3])) and not re.search(r"재무상태|현금흐름|자본변동", ctx):
                print("  -- 표", i, "|", ctx)
                for r in rows[:14]:
                    print("     ", [c[:24] for c in r[:8]])
