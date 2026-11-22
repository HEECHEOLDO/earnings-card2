# 시험용 — 카드 기간의 SEC 사실표 값들 (매출·영업이익·순이익 후보 태그 전부)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
for t in (os.environ.get("CODES") or "REG").split(","):
    d = json.load(open("data/flow/%s.json" % t))
    cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = cik[0] if isinstance(cik, list) else cik
    f = U.get_json(U.SEC_FACTS % str(int(cik)).zfill(10))
    g = f["facts"]["us-gaap"]
    print("==", t, d["start"], d["end"], "카드", d["rev"], d["op"], d["ni"], d.get("report"))
    for tag, x in g.items():
        for u in x.get("units", {}).get("USD", []):
            if u.get("start") == d["start"] and u.get("end") == d["end"]:
                v = u["val"] / 1e6
                if any(abs(v - c) <= max(abs(c) * 0.01, 0.6) for c in (d["rev"], d["op"], d["ni"])) or "Revenue" in tag or "NetIncome" in tag or "ProfitLoss" in tag or "OperatingIncome" in tag:
                    print("   ", tag, round(v, 1))
