# 시험용 — SEC companyfacts 에 최근 분기 값이 없는 회사: 무엇이 들어 있는지 출력
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
T = os.environ.get("CODES", "SO,AEE").split(",")
tick = U.get_json("https://www.sec.gov/files/company_tickers.json") or {}
cik = {str(r["ticker"]).upper(): r["cik_str"] for r in tick.values()}
for t in T:
    d = json.load(open("data/flow/%s.json" % t))
    f = U.get_json(U.SEC_FACTS % str(cik[t]).zfill(10)); time.sleep(0.2)
    g = ((f or {}).get("facts") or {}).get("us-gaap") or {}
    print("==", t, cik[t], d.get("start"), d.get("end"), "card rev", d.get("rev"), "ni", d.get("ni"), "src", d.get("src"))
    for tg in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]:
        us = ((g.get(tg) or {}).get("units") or {}).get("USD", [])
        us = sorted(us, key=lambda u: (u.get("end", ""), u.get("filed", "")))[-4:]
        for u in us:
            print("  ", tg, u.get("start"), u.get("end"), round(u["val"] / 1e6, 1), u.get("form"), u.get("fp"), u.get("filed"), u.get("accn"))
    # 같은 접수번호로 들어온 값이 있는지
    acc = d.get("src")
    n = sum(1 for tg, v in g.items() for u in (v.get("units") or {}).get("USD", []) if u.get("accn") == acc)
    print("   facts with card accn:", n)
    time.sleep(0.2)
