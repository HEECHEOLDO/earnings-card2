# 시험용 — 실적 발표 자료 안의 매출 구분 표 후보를 그대로 보여 준다
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
for t in (os.environ.get("CODES") or "NVDA").split(","):
    cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
    rc = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))["filings"]["recent"]
    i = next(i for i, f in enumerate(rc["form"]) if f == "8-K" and "2.02" in rc["items"][i])
    acc = rc["accessionNumber"][i]; base = U.SEC_ARCH % (cik, acc.replace("-", ""))
    names = [x["name"] for x in U.get_json(base + "index.json")["directory"]["item"]]
    print("==", t, acc, names)
    for n in [n for n in names if n.lower().endswith((".htm", ".html")) and n != rc["primaryDocument"][i] and "index" not in n.lower()][:5]:
        h = (U.get(base + n) or b"").decode("utf-8", "replace")
        for k, tm in enumerate(re.finditer(r"<table\b.*?</table>", h, re.S | re.I)):
            rows = [r for r in (F._cells(tr) for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(0), re.S | re.I)) if r]
            txt = " ".join(" ".join(r) for r in rows)
            if len(rows) >= 3 and re.search(r"segment|platform|by (product|region|geograph|category|market)|data center|merchandise|comparable|systems|services", txt + F._txt(h[max(0, tm.start() - 600):tm.start()]), re.I) and re.search(r"\d,\d{3}|\d{3}", txt):
                print("  --", n, "표", k, "|", F._txt(h[max(0, tm.start() - 300):tm.start()])[-160:])
                for r in rows[:14]:
                    print("      ", r[:6])
