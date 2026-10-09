#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'그때 샀다면' 해외 금액을 독립 자료와 맞춰 본다.

  python3 verify_us.py

1) 우리 파일(data/monthly_us.json, data/fx_usdkrw.json)로 buy.html 과 똑같이 계산
2) 바깥 자료로 따로 계산한 값과 나란히 놓는다
   - 주가: digrin.com 의 배당 조정 월말 종가 (2026-10-09 조회)
   - 환율: 2026-09-30 영국중앙은행 1,355.78원 / 2016-09-28 유럽중앙은행 1,097.34원
     (2016-09-30 값은 바깥에서 못 구해 이틀 전 값을 썼다 — 그래서 '대략' 비교다)
"""
import json
from datetime import date, timedelta

# 바깥 자료 — 우리 수집기와 아무 관계 없는 출처
OUT_PX = {   # 기호: {달: 조정종가}
    "SPY":  {"2016-09": 184.72, "2026-09": 762.63},
    "QQQ":  {"2016-09": 110.90, "2026-09": 739.77},
    "SCHD": {"2016-09": 10.08, "2026-09": 32.53},
}
OUT_FX = {"2016-09": 1097.34, "2026-09": 1355.78}


def mkey(s):
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def mstr(k):
    return "%d-%02d" % (k // 12, k % 12 + 1)


def mend(k):
    y, m = k // 12, k % 12 + 1
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def fx_on(rates, d):
    for _ in range(11):
        k = d.isoformat()
        if k in rates:
            return k, rates[k]
        d -= timedelta(days=1)
    return None, None


def main():
    mj = json.load(open("data/monthly_us.json", encoding="utf-8"))
    items = mj["items"]
    rates = json.load(open("data/fx_usdkrw.json", encoding="utf-8"))["rates"]

    # buy.html 과 같은 규칙: 받아온 달(asof)부터는 미완성으로 보고 버린다
    cap = mkey(mj.get("updated", "9999-12")[:7]) - 1
    lim = {}
    for c, o in items.items():
        v, b = o.get("v") or [], mkey(o["s"])
        last = max([b + i for i, x in enumerate(v) if isinstance(x, (int, float))] or [-1])
        a = o.get("asof")
        lim[c] = min((mkey(a[:7]) if a else last) - 1, cap)

    def at(c, k):
        o = items[c]
        i = k - mkey(o["s"])
        v = o.get("v") or []
        if k > lim[c] or not (0 <= i < len(v)):
            return None
        x = v[i]
        return x if isinstance(x, (int, float)) and x > 0 else None

    hi = max(min(mkey(o["s"]) + len(o["v"]) - 1, lim[c]) for c, o in items.items())
    need = max(1, -(-len(items) * 7 // 10))
    ref = next((k for k in range(hi, hi - 6, -1)
                if sum(1 for c in items if at(c, k) is not None) >= need), hi)
    d1, f1 = fx_on(rates, mend(ref))
    print("기준 달 %s 말 · 환율 %s %s원\n" % (mstr(ref), d1, "{:,.2f}".format(f1)))

    bad = 0
    for c in ("SPY", "QQQ", "SCHD", "DIA", "TQQQ", "VOO"):
        if c not in items or at(c, ref) is None:
            continue
        for n in (5, 10, 20):
            k0 = ref - n * 12
            p0, p1 = at(c, k0), at(c, ref)
            if p0 is None:
                continue
            d0, f0 = fx_on(rates, mend(k0))
            amt = p1 / p0 * f1 / f0
            card = ("%.1f" % amt) + "억원"
            line = ("%-5s %2d년  $%-9s → $%-9s  환율 %8s → %8s  = %s"
                    % (c, n, p0, p1, "{:,.2f}".format(f0), "{:,.2f}".format(f1), card))
            o = OUT_PX.get(c, {})
            m0, m1 = mstr(k0), mstr(ref)
            if m0 in o and m1 in o and m0 in OUT_FX and m1 in OUT_FX:
                ext = o[m1] / o[m0] * OUT_FX[m1] / OUT_FX[m0]
                gap = (amt / ext - 1) * 100
                flag = "OK" if abs(gap) < 1.5 else "확인 필요"
                bad += flag != "OK"
                line += "   | 바깥 자료 %.2f억 (차이 %+.2f%%) %s" % (ext, gap, flag)
            print(line)
        print()
    print("바깥 자료와 1.5%% 넘게 다른 줄: %d개" % bad)
    print("(환율 2016-09 를 이틀 전 값으로 썼고, 배당 조정 방식이 출처마다 조금 달라")
    print(" 0.5% 안팎 차이는 정상입니다)")


if __name__ == "__main__":
    main()
