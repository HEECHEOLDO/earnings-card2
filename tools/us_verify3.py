# 시험용 — companyfacts 에 아직 안 들어온 회사: 공시 원본 XBRL(인스턴스)을 따로 간단히 읽어 카드 값과 비교
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
T = os.environ.get("CODES", "").split(",")
tick = U.get_json("https://www.sec.gov/files/company_tickers.json") or {}
cik = {str(r["ticker"]).upper(): r["cik_str"] for r in tick.values()}
REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RegulatedAndUnregulatedOperatingRevenue", "OperatingLeasesIncomeStatementLeaseRevenue", "RevenuesNetOfInterestExpense"]
NI = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
OP = ["OperatingIncomeLoss"]
ok = 0
for t in T:
    d = json.load(open("data/flow/%s.json" % t))
    c, acc = cik[t], d["src"]
    base = U.SEC_ARCH % (int(c), acc.replace("-", ""))
    idx = U.get_json(base + "index.json"); time.sleep(0.2)
    names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
    inst = next((n for n in names if n.endswith("_htm.xml")), None)
    x = (U.get(base + inst) or b"").decode("utf-8", "replace") if inst else ""; time.sleep(0.2)
    # 차원(segment) 없는 같은 기간 맥락만
    ctx = set()
    for m in re.finditer(r'<(?:xbrli:)?context id="([^"]+)">(.*?)</(?:xbrli:)?context>', x, re.S):
        body = m.group(2)
        if "segment" in body:
            continue
        if re.search(r"startDate>%s<" % d["start"], body) and re.search(r"endDate>%s<" % d["end"], body):
            ctx.add(m.group(1))
    def get(tags):
        out = {}
        for tg in tags:
            for m in re.finditer(r'<us-gaap:%s[^>]*contextRef="([^"]+)"[^>]*>([-\d.]+)<' % tg, x):
                if m.group(1) in ctx:
                    out.setdefault(tg, float(m.group(2)) / 1e6)
        return out
    r, o, n = get(REV), get(OP), get(NI)
    def hit(card, vs, tol):
        return card is not None and any(abs(card - v) <= max(abs(v) * tol, 0.6) for v in vs.values())
    res = [("rev", hit(d.get("rev"), r, 0.005)), ("ni", hit(d.get("ni"), n, 0.01))] + ([("op", hit(d.get("op"), o, 0.01))] if o else [])
    good = all(h for _, h in res)
    ok += good
    print("OK " if good else "BAD", t, d.get("name"), "| 카드 rev %s op %s ni %s | 원본 rev %s op %s ni %s" % (d.get("rev"), d.get("op"), d.get("ni"), {k: round(v, 1) for k, v in r.items()}, {k: round(v, 1) for k, v in o.items()}, {k: round(v, 1) for k, v in n.items()}))
print("=== %d / %d 일치" % (ok, len(T)))
