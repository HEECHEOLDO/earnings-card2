# 시험용 — 달력 기준(frame) 카드가 실제로 어느 기간 값인지, 더 최근 분기 3개월 값이 있는지 출력
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
idx = json.load(open("data/flow/index.json"))["items"]
tick = U.get_json("https://www.sec.gov/files/company_tickers.json") or {}
cik = {str(r["ticker"]).upper().replace("-", "."): r["cik_str"] for r in tick.values()}
for t in sorted(k for k, v in idx.items() if v.get("m") == "US"):
    d = json.load(open("data/flow/%s.json" % t))
    if d.get("start") or not d.get("y"):
        continue
    fr = d.get("frame") or "CY%dQ%d" % (d["y"], d["q"])
    f = U.get_json(U.SEC_FACTS % str(cik[t]).zfill(10)); time.sleep(0.15)
    g = ((f or {}).get("facts") or {}).get("us-gaap") or {}
    hit, q3 = None, []
    for tg in ["NetIncomeLoss", "ProfitLoss"]:
        for u in ((g.get(tg) or {}).get("units") or {}).get("USD", []):
            if u.get("frame") == fr and not hit:
                hit = (tg, u.get("start"), u.get("end"), round(u["val"] / 1e6, 1), u.get("form"), u.get("filed"))
            if u.get("start") and u.get("end") and u.get("form") in ("10-Q", "10-K"):
                dd = (time.mktime(time.strptime(u["end"], "%Y-%m-%d")) - time.mktime(time.strptime(u["start"], "%Y-%m-%d"))) / 86400
                if 80 <= dd <= 120:
                    q3.append((u["end"], u["start"], round(u["val"] / 1e6, 1), u.get("form")))
        if hit:
            break
    q3 = sorted(set(q3))[-2:]
    print("FR", t, d.get("period"), "card ni", d.get("ni"), "| frame=", hit, "| latest 3M:", q3)
