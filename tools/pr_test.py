# 시험용 — 실적 발표(8-K 2.02) 손익표 읽기 확인 (저장하지 않고 출력만)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
for t in (os.environ.get("CODES") or "NVDA").split(","):
    cik = (json.load(open("data/us/%s.json" % t)) or {}).get("cik")
    cik = cik[0] if isinstance(cik, list) else cik
    old = json.load(open("data/flow/%s.json" % t)) if os.path.exists("data/flow/%s.json" % t) else None
    sub = U.get_json(U.SEC_SUBMIT % str(int(cik)).zfill(10))
    rc = sub["filings"]["recent"]
    F.FX.WHY = ""
    old2 = dict(old or {}); old2["src"] = "x"
    v = F.us_pr(int(cik), rc, old2)
    print("==", t, "카드", (old or {}).get("period"), "→", None if not v or v == "SAME" else {k: (round(x / 1e6, 1) if isinstance(x, float) else x) for k, x in v.items() if k not in ("items",)}, v and v != "SAME" and [[n, round(x / 1e6, 1)] for n, x in v["items"]], F.FX.WHY)
