#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 '최근 종가'(nc)를 주가 추이 일별 종가로 최신화 (2026-11, 호출 0회)

왜: '그때 샀다면'·'수익률' 탭의 해외 '지금' 값(returns.json / monthly_us.json 의 nc)은 collect_prices 가
    KST 03:00 에 채운다. 그때는 미국 장이 아직 열려 있어(06:00 마감) 하루 늦은 값이 된다 (11/24 에 11/20 기준).
    주가 탭(data/chart/us)은 07:10 에 장 마감 종가까지 받으므로, 그 값으로 nc 를 이어 붙인다.

  · nc = [기준일 종가, 최근 종가, 최근 날짜] 에서 '최근 종가·날짜'만 바꾼다.
  · 같은 기준(수정주가)인지: 일별 파일의 기준일(ncb) 종가가 nc 의 기준일 종가와 0.5% 안에서 같을 때만.
  · 같은 날이어도 값이 다르면 일별(장 마감 종가)로 바꾼다 — 03:00 수집이 장중 값을 넣었을 수 있다.
  · 올해 수익률(years[올해])은 (1+옛 값) × 새 종가/옛 종가 − 1 로 같이 옮긴다. 해가 바뀐 뒤 첫날은 건드리지 않는다.

  python3 sync_nc.py
"""
import json
import os

RET = os.path.join("data", "returns.json")
MON = os.path.join("data", "monthly_us.json")
CH = os.path.join("data", "chart", "us")


def ds(n):
    s = str(n)
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:8])


def main():
    r = json.load(open(RET, encoding="utf-8"))
    m = json.load(open(MON, encoding="utf-8"))
    n = bad = 0
    for code, it in (r.get("items") or {}).items():
        nc = it.get("nc")
        if it.get("market") != "US" or not nc or len(nc) != 3:
            continue
        try:
            d = json.load(open(os.path.join(CH, code + ".json"), encoding="utf-8"))["d"]
        except Exception:                         # noqa: BLE001
            continue
        if not d or ds(d[-1][0]) < nc[2] or (ds(d[-1][0]) == nc[2] and d[-1][1] == nc[1]):
            continue
        at = {ds(a): b for a, b in d}
        b0 = at.get(it.get("ncb") or "")
        if not b0 or not nc[0] or abs(b0 / nc[0] - 1) > 0.005:   # 기준일 종가가 같아야 같은 수정주가 기준
            bad += 1
            continue
        new_d, new_p = ds(d[-1][0]), d[-1][1]
        if new_d[:4] != nc[2][:4]:                # 해가 바뀌었다 — collect_prices 가 연말 종가로 다시 나눈다
            continue
        y = (it.get("years") or {}).get(new_d[:4])
        if y is not None:
            it["years"][new_d[:4]] = round(((1 + y / 100) * new_p / nc[1] - 1) * 100, 2)
        it["nc"] = [nc[0], new_p, new_d]
        it["asof"] = new_d
        o = (m.get("items") or {}).get(code)
        if o is not None:
            o["nc"] = it["nc"]
        n += 1
    if n:
        json.dump(r, open(RET, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        json.dump(m, open(MON, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("해외 최근 종가 최신화: %d종목 · 기준이 안 맞아 둔 종목 %d" % (n, bad))


if __name__ == "__main__":
    main()
