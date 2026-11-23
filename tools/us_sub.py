# 시험용 — SEC 최근 공시 목록 (10-Q/10-K/8-K). CODES=티커(쉼표)
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
m = U.load_ticker_map() if hasattr(U, "load_ticker_map") else None
for t in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    j = json.load(open("data/us/%s.json" % t))
    cik = j.get("cik") or (m or {}).get(t); cik = cik[-1] if isinstance(cik, list) else cik
    sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10)) if cik else None
    rc = (sub or {}).get("filings", {}).get("recent", {})
    rows = [(rc["filingDate"][i], rc["form"][i], rc["reportDate"][i]) for i in range(len(rc.get("form", []))) if rc["form"][i] in ("10-Q", "10-K", "8-K", "NT 10-Q")][:6]
    print("##", t, cik, rows)
