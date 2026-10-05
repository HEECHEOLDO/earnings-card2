#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stooq 가 '해외 일별'을 주는지 확인한다. 5분이면 끝난다.

왜 확인하나
----------
배당 기준을 '제외'로 통일하기로 하면, 해외도 알파밴티지(배당 포함)를 쓸
이유가 없어진다. Stooq 는 배당 제외·분할 반영이고 키도 한도도 없다.
만약 Stooq 가 일별까지 준다면 그림이 이렇게 바뀐다.

           지금                      Stooq 일별이 되면
  국내   네이버 일별 · 배당 제외      그대로
  해외   알파밴티지 월말 · 배당 포함   Stooq 일별 · 배당 제외
  섞기   날짜도 배당도 안 맞음        그냥 맞음
  한도   하루 25회 · 한 바퀴 21일     없음
  지연   공통 끝점이 한 달 뒤처짐      오늘까지

즉 '해외만 월말', '섞으면 해외 기준' 같은 규칙 자체가 필요 없어진다.

환율도 같이 본다
----------------
fx.json 에는 오늘 환율 하나뿐이라 2016년 10월 5일 환율을 모른다. '1억원
투자했다면' 이라고 말하는 이상 원화 기준이어야 하므로 과거 환율이 필요하다.
Stooq 에 usdkrw 심볼이 있어서, 주가가 되면 환율도 같은 코드로 받는다.
안 되면 Frankfurter (api.frankfurter.app, 키 없음) 로 받으면 된다.

보는 법
-------
  python3 probe_stooq.py

  일별 OK 가 전부 통과  -> 구조를 단순하게 갈 수 있다
  막힘/없음 이 섞여 나옴 -> Stooq 는 못 믿는다. 지금 설계(월말)로 간다
"""

import csv
import io
import sys
import time
import urllib.error
import urllib.request

HOSTS = ["https://stooq.com", "https://stooq.pl"]
PATH = "/q/d/l/?s=%s&i=%s&d1=%s&d2=%s"

# 성격이 다른 것들을 골랐다. 대형주 하나로 되는 걸 확인해 봐야 소용없다.
SAMPLES = [
    ("aapl.us", "애플 — 대형주"),
    ("brk-b.us", "버크셔 B — 기호에 점·하이픈"),
    ("spy.us", "SPY — 대형 ETF"),
    ("schd.us", "SCHD — 배당 ETF (배당 차이가 가장 크게 보일 종목)"),
    ("aaad.us", "AAAD — 소형 ETF (커버리지 바닥 확인)"),
    ("005930.kr", "삼성전자 — 국내도 주는지"),
    ("usdkrw", "달러/원 환율 — 해외 금액을 원화로 바꾸려면 필요"),
]

D1, D2 = "20160901", "20161031"       # 10년 전 언저리 한 달


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fincard probe)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %d" % e.code
    except Exception as e:                    # noqa: BLE001
        return None, type(e).__name__


def fetch(sym, interval):
    for host in HOSTS:
        txt, why = get(host + PATH % (sym, interval, D1, D2))
        time.sleep(0.4)
        if not txt:
            continue
        head = txt.strip()[:60].replace("\n", " | ")
        if not txt.lower().lstrip().startswith("date"):
            # Stooq 는 막을 때 'Exceeded the daily hits limit' 같은 평문을 준다
            return None, ("막힘: " + head if "limit" in txt.lower() else "없음: " + head)
        rows = list(csv.DictReader(io.StringIO(txt.strip())))
        rows = [r for r in rows if r.get("Close")]
        if not rows:
            return None, "빈 응답"
        return rows, host
    return None, why or "연결 실패"


def main():
    print("Stooq 확인 — 구간 %s ~ %s\n" % (D1, D2))
    ok_d = ok_m = 0
    for sym, label in SAMPLES:
        line = "%-12s %-42s" % (sym, label)
        drows, dinfo = fetch(sym, "d")
        mrows, minfo = fetch(sym, "m")
        if drows:
            ok_d += 1
            d = "일별 OK %2d행 (%s~%s)" % (len(drows), drows[0]["Date"], drows[-1]["Date"])
        else:
            d = "일별 %s" % dinfo
        if mrows:
            ok_m += 1
            m = "월별 OK %d행" % len(mrows)
        else:
            m = "월별 %s" % minfo
        print(line)
        print("   %s" % d)
        print("   %s" % m)

        # 10월 5일 종가가 실제로 집히는지 — 카드가 쓰는 바로 그 동작
        if drows:
            hit = [r for r in drows if r["Date"].replace("-", "") <= "20161005"]
            if hit:
                print("   2016-10-05 기준점 -> %s  %s" % (hit[-1]["Date"], hit[-1]["Close"]))
            else:
                print("   !! 2016-10-05 이하 자료가 없다")
        print()

    print("=" * 56)
    print("일별 %d/%d · 월별 %d/%d" % (ok_d, len(SAMPLES), ok_m, len(SAMPLES)))
    fx, _ = fetch("usdkrw", "d")
    print("환율(usdkrw) 일별: %s" % ("OK — 2016년 값도 있다" if fx else "안 됨 -> Frankfurter 로"))
    if ok_d == len(SAMPLES):
        print("\n전부 통과. 해외도 일별로 갈 수 있다.")
        print("  -> 날짜·배당 기준이 국내와 똑같아져서 섞어도 규칙이 필요 없다")
        print("  -> 알파밴티지 하루 25회 제약에서 벗어난다 (연간 수익률 탭 전용으로 남김)")
    elif ok_d:
        print("\n일부만 된다. 되는 종목만 일별로 쓰면 카드마다 기준이 달라진다.")
        print("  -> 지금 설계(해외 월말)를 유지하는 쪽이 안전하다")
    else:
        print("\n일별이 안 된다. 지금 설계(해외 월말)로 간다.")
        if ok_m:
            print("  다만 월별은 되므로, 배당 제외 월말 시계열 용도로는 쓸 수 있다.")


if __name__ == "__main__":
    main()
