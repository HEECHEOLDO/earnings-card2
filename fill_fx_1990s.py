#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1996~1998년 연말 환율을 data/rank.json 에 채운다 (fill_fx_history.py 가 못 채운 해).

  python3 fill_fx_1990s.py

1) 미 연준 FRED 를 넉넉한 시간(3분)으로 한 번 더 시도한다.
2) 그래도 안 되면 한국은행 연말 원/달러 환율(널리 알려진 값)을 넣는다:
     1996년 844.2원 · 1997년 1,415.2원 (외환위기) · 1998년 1,207.8원
두 번 돌려도 괜찮다.
"""
import json
import os
import urllib.request

OUT = os.path.join("data", "rank.json")
KNOWN = {1996: 844.2, 1997: 1415.2, 1998: 1207.8}      # 한국은행 연말 기준


def fred():
    req = urllib.request.Request("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXKOUS&cosd=1996-01-01&coed=1998-12-31",
                                 headers={"User-Agent": "Mozilla/5.0"})
    txt = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
    out = {}
    for line in txt.splitlines()[1:]:
        p = line.split(",")
        if len(p) == 2 and p[1] not in ("", "."):
            out[int(p[0][:4])] = round(float(p[1]), 2)
    return {y: v for y, v in out.items() if y in KNOWN}


rk = json.load(open(OUT, encoding="utf-8"))
try:
    fx, src = fred(), "FRED"
    if len(fx) < 3:
        raise RuntimeError("일부만 받음")
except Exception as e:                             # noqa: BLE001
    print("  FRED 안 됨 (%r) → 한국은행 연말 환율로 채웁니다" % e)
    fx, src = KNOWN, "한국은행"
n = 0
for y, v in fx.items():
    if str(y) in rk["cols"]:
        rk["cols"][str(y)]["usdkrw"] = v; n += 1
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(rk, f, ensure_ascii=False, separators=(",", ":"))
print("출처 %s · %s" % (src, " · ".join("%d년 %s원" % (y, format(v, ",.1f")) for y, v in sorted(fx.items()))))
print("%d개 해에 넣었습니다" % n)
