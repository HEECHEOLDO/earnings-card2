#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'그때 샀다면' 해외 금액을 독립 자료와 맞춰 본다.

  python3 verify_us.py

우리 파일(data/monthly_us.json)로 buy.html 과 똑같이 계산한 '주가 배수'를
digrin.com 의 배당 조정 월말 종가(2026-10-09 조회)로 따로 계산한 배수와
나란히 놓는다. 환율은 양쪽에 같은 값(우리 fx_usdkrw.json)을 곱한다 —
환율 파일은 영국중앙은행 값과 따로 맞춰 봤다(2026-09-30 1,355.40 vs 1,355.78).
그래서 여기서 보는 차이는 순수하게 주가 자료의 차이다.

기간은 10년. 10년 자료가 없는 ETF(QQQM·JEPI)는 5년으로 본다.
"""
import json
from datetime import date, timedelta

# digrin 배당 조정 월말 종가 — {기호: (기간, 그때, 지금)}
# 지금 = 2026-09, 그때 = 기간만큼 앞의 9월
OUT = {
    "SPY":  (10, 184.72, 762.63),   "VOO":  (10, 169.18, 700.86),
    "IVV":  (10, 184.45, 765.85),   "QQQ":  (10, 110.90, 739.77),
    "DIA":  (10, 151.13, 508.50),   "IWM":  (10, 109.88, 277.86),
    "VTI":  (10, 94.95, 374.24),    "VUG":  (10, 17.29, 90.11),
    "VTV":  (10, 68.09, 216.08),    "SCHD": (10, 10.08, 32.53),
    "XLU":  (10, 17.87, 39.44),     "ARKK": (10, 20.70, 89.10),
    "VNQ":  (10, 58.25, 89.63),     "TLT":  (10, 103.41, 77.78),
    "IEF":  (10, 88.18, 89.00),     "BND":  (10, 62.98, 70.15),
    "AGG":  (10, 84.44, 94.21),     "TQQQ": (10, 2.54, 78.03),
    "QLD":  (10, 5.32, 95.65),      "SSO":  (10, 8.43, 69.28),
    "UPRO": (10, 11.65, 146.85),    "SOXL": (10, 2.92, 147.86),
    "SQQQ": (10, 101920.13, 34.41), "TMF":  (10, 228.49, 25.68),
    "QQQM": (5, 142.69, 304.64),    "JEPI": (5, 38.68, 56.22),
}
# 바깥 자료가 믿기 어려운 것 — 대조하지 않고 우리 값만 보여준다
SKIP = {
    "SOXS": "digrin 이 2016년 값을 1,000,000 달러로 잘라 적어 둠",
    "SPLG": "digrin 에 2026년 9월 값이 없음 (2025년 이름·분할 변경)",
}


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
            return rates[k]
        d -= timedelta(days=1)
    return None


def money(a, span=10):
    """카드에 찍히는 모양 그대로 (buy.html 의 unit·vtxt·decOf 와 같은 규칙)"""
    if a >= 0.01:
        dec = 2 if (span <= 3 or a < 0.1) else 1
        return ("%." + str(dec) + "f") % a + "억"
    if a >= 0.0001:
        return "%d만" % round(a * 10000)
    return "{:,}원".format(round(a * 1e8))


def px(v):
    return "{:,.0f}".format(v) if v >= 1000 else "%.5g" % v


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
    f1 = fx_on(rates, mend(ref))
    print("기준 달 %s 말 · 환율 %s원 · 해외 %d종목\n" % (mstr(ref), "{:,.2f}".format(f1), len(items)))
    print("  %-5s %3s  %-22s %-22s %8s %8s  %s"
          % ("기호", "기간", "우리 자료 (그때→지금)", "digrin (그때→지금)", "카드", "바깥", "판정"))

    ok = bad = 0
    for c in sorted(items, key=lambda x: (x not in OUT, x)):
        span = OUT[c][0] if c in OUT else 10
        k0 = ref - span * 12
        p0, p1 = at(c, k0), at(c, ref)
        if p0 is None or p1 is None:
            print("  %-5s %3d년  %s 값 없음 — 카드에서도 이 기간은 안 나옵니다"
                  % (c, span, mstr(k0) if p0 is None else mstr(ref)))
            continue
        fx = f1 / fx_on(rates, mend(k0))
        ours = p1 / p0 * fx
        mine = "%s→%s" % (px(p0), px(p1))
        if c in OUT:
            _, e0, e1 = OUT[c]
            ext = e1 / e0 * fx
            gap = (ours / ext - 1) * 100
            # digrin 은 소수 둘째 자리에서 반올림한다 — 값이 작으면 그만큼 흔들린다
            tol = 1.0 + 100 * 0.005 / e0
            good = abs(gap) <= tol
            ok += good
            bad += not good
            print("  %-5s %3d년  %-22s %-22s %8s %8s  %s (차이 %+.2f%%)"
                  % (c, span, mine, "%s→%s" % (px(e0), px(e1)), money(ours, span), money(ext, span),
                     "OK" if good else "확인 필요", gap))
        else:
            why = SKIP.get(c, "바깥 자료 없음")
            print("  %-5s %3d년  %-22s %-22s %8s %8s  대조 안 함 — %s"
                  % (c, span, mine, "-", money(ours, span), "-", why))

    print("\nOK %d개 · 확인 필요 %d개" % (ok, bad))
    print("(배당 조정 방식이 출처마다 조금 달라 1% 안팎 차이는 정상입니다.")
    print(" 값이 작은 ETF 는 digrin 의 반올림만큼 허용 폭을 넓혀 봅니다)")


if __name__ == "__main__":
    main()
