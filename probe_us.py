#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 주가를 어디서 받을 수 있는지 확인한다.

  python3 probe_us.py

왜 필요한가
-----------
Stooq 가 자바스크립트 검증으로 막혀 이제 알파밴티지만 남았는데, 하루 25회
제한이라 548종목을 한 바퀴 도는 데 21일이 걸린다. 그 사이 '그때 샀다면'
해외 탭을 만들 수 없다.

collect_prices.py 안에 야후 경로가 이미 있지만 USE_YAHOO = False 로 꺼져
있다('자주 막힌다'는 이유). 지금도 막히는지 본다. 열려 있으면 한 번에
548종목을 받을 수 있고, 조정종가라 배당 기준도 알파밴티지와 같아
섞어 써도 된다.

야후는 쿠키와 crumb 을 요구하는 때가 있어 네 가지 방법을 다 해 본다.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
SYMS = [("AAPL", "애플 — 대형주"),
        ("BRK-B", "버크셔 B — 기호에 하이픈"),
        ("SPY", "SPY — 대형 ETF"),
        ("AAAD", "AAAD — 소형 ETF (커버리지 바닥)")]


def fetch(url, jar=None, timeout=20):
    import http.cookiejar
    h = [("User-Agent", UA), ("Accept", "application/json,text/plain,*/*")]
    if jar is None:
        op = urllib.request.build_opener()
    else:
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = h
    try:
        with op.open(url, timeout=timeout) as r:
            return r.status, r.read(400000).decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(600).decode("utf-8", "replace")
        except Exception:                     # noqa: BLE001
            body = ""
        return e.code, body, None
    except Exception as e:                    # noqa: BLE001
        return None, "", type(e).__name__


def months(body):
    """차트 응답에서 '몇 개월치인지'와 기간을 뽑는다."""
    try:
        j = json.loads(body)
    except Exception:                         # noqa: BLE001
        return None, "JSON 아님"
    ch = j.get("chart") or {}
    if ch.get("error"):
        return None, str(ch["error"])[:80]
    res = ch.get("result")
    if not res:
        return None, "result 없음"
    r = res[0]
    ts = r.get("timestamp") or []
    ind = r.get("indicators") or {}
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    if not ts:
        return None, "날짜 없음"
    import datetime
    a = datetime.datetime.utcfromtimestamp(ts[0]).strftime("%Y-%m")
    b = datetime.datetime.utcfromtimestamp(ts[-1]).strftime("%Y-%m")
    return (len(ts), a, b, "조정종가 있음" if adj else "조정종가 없음(종가만)"), None


def try_plain(sym, host):
    u = ("https://%s/v8/finance/chart/%s?range=25y&interval=1mo" % (host, sym))
    st, body, err = fetch(u)
    return st, body, err, u


def try_crumb(sym):
    """쿠키를 받고 crumb 을 얻어 붙이는 방법."""
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    fetch("https://fc.yahoo.com/", jar)
    st, crumb, err = fetch("https://query2.finance.yahoo.com/v1/test/getcrumb", jar)
    if st != 200 or not crumb or len(crumb) > 40:
        return None, "crumb 못 받음 (HTTP %s)" % st, jar, None
    u = ("https://query2.finance.yahoo.com/v8/finance/chart/%s"
         "?range=25y&interval=1mo&crumb=%s" % (sym, urllib.parse.quote(crumb)))
    st2, body, err2 = fetch(u, jar)
    return st2, body, jar, crumb


def main():
    ok_any = False
    print("야후 금융 — 월별 조정종가 25년치\n")

    for sym, label in SYMS:
        print("  %-7s %s" % (sym, label))
        for name, host in (("query2", "query2.finance.yahoo.com"),
                           ("query1", "query1.finance.yahoo.com")):
            st, body, err, u = try_plain(sym, host)
            if err:
                print("    %-8s 연결 실패: %s" % (name, err))
                continue
            info, why = months(body)
            if info:
                ok_any = True
                print("    %-8s HTTP %s · %d개월치 (%s ~ %s) · %s"
                      % (name, st, info[0], info[1], info[2], info[3]))
            else:
                print("    %-8s HTTP %s · %s" % (name, st, why))
            time.sleep(0.5)
        print()

    if not ok_any:
        print("  쿠키·crumb 을 붙여 다시 해 봅니다")
        st, body, jar, crumb = try_crumb("AAPL")
        if st is None:
            print("    %s" % body)
        else:
            info, why = months(body)
            if info:
                ok_any = True
                print("    HTTP %s · %d개월치 (%s ~ %s) · %s"
                      % (st, info[0], info[1], info[2], info[3]))
            else:
                print("    HTTP %s · %s" % (st, why))

    print("\n" + "=" * 58)
    if ok_any:
        print("야후가 열려 있습니다.")
        print("  -> collect_prices.py 의 USE_YAHOO 를 켜고 해외 1순위로 두면")
        print("     548종목을 한 번에 받습니다. 21일 대기가 사라집니다.")
        print("  -> 조정종가라 배당 기준이 알파밴티지와 같아 섞어 써도 됩니다.")
    else:
        print("야후도 막혀 있습니다.")
        print("  -> 알파밴티지 하루 25회로 가야 합니다.")
        print("  -> 해외 종목을 인기 150개로 추리면 6일이면 한 바퀴입니다.")
        print("     (연간 수익률 탭은 지금처럼 전체를 쓰고, 카드용만 추립니다)")


if __name__ == "__main__":
    main()
