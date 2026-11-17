"""시험용 — 2026 반기 누적·3분기 누적·3분기 3개월 매출 비교 (저장 안 함)"""
import os, sys
sys.path.insert(0, os.getcwd())
import collect as C
C.API_KEY = C.get_key()
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "288980").split(","):
    cc = cmap[code]["corp_code"]
    h = C.fetch_fs(cc, 2026, C.REPRT["HALF"]); q3 = C.fetch_fs(cc, 2026, C.REPRT["Q3"])
    g = lambda fs, cum: C.pick_account(fs, "rev", cumulative=cum) if fs else None
    hc, qc, q3m = g(h, True), g(q3, True), g(q3, False)
    go = lambda fs, cum: C.pick_account(fs, "op", cumulative=cum) if fs else None
    ho, qo, q3o = go(h, True), go(q3, True), go(q3, False)
    print("P3op", code, "반기누적", ho and round(ho / 1e8, 1), "3분기누적", qo and round(qo / 1e8, 1), "누적차", (qo and ho is not None) and round((qo - ho) / 1e8, 1), "3개월칸", q3o and round(q3o / 1e8, 1), flush=True)
    print("P3", code, cmap[code]["name"], "반기누적", hc and round(hc / 1e8, 1), "3분기누적", qc and round(qc / 1e8, 1), "누적차", (qc and hc) and round((qc - hc) / 1e8, 1), "3개월칸", q3m and round(q3m / 1e8, 1), flush=True)
