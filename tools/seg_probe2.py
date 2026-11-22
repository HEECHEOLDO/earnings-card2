# 시험용 — 큰 회사 3분기 매출 구분: 수집기가 어떻게 채우는지 + 못 채우면 원문의 매출 표 후보를 보여 준다
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import collect_flow as F
import probe_audit as P
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "030000").split(","):
    corp = cm[code]["corp_code"]
    v = F.kr_xbrl(corp, None)
    if not isinstance(v, dict):
        print("==", code, "카드 없음", F.FX.WHY); continue
    d = F.scaled(v, 1e8)
    print("==", code, cm[code]["name"], d.get("report"), "매출", d.get("rev"), "누적", d.get("cum_rev"), d.get("cum_lab"), "| 구분", d.get("segs"), d.get("seg_from"), d.get("seg_note"), d.get("seg_err"), d.get("doc_err"))
    continue
    doc = P.fetch_doc(v["src"])
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc or "", re.S | re.I))
    shown = 0
    for i, m in enumerate(tabs):
        before = re.sub(r"<[^>]+>", " ", (doc or "")[max(0, m.start() - 600):m.start()])
        rows = P.rows_of(m.group(1))
        t = " ".join(" ".join(r) for r in rows[:3])
        if re.search(r"부문|지역|매출|수익", before[-250:] + t) and re.search(r"부문|지역|사업|제품|국내|해외|합\s*계", " ".join(r[0] for r in rows if r)) and len(rows) >= 3:
            print("   -- 표", i, "|", re.sub(r"\s+", " ", before[-160:]))
            for r in rows[:14]:
                print("      ", r[:7])
            shown += 1
            if shown >= 4:
                break
