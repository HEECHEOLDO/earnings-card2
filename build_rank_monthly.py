#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""월말 시총 순위 (국내, 1995년 5월~) → data/rank_monthly.json — 시가총액 탭 '변천사 영상'의 '매월' 간격용

  python3 build_rank_monthly.py          처음엔 1995년부터 전부, 그다음엔 올해·작년만 다시
  python3 build_rank_monthly.py --all    전부 다시
  python3 build_rank_monthly.py --us-only  국내는 그대로 두고 미국(추정)만 다시

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


def _ym_add(ym, k):
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + k
    return "%04d-%02d" % (y + m // 12, m % 12 + 1)


def add_us(months):
    """미국 달마다 순위 (추정) — 달별 시가총액 무료 자료가 없어서
    연말 실제 시가총액(rank.json 의 us·us_only, companiesmarketcap)을 기준점으로 두고,
    그 사이 달은 월말 주가(monthly_us.json, 2005-11~) 오르내림만큼 늘리고 줄인다.
    두 연말 사이 주식 수 변화 등으로 생기는 차이는 달마다 조금씩 나눠 맞춰, 연말에는 실제 값과 같아진다.
    주가가 없는 회사(옛 회사·외국 회사)와 2005년 이전은 두 연말 값 사이를 고르게(기하) 잇는다."""
    try:
        R = json.load(open(C.OUT, encoding="utf-8"))["cols"]
        P = json.load(open(os.path.join("data", "monthly_us.json"), encoding="utf-8"))["items"]
    except Exception as e:                       # noqa: BLE001
        print("  !! 미국: 자료 없음 (%s)" % e)
        return
    def price(t, ym):
        it = P.get(t)
        if not it:
            return None
        s = it["s"]
        i = (int(ym[:4]) - int(s[:4])) * 12 + int(ym[5:7]) - int(s[5:7])
        v = it["v"]
        return v[i] if 0 <= i < len(v) and v[i] else None
    anchors = []                                  # (월, 시점 키) — 연말들 + 지금
    for y in sorted(k for k in R if k.isdigit()):
        if R[y].get("us"):
            anchors.append(("%s-12" % y, y))
    now = R.get("now") or {}
    nd = now.get("us_date") or now.get("date") or ""
    if now.get("us") and len(nd) >= 7 and anchors and nd[:7] > anchors[-1][0]:
        anchors.append((nd[:7], "now"))
    n_months = 0
    for (m0, k0), (m1, k1) in zip(anchors, anchors[1:]):
        span = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
        for mk in ("us", "us_only"):
            A = {r[0]: (r[1], r[2]) for r in R[k0].get(mk, [])[:40]}
            B = {r[0]: (r[1], r[2]) for r in R[k1].get(mk, [])[:40]}
            for step in range(1, span + 1):
                ym = _ym_add(m0, step)
                if k1 == "now" and step == span:
                    continue                      # 이번 달은 rank.html 이 '지금' 칸으로 붙인다
                f = step / span
                if step == span:                  # 연말 = 실제 순위 그대로
                    months.setdefault(ym, {"date": ym + "-28"})[mk] = [list(r) for r in R[k1].get(mk, [])[:30]]
                    n_months += (mk == "us")
                    continue
                # 한쪽 연말 목록(40위)에 없는 회사는 그 목록의 끝자리 바로 아래 값으로 잇는다
                # (루슨트 2000년: 1999년 말 2위 → 2000년 말 40위 밖. 없다고 1999년 값을 그대로 두면 안 된다)
                fa = min(v for _, v in A.values()) * 0.95 if A else 0
                fb = min(v for _, v in B.values()) * 0.95 if B else 0
                rows = []
                for c in set(A) | set(B):
                    a, b = A.get(c), B.get(c)
                    nm = (b if (b and f >= 0.5) or not a else a)[0]
                    pa, pm, pb = price(c, m0), price(c, ym), price(c, m1)
                    if a and b and pa and pm and pb:
                        drift = b[1] / (a[1] * pb / pa)
                        v = a[1] * pm / pa * drift ** f
                    elif a and pa and pm:
                        v = a[1] * pm / pa
                    elif b and pb and pm:
                        v = b[1] * pm / pb
                    else:
                        va, vb = (a[1] if a else fa), (b[1] if b else fb)
                        v = va * (vb / va) ** f if va > 0 and vb > 0 else (va or vb)
                    rows.append([c, nm, round(v, 1)])
                rows.sort(key=lambda r: -r[2])
                months.setdefault(ym, {"date": ym + "-28"})[mk] = rows[:30]
                n_months += (mk == "us")
    print("  미국 %d개월 (연말 실제 값 + 월말 주가로 추정)" % n_months)


def main():
    try:
        j = json.load(open(OUT, encoding="utf-8"))
    except Exception:                            # noqa: BLE001
        j = {"months": {}}
    months = j.setdefault("months", {})
    this = date.today().year
    have_years = {k[:4] for k in months}
    years = [] if "--us-only" in sys.argv else [y for y in range(FIRST, this + 1)
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
    add_us(months)                               # 미국은 늘 다시 (호출 없음)
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
