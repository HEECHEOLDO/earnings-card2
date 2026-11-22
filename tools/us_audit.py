# 시험용 — 돈의 흐름 해외 카드 전부를 SEC companyfacts(두 번째 출처)와 줄마다 대조하고, 10-Q 가 나왔는데 카드가 아직 실적발표(8-K) 기준인지 본다
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
import collect_flow as F
idx = json.load(open("data/flow/index.json"))["items"]
codes = [k for k, v in idx.items() if v.get("m") == "US"]
if os.environ.get("CODES") not in (None, "", "ALL"):
    codes = os.environ["CODES"].split(",")
TAGS = {"rev": F.SEC_REV, "op": ["OperatingIncomeLoss"], "ni": F.SEC_NI, "gross": ["GrossProfit"],
        "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"], "tax": ["IncomeTaxExpenseBenefit"],
        "rnd": ["ResearchAndDevelopmentExpense"], "sga": ["SellingGeneralAndAdministrativeExpense"]}
cnt = {}
for code in codes:
    try:
        d = json.load(open("data/flow/%s.json" % code))
        cik = (json.load(open("data/us/%s.json" % code)).get("cik"))
        cik = int(cik[0] if isinstance(cik, list) else cik)
        f = None
        for _ in range(3):
            f = U.get_json(U.SEC_FACTS % str(cik).zfill(10)); time.sleep(0.3)
            if f:
                break
        if not f:
            print("%-6s 받기실패" % code, flush=True); continue
        g = ((f or {}).get("facts") or {}).get("us-gaap") or {}
        sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10)) or {}; time.sleep(0.15)
        rc = (sub.get("filings") or {}).get("recent") or {}
        q = next(((rc["filingDate"][i], rc["accessionNumber"][i], rc["reportDate"][i]) for i, x in enumerate(rc.get("form", [])) if x in ("10-Q", "10-K")), None)
        res = []
        for k, tags in TAGS.items():
            if d.get(k) is None:
                continue
            vs = [u["val"] / 1e6 for t in tags for u in ((g.get(t) or {}).get("units") or {}).get("USD", []) if u.get("start") == d.get("start") and u.get("end") == d.get("end")]
            if not vs:
                res.append(k + ":없음"); continue
            ok = any(abs(d[k] - x) <= max(abs(x) * 0.005, 0.6) for x in vs)
            res.append(k + (":OK" if ok else ":틀림(%s vs %s)" % (d[k], sorted(set(round(x, 1) for x in vs)))))
        bad = any("틀림" in r for r in res); none = all("없음" in r for r in res)
        st = "틀림" if bad else ("SEC없음" if none else "OK")
        stale = bool(q and d.get("pr") and q[2] >= d.get("end", "9"))
        cnt[st] = cnt.get(st, 0) + 1
        if stale: cnt["10Q나옴_카드는8K"] = cnt.get("10Q나옴_카드는8K", 0) + 1
        if not d.get("segs"): cnt["매출구조없음"] = cnt.get("매출구조없음", 0) + 1
        print("%-6s %-5s pr=%s segs=%d end=%s 10Q=%s %s %s" % (code, st, d.get("pr") or "-", len(d.get("segs") or []), d.get("end"), q, "STALE" if stale else "", " ".join(res)), flush=True)
    except Exception as e:                       # noqa: BLE001
        print("%-6s ERR %s" % (code, e), flush=True)
print("합계", cnt)
