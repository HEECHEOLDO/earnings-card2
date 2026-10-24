#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""변천사 영상용 — 해마다 '6월 말(반기 말)' 시가총액 순위를 모은다 → data/rank_half.json

  python3 collect_half.py            빠진 해 채우기 (1995~2019 는 _marcap/ 자료, 2020~ 는 공공데이터포털)
  python3 collect_half.py --recent   2020년부터만 (GitHub Actions 에서 매일 — 새 6월 말이 생기면 한 칸 더한다)
  python3 collect_half.py --force    있는 해도 다시
  python3 collect_half.py --show     받아 둔 것 보기

rank.json(연말)과 칸 모양이 같다:  cols { "1996": {date, src, kospi, kosdaq, all}, ... }  — 키는 그 해 6월 말.
시가총액 탭·시총 순위 탭은 그대로 연말만 쓰고, 이 파일은 영상이 연말 사이에 끼워 넣을 때만 쓴다.
미국 6월 말은 따로 (collect_us_mcap.py) 같은 파일의 us·us_only 에 더한다.
"""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import collect_rank as C

OUT = os.path.join("data", "rank_half.json")


def june_marcap(y):
    """marcap 연도 파일에서 y년 6월 30일 이전 마지막 거래일"""
    import import_marcap as M
    path = M.fetch(y)
    cut = "%d-06-30" % y
    if path.endswith(".parquet"):
        import pandas as pd
        df = pd.read_parquet(path)
        cols = {str(k).lower(): k for k in df.columns}
        if "date" not in cols and df.index.name and str(df.index.name).lower() == "date":
            df = df.reset_index()
            cols = {str(k).lower(): k for k in df.columns}
        d = df[cols["date"]].astype(str).str[:10]
        df, d = df[(d >= "%d-01-01" % y) & (d <= cut)], d[(d >= "%d-01-01" % y) & (d <= cut)]
        if df.empty:
            return "", []
        last = d.max()
        df = df[d == last]
        rows = []
        for code, name, mk, cap in zip(df[cols["code"]], df[cols["name"]], df[cols["market"]], df[cols["marcap"]]):
            m = str(mk or "").upper()
            m = "KOSDAQ" if m.startswith("KOSDAQ") else "KOSPI" if m.startswith("KOSPI") else m
            try:
                cap = int(float(cap or 0))
            except (TypeError, ValueError):
                cap = 0
            rows.append((str(code).zfill(6), str(name), m, cap))
    else:
        import csv, gzip
        opener = gzip.open if path.endswith(".gz") else open
        last, rows = "", []
        with opener(path, "rt", encoding="utf-8-sig", errors="replace") as f:
            rd = csv.DictReader(f)
            cols = {k.lower(): k for k in rd.fieldnames or []}
            for r in rd:
                dd = (r[cols["date"]] or "")[:10]
                if not dd.startswith(str(y)) or dd > cut or dd < last:
                    continue
                if dd > last:
                    last, rows = dd, []
                m = (r[cols["market"]] or "").upper()
                m = "KOSDAQ" if m.startswith("KOSDAQ") else "KOSPI" if m.startswith("KOSPI") else m
                try:
                    cap = int(float(r[cols["marcap"]] or 0))
                except ValueError:
                    cap = 0
                rows.append((str(r[cols["code"]]).zfill(6), r[cols["name"]], m, cap))
    if rows and max(r[3] for r in rows) < 10 ** 11:           # 백만원 단위 파일
        rows = [(c, n, m, cap * 10 ** 6) for c, n, m, cap in rows]
    return last, rows


def show(j):
    print("받은 날 %s · 칸 %d개" % (j.get("updated"), len(j.get("cols", {}))))
    for k in sorted(j.get("cols", {})):
        c = j["cols"][k]
        kr = " · ".join(r[1] for r in (c.get("kospi") or [])[:3]) or "-"
        us = " · ".join(r[1] for r in (c.get("us") or [])[:3]) or "-"
        print("  %s  %-10s 코스피 %s  |  미국 %s" % (k, c.get("date", ""), kr, us))


def main():
    try:
        j = json.load(open(OUT, encoding="utf-8"))
    except Exception:                              # noqa: BLE001
        j = {"cols": {}}
    if "--show" in sys.argv:
        return show(j)
    cols = j.setdefault("cols", {})
    force, recent = "--force" in sys.argv, "--recent" in sys.argv
    today = datetime.now(C.KST).date()
    done, key = 0, None
    last_year = today.year if today > date(today.year, 7, 1) else today.year - 1   # 올해 6월 말은 7월 2일부터
    for y in range(1995 if not recent else C.START, last_year + 1):
        if str(y) in cols and cols[str(y)].get("kospi") and not force:
            continue
        try:
            if y < C.START:
                d, rows = june_marcap(y)
                d = date.fromisoformat(d) if d else None
                src = "marcap"
            else:
                key = key or C.get_key()
                d, rows = C.last_trading(key, date(y, 6, 30))
                src = "datago"
        except Exception as e:                     # noqa: BLE001
            print("  !! %d  %s" % (y, e))
            continue
        if not rows or not d:
            print("  !! %d  6월 말 자료가 없습니다" % y)
            continue
        col = C.column(d, rows)
        col["src"] = src
        old = cols.get(str(y)) or {}
        col.update({k: v for k, v in old.items() if k.startswith("us")})   # 미국 칸은 그대로
        cols[str(y)] = col
        done += 1
        print("  %d  %s  코스피 %s" % (y, d, " · ".join("%s %s조" % (r[1], format(r[2] // 10000, ","))
                                                       for r in col["kospi"][:3])))
        time.sleep(0.2)
    j.update({"updated": today.isoformat(), "unit": "억원", "top": C.TOP,
              "note": "해마다 6월 말(반기 말) 순위 — 변천사 영상이 연말 사이에 끼워 넣는다"})
    if done or not os.path.exists(OUT):
        os.makedirs("data", exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    print("\n%d개 해를 더했습니다 → %s (칸 %d개%s)" % (done, OUT, len(cols),
                                               " · 공공데이터포털 호출 %d회" % C.CALLS[0] if C.CALLS[0] else ""))


if __name__ == "__main__":
    main()
