# 시험용 — 실적 발표(8-K 2.02) 손익표 읽기 확인 (저장하지 않고 출력만)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
for t in (os.environ.get("CODES") or "NVDA").split(","):
    if not os.path.exists("data/us/%s.json" % t):
        continue
    cik = (json.load(open("data/us/%s.json" % t)) or {}).get("cik")
    cik = cik[0] if isinstance(cik, list) else cik
    old = json.load(open("data/flow/%s.json" % t)) if os.path.exists("data/flow/%s.json" % t) else None
    sub = U.get_json(U.SEC_SUBMIT % str(int(cik)).zfill(10))
    rc = sub["filings"]["recent"]
    F.FX.WHY = ""
    old2 = dict(old or {}); old2["src"] = "x"
    v = F.us_pr(int(cik), rc, old2)
    print("==", t, "카드", (old or {}).get("period"), "→", None if not v or v == "SAME" else {k: (round(x / 1e6, 1) if isinstance(x, float) else x) for k, x in v.items() if k not in ("items",)}, v and v != "SAME" and [[n, round(x / 1e6, 1)] for n, x in v["items"]], F.FX.WHY)
# 못 읽은 회사: 손익표 후보의 줄 이름과 첫 숫자
import re
for t in (os.environ.get("CODES") or "").split(","):
    if not os.path.exists("data/us/%s.json" % t):
        continue
    cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
    rc = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))["filings"]["recent"]
    i = next((i for i, f in enumerate(rc["form"]) if f == "8-K" and "2.02" in rc["items"][i]), None)
    if i is None:
        continue
    acc = rc["accessionNumber"][i]; base = U.SEC_ARCH % (cik, acc.replace("-", ""))
    names = [x["name"] for x in U.get_json(base + "index.json")["directory"]["item"]]
    for n in [n for n in names if n.lower().endswith(".htm") and n != rc["primaryDocument"][i]][:2]:
        h = (U.get(base + n) or b"").decode("utf-8", "replace")
        for tm in re.finditer(r"<table\b.*?</table>", h, re.S | re.I):
            before = F._txt(h[max(0, tm.start() - 2500):tm.start()]).lower()
            if re.search(r"statements? of (income|operations|earnings)", before[-1200:]):
                rows = [F._cells(tr) for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(0), re.S | re.I)]
                print("--", t, n, "| 앞:", before[-200:].replace("\n", " "))
                for r in rows[:40]:
                    print("   ", r[:4])
                break
