# 시험용 — 감사보고서 손익계산서 줄 보기
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import probe_audit as P
for rc in (os.environ.get("CODES") or "").split(","):
    doc = P.fetch_doc(rc)
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc or "", re.S | re.I))
    print("==", rc, len(tabs))
    for i, m in enumerate(tabs):
        rows = P.rows_of(m.group(1))
        t = " ".join(" ".join(r) for r in rows)
        if re.search(r"당기순|법인세비용차감전", t) and re.search(r"매출|영업수익", t):
            for r in rows[:45]:
                print("   ", i, r[:5])
            break
