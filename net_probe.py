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
    if s.isdigit() and len(s) == 6:              # 국내 — 정규장(KRX) 종가와 통합(NXT 포함) 종가가 어느 쪽인지 보기
        return [
            ("siseJson", "https://api.finance.naver.com/siseJson.naver?symbol=%s&requestType=1&startTime=20261105&endTime=20261113&timeframe=day" % s),
            ("sise_day", "https://finance.naver.com/item/sise_day.naver?code=%s&page=1" % s),
            ("m-price", "https://m.stock.naver.com/api/stock/%s/price?pageSize=6&page=1" % s),
            ("m-integ", "https://m.stock.naver.com/api/stock/%s/integration" % s),
            ("m-basic", "https://m.stock.naver.com/api/stock/%s/basic" % s),
            ("chart-day", "https://api.stock.naver.com/chart/domestic/item/%s/day?startDateTime=202611050000&endDateTime=202611132359" % s),
            ("chart-day-K", "https://api.stock.naver.com/chart/domestic/item/%s/day?startDateTime=202611050000&endDateTime=202611132359&marketType=KRX" % s),
            ("fchart", "https://fchart.stock.naver.com/sise.nhn?symbol=%s&timeframe=day&count=6&requestType=0" % s),
            ("fchart-krx", "https://fchart.stock.naver.com/siseJson.nhn?symbol=%s&requestType=1&startTime=20261105&endTime=20261113&timeframe=day&marketType=KRX" % s),
            ("daum", "https://finance.daum.net/api/quote/A%s/days?symbolCode=A%s&page=1&perPage=6&pagination=true" % (s, s)),
        ]
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
        # 일별 과거 시세 후보 (주가 추이 카드용, 2026-11)
        ("cnbc-1y", "https://ts-api.cnbc.com/harmony/app/charts/1Y.json?symbol=%s" % s),
        ("cnbc-5y", "https://ts-api.cnbc.com/harmony/app/charts/5Y.json?symbol=%s" % s),
        ("nasdaq-hist", "https://api.nasdaq.com/api/quote/%s/historical?assetclass=stocks&fromdate=2016-01-01&limit=9999" % s),
        ("naver-w-O", "https://api.stock.naver.com/chart/foreign/item/%s.O/day?startDateTime=202510010000&endDateTime=202611110000" % s),
        ("naver-w-N", "https://api.stock.naver.com/chart/foreign/item/%s.N/day?startDateTime=202510010000&endDateTime=202611110000" % s),
        ("naver-w-K", "https://api.stock.naver.com/chart/foreign/item/%s.K/day?startDateTime=202510010000&endDateTime=202611110000" % s),
        ("naver-w", "https://api.stock.naver.com/chart/foreign/item/%s/day?startDateTime=202510010000&endDateTime=202611110000" % s),
        ("naver-basic-O", "https://api.stock.naver.com/stock/%s.O/basic" % s),
        ("naver-basic", "https://api.stock.naver.com/stock/%s/basic" % s),
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
        if s.isdigit():
            import re
            t = re.sub(r"<[^>]+>", " ", b) if "<html" in b[:2000].lower() or "<table" in b else b
            t = " ".join(t.split())
            i = t.find("2026.11.1") if "2026.11.1" in t else 0
            print("  %-14s %s  %d바이트 | %s" % (name, code, len(b), t[i:i + 900] if i else t[:900]))
            continue
        snip = " ".join(b[:300].split())
        hit = ""
        for key in ('"regularMarketPrice":', '"last":', 'data-last-price="', '"lastSalePrice":', 'YMtoe', '"p":',
                    '"closePrice"', '"close"', '"localTradedAt"', '"reutersCode"'):
            i = b.find(key)
            if i >= 0:
                hit = b[i:i + 60].replace("\n", " "); break
        print("  %-14s %s  %d바이트  %s | %s" % (name, code, len(b), hit, snip[:160]))
