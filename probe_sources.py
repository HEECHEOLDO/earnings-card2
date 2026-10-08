#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stooq 가 왜 HTML 을 주는지, 환율은 어디서 받을지 한 번에 본다.

  python3 probe_sources.py

왜 필요한가
-----------
probe_stooq.py 가 7개 전부 '없음: <!DOCTYPE html>' 로 나왔다. CSV 자리에
웹페이지가 왔다는 뜻이고, 이유는 셋 중 하나다.

  (가) 봇 차단 / 한도 초과 안내 페이지
  (나) 주소나 변수 이름이 바뀜
  (다) 쿠키·동의 페이지를 거쳐야 함

셋을 가르려면 응답 코드·최종 주소·내용 앞부분을 봐야 한다. 그래서 주소
모양을 바꿔 가며 부르고, 브라우저인 척도 해 본다.

이건 '그때 샀다면' 해외 탭만의 문제가 아니다. collect_prices.py 가 해외
주가를 받을 때 Stooq 를 1순위로 쓰므로, 여기가 막혀 있으면 524종목이
전부 알파밴티지(하루 25회)로 몰린다. monthly_us.json 이 안 쌓이는
진짜 이유일 수 있다.
"""

import json
import sys
import time
import urllib.error
import urllib.request

UA_BOT = "Mozilla/5.0 (fincard probe)"
UA_WEB = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def get(url, ua, extra=None):
    h = {"User-Agent": ua}
    if extra:
        h.update(extra)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(4000).decode("utf-8", "replace")
            return r.status, r.headers.get("Content-Type", ""), r.geturl(), body, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(2000).decode("utf-8", "replace")
        except Exception:                     # noqa: BLE001
            body = ""
        return e.code, e.headers.get("Content-Type", ""), url, body, None
    except Exception as e:                    # noqa: BLE001
        return None, "", url, "", type(e).__name__


def kind(body):
    t = body.lstrip()[:400].lower()
    if t.startswith("date,"):
        return "CSV (정상)"
    if "exceeded" in t or "limit" in t:
        return "한도 초과 안내"
    if "captcha" in t or "robot" in t or "cloudflare" in t:
        return "봇 차단"
    if t.startswith("<!doctype") or t.startswith("<html"):
        return "HTML 페이지"
    if not t:
        return "빈 응답"
    return "알 수 없음"


def line(body, n=220):
    s = " ".join(body.split())[:n]
    return s or "(빈 응답)"


def section(title):
    print("\n" + "─" * 60)
    print(title)
    print("─" * 60)


def main():
    section("1. Stooq — 주소 모양을 바꿔 가며")
    cases = [
        ("지금 쓰는 그대로 (월별)", "https://stooq.com/q/d/l/?s=aapl.us&i=m", UA_BOT, None),
        ("같은 주소 · 브라우저 UA", "https://stooq.com/q/d/l/?s=aapl.us&i=m", UA_WEB, None),
        ("일별 · 날짜 없이", "https://stooq.com/q/d/l/?s=aapl.us&i=d", UA_WEB, None),
        ("일별 · 날짜 지정", "https://stooq.com/q/d/l/?s=aapl.us&i=d&d1=20160901&d2=20161031",
         UA_WEB, None),
        ("폴란드 쪽 주소", "https://stooq.pl/q/d/l/?s=aapl.us&i=m", UA_WEB, None),
        ("Accept 헤더 추가", "https://stooq.com/q/d/l/?s=aapl.us&i=m", UA_WEB,
         {"Accept": "text/csv,*/*", "Referer": "https://stooq.com/"}),
        ("종목 페이지 자체", "https://stooq.com/q/?s=aapl.us", UA_WEB, None),
    ]
    csv_ok = False
    for label, url, ua, extra in cases:
        st, ct, final, body, err = get(url, ua, extra)
        k = kind(body) if body else ("연결 실패: " + (err or "?"))
        if k.startswith("CSV"):
            csv_ok = True
        print("\n  %s" % label)
        print("    %s" % url)
        print("    HTTP %s · %s · %s" % (st, (ct or "?").split(";")[0], k))
        if final != url:
            print("    최종 주소: %s" % final)
        print("    앞부분: %s" % line(body))
        time.sleep(0.6)

    section("2. 환율 — 2016-10-05 달러/원")
    fx = [
        ("Frankfurter (현재 주소)",
         "https://api.frankfurter.dev/v1/2016-10-05?base=USD&symbols=KRW"),
        ("Frankfurter (옛 주소)",
         "https://api.frankfurter.app/2016-10-05?from=USD&to=KRW"),
        ("Frankfurter 구간 조회 (한 번에 여러 해)",
         "https://api.frankfurter.dev/v1/2016-10-01..2016-10-10?base=USD&symbols=KRW"),
    ]
    fx_ok = None
    for label, url in fx:
        st, ct, final, body, err = get(url, UA_WEB)
        ok = False
        rate = ""
        if body:
            try:
                j = json.loads(body)
                r = j.get("rates") or {}
                if isinstance(r, dict) and r:
                    first = r if "KRW" in r else list(r.values())[0]
                    rate = str(first.get("KRW") if isinstance(first, dict) else first)
                    ok = True
            except Exception:                 # noqa: BLE001
                pass
        if ok and fx_ok is None:
            fx_ok = label
        print("\n  %s" % label)
        print("    HTTP %s · %s" % (st, "OK  1달러 = %s원" % rate if ok
                                    else ("연결 실패: " + (err or "?") if err else "형식 다름")))
        if not ok:
            print("    앞부분: %s" % line(body, 160))
        time.sleep(0.6)

    section("정리")
    if csv_ok:
        print("  Stooq: 되는 주소가 있다 → collect_prices.py 를 그 모양으로 고치면 된다.")
    else:
        print("  Stooq: 어떤 주소로도 CSV 가 안 온다.")
        print("    → collect_prices.py 에서 Stooq 를 떼고 알파밴티지만 쓰는 게 낫다.")
        print("      (지금은 종목마다 Stooq 를 먼저 부르느라 시간만 버리고 있다)")
        print("    → 해외 기준은 '알파밴티지 월말 · 배당 재투자 포함' 하나로 통일된다.")
    if fx_ok:
        print("  환율: %s 로 받으면 된다." % fx_ok)
    else:
        print("  환율: Frankfurter 도 안 된다 → 한국은행 ECOS(키 발급 필요)로 간다.")


if __name__ == "__main__":
    main()
