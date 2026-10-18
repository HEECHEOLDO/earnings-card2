#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 시가총액 상위 종목을 받아 data/mcap.json 에 적는다 — '시가총액' 탭(mcap.html)이 읽는다.

  python3 collect_mcap.py           받기 (네이버 금융, 키 필요 없음 · 호출 4~6회)
  python3 collect_mcap.py --show    받아둔 파일만 보기

코스피·코스닥 각각 시가총액 순으로 앞쪽 100종목을 받아, 그중 국내 실적 목록
(data/index.json)에 있는 보통주만 남긴다. ETF·우선주·스팩은 그래서 빠진다.
상위 60종목까지 적는다 (화면은 최대 TOP 50).

올해 등락률(원 테두리 색)은 연간 수익률 자료(data/returns.json)의 올해 값을 쓴다.
네이버가 막히면 아무것도 바꾸지 않고 끝낸다 (전날 파일이 그대로 남는다).
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "mcap.json")
KEEP = 60
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MARKETS = (("kospi", "KOSPI", 0), ("kosdaq", "KOSDAQ", 1))


def log(*a):
    print(*a, flush=True)


def get(url, enc="utf-8"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode(enc, "replace")


def num(s):
    s = re.sub(r"[^\d.\-]", "", str(s or ""))
    try:
        return float(s)
    except ValueError:
        return None


def from_mobile(mk):
    """네이버 증권 모바일 JSON. marketValue 는 억원."""
    out = []
    for page in (1, 2):
        j = json.loads(get("https://m.stock.naver.com/api/stocks/marketValue/%s?page=%d&pageSize=50" % (mk, page)))
        for s in j.get("stocks", []):
            cap = num(s.get("marketValue"))
            if not cap:
                continue
            out.append({"code": s.get("itemCode"), "name": s.get("stockName"),
                        "cap": cap, "day": num(s.get("fluctuationsRatio"))})
        time.sleep(0.3)
    return out


def from_html(sosok):
    """네이버 금융 시가총액 표 (PC). 칸 순서는 머리글에서 찾는다. 시가총액은 억원."""
    out = []
    for page in (1, 2):
        t = get("https://finance.naver.com/sise/sise_market_sum.naver?sosok=%d&page=%d" % (sosok, page), "euc-kr")
        heads = [re.sub(r"<[^>]+>|\s", "", h) for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
        try:
            i_cap, i_rate = heads.index("시가총액"), heads.index("등락률")
        except ValueError:
            raise RuntimeError("표 머리글을 못 찾음")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            m = re.search(r'code=(\d{6})"[^>]*>([^<]+)</a>', tr)
            if not m:
                continue
            tds = [re.sub(r"<[^>]+>|\s", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) <= max(i_cap, i_rate):
                continue
            out.append({"code": m.group(1), "name": html.unescape(m.group(2)).strip(),
                        "cap": num(tds[i_cap]), "day": num(tds[i_rate])})
        time.sleep(0.3)
    return out


def main():
    if "--show" in sys.argv:
        j = json.load(open(OUT, encoding="utf-8"))
        log("%s 기준" % j.get("asof"))
        for k, _, _ in MARKETS:
            log("\n[%s]" % k)
            for i, r in enumerate(j.get(k, [])[:50], 1):
                log("  %2d %-14s %s  %8s억  올해 %s" % (i, r["name"], r["code"], format(round(r["cap"]), ","),
                                                   "-" if r.get("ytd") is None else "%+.1f%%" % r["ytd"]))
        return

    try:
        listed = {c["code"]: c for c in json.load(open("data/index.json", encoding="utf-8")).get("companies", [])}
    except Exception:                         # noqa: BLE001
        listed = {}
        log("! data/index.json 이 없어 ETF·우선주를 이름으로만 거릅니다")
    try:
        ret = json.load(open("data/returns.json", encoding="utf-8")).get("items", {})
    except Exception:                         # noqa: BLE001
        ret = {}
    year = str(datetime.now(KST).year)

    out = {"updated": datetime.now(KST).strftime("%Y-%m-%d"), "unit": "억원", "source": ""}
    for key, mk, sosok in MARKETS:
        rows, src = None, ""
        for fn, label in ((lambda: from_mobile(mk), "네이버 증권"), (lambda: from_html(sosok), "네이버 금융")):
            try:
                rows = fn()
                if rows:
                    src = label
                    break
            except Exception as e:            # noqa: BLE001
                log("  %s %s 실패: %s" % (mk, label, e))
        if not rows:
            log("!! %s 시가총액을 받지 못했습니다. 파일을 바꾸지 않습니다." % mk)
            sys.exit(1)
        keep = []
        for r in rows:
            if not r["code"] or not r["cap"]:
                continue
            if listed and r["code"] not in listed:
                continue                      # ETF·우선주·스팩 (국내 실적 목록에 없는 것)
            if not listed and re.search(r"(우|우B|\d우|KODEX|TIGER|스팩)$|^(KODEX|TIGER|ACE|SOL|RISE|HANARO|PLUS|KIWOOM)", r["name"]):
                continue
            yv = (ret.get(r["code"], {}).get("years") or {}).get(year)
            r["ytd"] = round(float(yv), 1) if yv is not None else None
            keep.append(r)
        keep.sort(key=lambda r: -r["cap"])
        out[key] = keep[:KEEP]
        out["source"] = src
        log("%s %d종목 (%s) · 1위 %s %s억" % (mk, len(out[key]), src, keep[0]["name"], format(round(keep[0]["cap"]), ",")))

    out["asof"] = out["updated"]              # 장중에 돌면 그 시각 값, 장 마감 뒤면 그날 종가
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("저장: %s" % OUT)


if __name__ == "__main__":
    main()
