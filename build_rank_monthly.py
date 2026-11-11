#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""월말 시총 순위 (국내, 1995년 5월~) → data/rank_monthly.json — 시가총액 탭 '변천사 영상'의 '매월' 간격용

  python3 build_rank_monthly.py          처음엔 1995년부터 전부, 그다음엔 올해·작년만 다시
  python3 build_rank_monthly.py --all    전부 다시

출처: FinanceData/marcap (import_marcap.py 와 같은 곳 — 한국거래소 일별 전 종목 시가총액, 연도별 parquet).
달마다 마지막 거래일 하루를 골라 collect_rank.column() 으로 코스피·코스닥·전체 TOP 50 을 만든다.
pandas·pyarrow 가 필요하다 (워크플로에서 설치).
"""
import json
import os
import sys
from datetime import date

import collect_rank as C
import import_marcap as M

OUT = os.path.join("data", "rank_monthly.json")
FIRST = 1995


def months_of(path, y):
    import pandas as pd
    df = pd.read_parquet(path)
    cols = {str(k).lower(): k for k in df.columns}
    if "date" not in cols and df.index.name and str(df.index.name).lower() == "date":
        df = df.reset_index()
        cols = {str(k).lower(): k for k in df.columns}
    d = df[cols["date"]].astype(str).str[:10]
    df = df.assign(_d=d)
    df = df[df["_d"].str.startswith(str(y))]
    out = {}
    for ym, g in df.groupby(df["_d"].str[:7]):
        last = g["_d"].max()
        g = g[g["_d"] == last]
        rows = []
        for code, name, mk, cap in zip(g[cols["code"]], g[cols["name"]], g[cols["market"]], g[cols["marcap"]]):
            m = str(mk or "").upper()
            m = "KOSDAQ" if m.startswith("KOSDAQ") else "KOSPI" if m.startswith("KOSPI") else m
            try:
                cap = int(float(cap or 0))
            except (TypeError, ValueError):
                cap = 0
            rows.append((str(code).zfill(6), str(name), m, cap))
        if rows and max(r[3] for r in rows) < 10 ** 11:          # 백만원 단위로 적힌 해
            rows = [(c, n, m, cap * 10 ** 6) for c, n, m, cap in rows]
        col = C.column(date.fromisoformat(last), rows)
        out[ym] = {"date": col["date"], "kospi": col["kospi"], "kosdaq": col["kosdaq"], "all": col["all"]}
    return out


def main():
    try:
        j = json.load(open(OUT, encoding="utf-8"))
    except Exception:                            # noqa: BLE001
        j = {"months": {}}
    months = j.setdefault("months", {})
    this = date.today().year
    have_years = {k[:4] for k in months}
    years = [y for y in range(FIRST, this + 1)
             if "--all" in sys.argv or str(y) not in have_years or y >= this - 1]
    for y in years:
        try:
            path = M.fetch(y)
            got = months_of(path, y)
        except Exception as e:                   # noqa: BLE001
            print("  !! %d  %s" % (y, e))
            continue
        for k in [k for k in months if k.startswith(str(y))]:
            months.pop(k)
        months.update(got)
        ks = sorted(got)
        if ks:
            top = got[ks[-1]]["all"][:3]
            print("  %d  %s~%s (%d개월)  %s" % (y, ks[0], ks[-1], len(ks), " · ".join(r[1] for r in top)))
    j["months"] = dict(sorted(months.items()))
    j["updated"] = date.today().isoformat()
    j["unit"] = "억원"
    j["source"] = "FinanceData/marcap (한국거래소 일별 시가총액) · 달마다 마지막 거래일"
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    ks = list(j["months"])
    print("저장 %s · %d개월 (%s ~ %s) · %.1fMB" % (OUT, len(ks), ks[0] if ks else "-", ks[-1] if ks else "-",
                                               os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
