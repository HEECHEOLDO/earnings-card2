#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시세 출처 점검 (점검용, 파일은 바꾸지 않는다) — GitHub 자동 작업에서 어느 사이트가 열리는지 본다.
ETF(SPY·QQQ·SCHD) 현재가를 받을 곳을 찾으려고 만들었다 (2026-11)."""
import json
import sys
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SYMS = sys.argv[1:] or ["SPY", "QQQ", "SCHD"]

def tries(s):
    lo = s.lower()
    return [
        ("stooq", "https://stooq.com/q/l/?s=%s.us&f=sd2t2c&h&e=csv" % lo),
        ("yahoo1", "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d" % s),
        ("yahoo2", "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d" % s),
        ("nasdaq", "https://api.nasdaq.com/api/quote/%s/info?assetclass=etf" % s),
        ("cnbc", "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=%s"
                 "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json" % s),
        ("google", "https://www.google.com/finance/quote/%s:NYSEARCA" % s),
        ("stockanalysis", "https://stockanalysis.com/etf/%s/" % lo),
        ("finviz", "https://finviz.com/quote.ashx?t=%s" % s),
        ("marketwatch", "https://www.marketwatch.com/investing/fund/%s" % lo),
    ]

for s in SYMS:
    print("\n==", s)
    for name, url in tries(s):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                                       "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=20) as r:
                b = r.read(400000).decode("utf-8", "replace")
                code = r.status
        except Exception as e:                       # noqa: BLE001
            print("  %-14s 실패 %s" % (name, str(e)[:120])); continue
        snip = " ".join(b[:300].split())
        hit = ""
        for key in ('"regularMarketPrice":', '"last":', 'data-last-price="', '"lastSalePrice":', 'YMtoe', '"p":'):
            i = b.find(key)
            if i >= 0:
                hit = b[i:i + 60].replace("\n", " "); break
        print("  %-14s %s  %d바이트  %s | %s" % (name, code, len(b), hit, snip[:160]))
