# 시험용 — 못 읽은 감사보고서 원문에서 손익 표 모양 보기. CODES=접수번호(쉼표)
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
import probe_audit as P
C.API_KEY = C.get_key()
for rc in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    blob = C.api_get("document.xml", {"rcept_no": rc}, raw=True)
    print("=====", rc, "크기", len(blob or b""), "머리", (blob or b"")[:60])
    doc = P.fetch_doc(rc)
    if not doc:
        continue
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I))
    print("  표", len(tabs), "글자", len(doc), "TABLE 태그 수(소문자 포함)", len(re.findall(r"<table", doc, re.I)))
    shown = 0
    for m in tabs:
        rows = P.rows_of(m.group(1))
        txt = " ".join("".join(map(str, r[:1])) for r in rows[:40])
        if re.search(r"매출|영업수익|수익\(매출", txt) and re.search(r"영업|당기순", txt):
            for r in rows[:14]:
                print("   ", r[:4])
            shown += 1
            if shown >= 1:
                break
    if not shown:
        i = doc.find("매출")
        print("  손익 표 못 찾음 · '매출' 주변:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", doc[max(0, i - 300):i + 600]))[:700])
