# 시험용 — 돈의 흐름 해외 카드 금액을 SEC 원본(companyfacts)과 따로 맞춰 본다 (저장하지 않고 결과만 출력)
#   같은 기간(시작·끝 날짜)의 매출·영업이익·순이익을 SEC 에서 다시 찾아 카드 값과 비교
#   더 최근 분기 보고서가 이미 나왔는데 카드가 옛 분기인지도 본다
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U

REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
       "SalesRevenueNet", "RevenuesNetOfInterestExpense", "SalesRevenueGoodsNet", "RegulatedAndUnregulatedOperatingRevenue",
       "ElectricUtilityRevenue", "RevenuesExcludingInterestAndDividends", "OperatingLeasesIncomeStatementLeaseRevenue"]
OP = ["OperatingIncomeLoss"]
NI = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]


def vals(g, tags, start, end, frame):
    out = []
    for t in tags:
        for u in ((g.get(t) or {}).get("units") or {}).get("USD", []):
            if (start and u.get("start") == start and u.get("end") == end) or (frame and u.get("frame") == frame):
                out.append((t, u["val"] / 1e6))
    return out


def near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= max(abs(b) * tol, 0.6)


def main():
    idx = json.load(open("data/flow/index.json"))["items"]
    us = [k for k, v in idx.items() if v.get("m") == "US"]
    tick = U.get_json("https://www.sec.gov/files/company_tickers.json") or {}
    cik = {str(r["ticker"]).upper().replace("-", "."): r["cik_str"] for r in tick.values()}
    bad, ok, stale = [], 0, []
    for t in sorted(us):
        d = json.load(open("data/flow/%s.json" % t))
        c = cik.get(t) or cik.get(t.replace(".", "-"))
        if not c:
            bad.append((t, "CIK 없음")); continue
        f = U.get_json(U.SEC_FACTS % str(c).zfill(10)); time.sleep(0.15)
        g = ((f or {}).get("facts") or {}).get("us-gaap") or {}
        st, en, fr = d.get("start"), d.get("end"), d.get("frame")
        if not st and not fr:
            p = d.get("period", "")
            if "달력" in p:
                fr = "CY20%sQ%s" % (p[1:3], p.split("년 ")[1][0])
        prob = []
        for k, tags, tol in (("rev", REV, 0.005), ("op", OP, 0.01), ("ni", NI, 0.01)):
            vs = vals(g, tags, st, en, fr)
            if not vs:
                if k != "op":
                    prob.append("%s SEC 값 없음(카드 %s)" % (k, d.get(k)))
                continue
            if not any(near(d.get(k), v, tol) for _, v in vs):
                prob.append("%s 카드 %s vs SEC %s" % (k, d.get(k), sorted(set(round(v, 1) for _, v in vs))[:4]))
        # 더 최근 분기가 나왔는지 (3개월 순이익 값의 최신 끝 날짜)
        latest = ""
        for tg in NI[:2]:
            for u in ((g.get(tg) or {}).get("units") or {}).get("USD", []):
                if u.get("form") in ("10-Q", "10-K") and u.get("start") and u.get("end"):
                    try:
                        days = (time.mktime(time.strptime(u["end"], "%Y-%m-%d")) - time.mktime(time.strptime(u["start"], "%Y-%m-%d"))) / 86400
                    except Exception:
                        continue
                    if 80 <= days <= 120 and u["end"] > latest:
                        latest = u["end"]
        cend = en or ""
        if latest and cend and latest > cend:
            stale.append((t, d.get("period"), cend, latest))
        if prob:
            bad.append((t, d.get("name"), d.get("period"), "; ".join(prob)))
        else:
            ok += 1
    print("=== 해외 카드 %d곳 · SEC 와 일치 %d · 문제 %d · 더 최근 분기 있음 %d" % (len(us), ok, len(bad), len(stale)))
    for b in bad:
        print("BAD", *b)
    for s in stale:
        print("STALE", *s)


main()
