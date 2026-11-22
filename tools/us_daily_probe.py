# 시험용 — 미국 종목 10년 일별 종가를 어디서 받을 수 있는지 (야후·나스닥), 주별 파일과 맞는지
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_chart_us as U
from datetime import date, timedelta
today = date.today()
for s in (os.environ.get("CODES") or "AAPL,NVDA,TSLA").split(","):
    w = {a: b for a, b in json.load(open("data/chart/us/%s.json" % s))["w"]}
    for name, f in (("yahoo", lambda: U.yahoo_bars(s, "10y", "1d")), ("nasdaq", lambda: U.nasdaq_bars(s, (today - timedelta(days=3700)).strftime("%Y-%m-%d")))):
        try:
            rows = f()
        except Exception as e:                  # noqa: BLE001
            rows = None; print(s, name, "오류", e)
        if not rows:
            print(s, name, "없음"); continue
        m = [abs(b / w[a] - 1) for a, b in rows if a in w]
        ok = sum(1 for x in m if x < 0.01)
        print(s, name, len(rows), rows[0], rows[-1], "주별과 맞음 %d/%d" % (ok, len(m)), flush=True)
