#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주요 시장 지수 → data/chart/idx/{코드}.json  (주가 추이 카드용, 2026-11)

  python3 collect_chart_idx.py

국내 지수는 네이버(일별 11년 치 한 번에), 해외 지수는 CNBC(1년 일별 + 약 10년 주별).
네이버가 막히면 국내도 CNBC(.KS11 등)로 받는다. 받은 게 없으면 있던 파일을 그대로 둔다.
파일 모양은 종목과 같다: {"u":"PT","d":[[YYYYMMDD,값]...],"w":[[YYYYMMDD,값]...]}
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect_chart_us import cnbc_bars, get, weekly  # noqa: E402

OUT_DIR = os.path.join("data", "chart", "idx")
DAYS = 400
YEARS = 11

# 코드: (이름, 네이버 기호, CNBC 기호)  — 코드·이름은 price.js 의 INDICES 와 맞춘다
INDICES = {
    "KOSPI":    ("코스피", "KOSPI", ".KS11"),
    "KOSDAQ":   ("코스닥", "KOSDAQ", ".KQ11"),
    "KOSPI200": ("코스피 200", "KPI200", None),
    "SPX":      ("S&P 500", None, ".SPX"),
    "IXIC":     ("나스닥 종합", None, ".IXIC"),
    "NDX":      ("나스닥 100", None, ".NDX"),
    "DJI":      ("다우존스", None, ".DJI"),
    "SOX":      ("필라델피아 반도체", None, ".SOX"),
    "RUT":      ("러셀 2000", None, ".RUT"),
    "N225":     ("닛케이 225", None, ".N225"),
    "HSI":      ("항셍", None, ".HSI"),
    "SSEC":     ("상하이 종합", None, ".SSEC"),
}


def naver_rows(sym, today):
    url = ("https://api.finance.naver.com/siseJson.naver?symbol=%s&requestType=1&startTime=%s&endTime=%s&timeframe=day"
           % (sym, (today - timedelta(days=int(YEARS * 365.25) + 10)).strftime("%Y%m%d"), today.strftime("%Y%m%d")))
    t = get(url, tries=3, accept="*/*")
    if not t:
        return None
    out = []
    for m in re.finditer(r'\["(\d{8})"\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)', t):
        c = float(m.group(5))
        if c > 0:
            out.append((int(m.group(1)), c))
    out.sort()
    return out if len(out) > 100 else None


def main():
    today = date.today()
    d0 = int((today - timedelta(days=DAYS)).strftime("%Y%m%d"))
    w0 = int((today - timedelta(days=int(YEARS * 365.25))).strftime("%Y%m%d"))
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    for code, (name, nv, cn) in INDICES.items():
        daily = wk = None
        src = ""
        if nv:
            rows = naver_rows(nv, today)
            if rows:
                daily, wk, src = rows, weekly(rows), "naver"
        if not daily and cn:
            daily = cnbc_bars(cn, "1Y")
            if daily:
                wk = weekly(sorted(set(x for x in (cnbc_bars(cn, "5Y") or []) if x[0] < daily[0][0]) | set(daily)))
                src = "cnbc"
        time.sleep(0.4)
        if not daily or len(daily) < 2:
            print("  %-9s %s  실패 — 있던 파일 그대로" % (code, name))
            continue
        j = {"u": "PT", "src": src,
             "d": [[a, round(b, 2)] for a, b in daily if a >= d0],
             "w": [[a, round(b, 2)] for a, b in wk if a >= w0]}
        with open(os.path.join(OUT_DIR, code + ".json"), "w", encoding="utf-8") as f:
            json.dump(j, f, separators=(",", ":"))
        ok += 1
        print("  %-9s %-10s %-6s 일별 %d · 주별 %d · 마지막 %s %.2f" % (code, name, src, len(j["d"]), len(j["w"]), j["d"][-1][0], j["d"][-1][1]))
    print("끝: %d / %d" % (ok, len(INDICES)))


if __name__ == "__main__":
    main()
