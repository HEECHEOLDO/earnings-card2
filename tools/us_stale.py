# 시험용 — 해외 카드보다 더 최근 10-Q/10-K 가 이미 나왔는지 (SEC 제출 목록 기준) 출력
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_us as U
idx = json.load(open("data/flow/index.json"))["items"]
tick = U.get_json("https://www.sec.gov/files/company_tickers.json") or {}
cik = {str(r["ticker"]).upper().replace("-", "."): r["cik_str"] for r in tick.values()}
st, ok = [], 0
for t in sorted(k for k, v in idx.items() if v.get("m") == "US"):
    d = json.load(open("data/flow/%s.json" % t))
    c = cik.get(t) or cik.get(t.replace(".", "-"))
    s = U.get_json("https://data.sec.gov/submissions/CIK%s.json" % str(c).zfill(10)) if c else None; time.sleep(0.12)
    r = ((s or {}).get("filings") or {}).get("recent") or {}
    best = ("", "", "")
    for f, rd, fd in zip(r.get("form", []), r.get("reportDate", []), r.get("filingDate", [])):
        if f in ("10-Q", "10-K") and rd > best[0]:
            best = (rd, f, fd)
    end = d.get("end") or ""
    if not end and d.get("y"):
        end = "%d-%02d-28" % (d["y"], d["q"] * 3)
    if best[0] and best[0] > end:
        st.append((t, d.get("name"), d.get("period"), end, best))
    else:
        ok += 1
print("=== 해외 %d곳 중 최신 %d · 더 최근 보고서 있음 %d" % (ok + len(st), ok, len(st)))
for x in st:
    print("STALE", *x)
