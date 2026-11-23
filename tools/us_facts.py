# 시험용 — companyfacts 최근 값 보기. CODES=티커(쉼표)
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
for t in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    j = json.load(open("data/us/%s.json" % t)); cik = j.get("cik"); cik = cik[-1] if isinstance(cik, list) else cik
    f = U.get_json(U.SEC_FACTS % str(cik).zfill(10)) or {}
    us = f.get("facts", {}).get("us-gaap", {})
    print("##", t, cik, "태그", len(us))
    for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "NetIncomeLoss", "OperatingIncomeLoss"):
        rows = [r for r in us.get(tag, {}).get("units", {}).get("USD", []) if r.get("end", "") >= "2026-06-01"]
        print("  ", tag, [(r.get("start"), r["end"], r.get("form"), r.get("fp"), r.get("filed"), r["val"]) for r in rows][:6])
