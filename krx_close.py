#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 '정규장(KRX) 종가' 바로잡기  (2026-11)

왜: 2025년 3월 넥스트레이드(NXT)가 열린 뒤 네이버 일별 시세의 종가는 저녁 8시 애프터마켓까지 포함한
    '마지막 체결가'다. 사람들이 아는 종가(증권사 앱·뉴스·전일 대비 기준)는 오후 3시 30분 KRX 정규장 종가.
    예) 실리콘투 2026-11-12: 네이버 일별 24,550 · KRX 종가 24,900 / 삼성전자 206,500 · 208,000

  python3 krx_close.py            빠진 날의 KRX 종가 받기 (공공데이터포털, 2025-03-04 ~ 어제) → data/krx/YYYYMMDD.json
  python3 krx_close.py --apply    받아 둔 값 + 오늘 네이버 정규장 시세로 data/chart/kr · data/anchor.json 바로 고치기
  python3 krx_close.py --show 257720   한 종목 비교만

다른 수집기는 krx_fix(code, rows) 로 네이버 일별 [(YYYYMMDD, 값)] 을 고친다.
네이버 값은 수정주가라 그 뒤 무상증자·분할이 있으면 KRX 원래 종가와 배수만큼 다르다 → 구간별 배수를 찾아 맞춘다.
키: 환경변수 DATA_GO_KEY 또는 datago_key.txt (받기에만 필요. 고치기는 키 없이 된다)
"""
import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DIR = os.path.join("data", "krx")
NONE = os.path.join(DIR, "_none.json")        # 장이 안 열린 날 (다시 묻지 않게)
START = date(2025, 3, 4)                      # 넥스트레이드 첫날 — 그 전은 네이버 값이 곧 KRX 종가
URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
POLL = "https://polling.finance.naver.com/api/realtime/domestic/stock/%s"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 받아 둔 값

_KRX = [None]


def load():
    """{코드: {YYYYMMDD: KRX 종가}} — 받아 둔 파일 + 오늘 정규장 시세(있으면)"""
    if _KRX[0] is None:
        m = {}
        for f in sorted(glob.glob(os.path.join(DIR, "2*.json"))):
            d = os.path.basename(f)[:8]
            try:
                c = json.load(open(f, encoding="utf-8")).get("c") or {}
            except Exception:                 # noqa: BLE001
                continue
            for k, v in c.items():
                m.setdefault(k, {})[d] = v
        _KRX[0] = m
    return _KRX[0]


def add_today(codes):
    """네이버 실시간 시세의 정규장 종가(closePrice — 애프터마켓은 overMarketPriceInfo 로 따로 온다)를 더한다.
    전일 종가(closePrice − 전일 대비)도 같이 — 공공데이터포털은 하루 늦게 올라오니 어제 값은 이걸로 채운다."""
    m = load()
    n = 0
    codes = list(codes)
    for i in range(0, len(codes), 60):
        part = codes[i:i + 60]
        try:
            req = urllib.request.Request(POLL % ",".join(part), headers={"User-Agent": UA, "Accept": "application/json"})
            j = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace"))
        except Exception as e:                # noqa: BLE001
            log("  정규장 시세 못 받음 (%s) — 건너뜀" % str(e)[:80])
            time.sleep(1)
            continue
        for x in j.get("datas") or []:
            try:
                code = x["itemCode"]
                c = int(str(x["closePriceRaw"] if x.get("closePriceRaw") else x["closePrice"]).replace(",", ""))
                ch = int(str(x.get("compareToPreviousClosePriceRaw") or x.get("compareToPreviousClosePrice") or "0").replace(",", ""))
                d = str(x.get("localTradedAt") or "")[:10].replace("-", "")
            except Exception:                 # noqa: BLE001
                continue
            if c > 0 and len(d) == 8:
                mm = m.setdefault(code, {})
                mm[d] = c
                mm["prev:" + d] = c - ch     # d 바로 전 거래일의 KRX 종가 (그 날짜는 고칠 때 정한다)
                n += 1
        time.sleep(0.25)
    log("  오늘 정규장 시세 %d종목" % n)
    return n


def krx_fix(code, rows):
    """네이버 일별 [(YYYYMMDD, 값)] → 넥스트레이드 이후 날짜는 KRX 종가로 (수정주가 배수 반영)."""
    m = load().get(code)
    if not m or not rows:
        return rows
    s0 = START.strftime("%Y%m%d")
    km = dict(m)
    # 전일 종가: 오늘 시세의 '전 거래일' = rows 에서 그 날 바로 앞 날짜
    for k in [k for k in km if k.startswith("prev:")]:
        d = k[5:]
        before = [r[0] for r in rows if r[0] < d]
        if before and before[-1] not in km:
            km[before[-1]] = km[k]
    idx = [i for i, r in enumerate(rows) if r[0] >= s0 and r[0] in km and r[1] > 0]
    if not idx:
        return rows
    out = list(rows)
    f = 1.0                                   # 지금 구간의 배수 (KRX 원래 종가 ÷ 네이버 수정주가)
    for p in range(len(idx) - 1, -1, -1):
        i = idx[p]
        r = km[rows[i][0]] / rows[i][1]
        if abs(r / f - 1) > 0.015:
            nxt = sorted(km[rows[j][0]] / rows[j][1] for j in idx[max(0, p - 4):p + 1])
            med = nxt[len(nxt) // 2]
            if abs(med / f - 1) > 0.015 and len(nxt) >= 3:
                f = med                       # 무상증자·분할 뒤라 배수가 바뀐 구간
        v = km[rows[i][0]] / f
        if abs(v / rows[i][1] - 1) < 0.15:    # 애프터마켓 차이는 보통 몇 % — 그 이상이면 다른 문제라 두고 본다
            out[i] = (rows[i][0], round(v) if f == 1.0 else round(v, 2))
    return out


# ---------------------------------------------------------------- 받기 (공공데이터포털)

def get_key():
    k = os.environ.get("DATA_GO_KEY", "").strip()
    if not k and os.path.exists("datago_key.txt"):
        k = open("datago_key.txt", encoding="utf-8").read().strip()
    if not k:
        sys.exit("!! 공공데이터포털 키가 없습니다 (DATA_GO_KEY 또는 datago_key.txt)")
    return urllib.parse.unquote(k)


def day_close(key, d):
    out, page = {}, 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": key, "resultType": "json", "basDt": d.strftime("%Y%m%d"),
                                    "numOfRows": 1000, "pageNo": page})
        j = None
        for wait in (5, 15, 30, 60, None):
            try:
                j = json.loads(urllib.request.urlopen(URL + "?" + q, timeout=40).read().decode("utf-8", "replace"))
                break
            except Exception as e:            # noqa: BLE001
                if wait is None:
                    raise RuntimeError("공공데이터포털 응답 이상: %r" % e)
                time.sleep(wait)
        body = j.get("response", {}).get("body", {})
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        for r in items:
            try:
                c = int(float(r.get("clpr") or 0))
            except Exception:                 # noqa: BLE001
                c = 0
            if c > 0 and r.get("srtnCd"):
                out[r["srtnCd"]] = c
        total = int(body.get("totalCount") or 0)
        if not items or len(out) >= total:
            return out
        page += 1
        time.sleep(0.3)


def fetch():
    key = get_key()
    os.makedirs(DIR, exist_ok=True)
    try:
        none = set(json.load(open(NONE)))
    except Exception:                         # noqa: BLE001
        none = set()
    today = datetime.now(KST).date()
    d, got, calls = START, 0, 0
    while d < today:
        ds = d.strftime("%Y%m%d")
        if d.weekday() < 5 and ds not in none and not os.path.exists(os.path.join(DIR, ds + ".json")):
            try:
                c = day_close(key, d)
            except RuntimeError as e:
                log("::warning::%s 못 받음 — 다음에 다시 (%s)" % (ds, e))
                break
            calls += 1
            if c:
                with open(os.path.join(DIR, ds + ".json"), "w", encoding="utf-8") as f:
                    json.dump({"c": c}, f, separators=(",", ":"), sort_keys=True)
                got += 1
            elif (today - d).days > 5:        # 최근 며칠은 아직 안 올라온 것일 수 있다
                none.add(ds)
            if calls % 20 == 0:
                log("  %s 까지 · 새로 %d일" % (ds, got))
            time.sleep(0.2)
        d += timedelta(days=1)
    with open(NONE, "w") as f:
        json.dump(sorted(none), f)
    log("KRX 종가: 새로 받은 날 %d · 모두 %d일" % (got, len(glob.glob(os.path.join(DIR, "2*.json")))))


# ---------------------------------------------------------------- 이미 만든 파일 고치기

def apply():
    codes = [os.path.basename(f)[:-5] for f in glob.glob(os.path.join("data", "chart", "kr", "*.json"))]
    add_today(codes)
    n_chart = 0
    for code in codes:
        p = os.path.join("data", "chart", "kr", code + ".json")
        j = json.load(open(p, encoding="utf-8"))
        rows = sorted({str(a): b for a, b in j["w"] + j["d"]}.items())
        fixed = dict(krx_fix(code, rows))
        if fixed != dict(rows):
            num = lambda v: int(v) if float(v).is_integer() else v       # noqa: E731
            j["d"] = [[a, num(fixed[str(a)])] for a, _ in j["d"]]
            j["w"] = [[a, num(fixed[str(a)])] for a, _ in j["w"]]
            with open(p, "w", encoding="utf-8") as f:
                json.dump(j, f, separators=(",", ":"))
            n_chart += 1
    pa = os.path.join("data", "anchor.json")
    a = json.load(open(pa, encoding="utf-8"))
    n_anc = 0
    for code, it in (a.get("kr", {}).get("items") or {}).items():
        pts = {k: v for k, v in it.items() if isinstance(v, dict) and v.get("d")}
        if not pts:
            continue
        cp = os.path.join("data", "chart", "kr", code + ".json")
        ctx = {}
        if os.path.exists(cp):                # 배수(수정주가) 판단에 앞뒤 값이 필요해 차트 값과 같이 넣는다
            cj = json.load(open(cp, encoding="utf-8"))
            ctx = {str(x): y for x, y in cj["w"] + cj["d"]}
        for v in pts.values():
            ctx[v["d"].replace("-", "")] = ctx.get(v["d"].replace("-", ""), v["v"])
        fixed = dict(krx_fix(code, sorted(ctx.items())))
        for v in pts.values():
            nv = fixed.get(v["d"].replace("-", ""))
            if nv and nv != v["v"]:
                v["v"] = float(nv)
                n_anc += 1
    with open(pa, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, separators=(",", ":"))
    log("고침: 차트 %d종목 · 기준점 %d곳" % (n_chart, n_anc))


def show(code):
    add_today([code])
    p = os.path.join("data", "chart", "kr", code + ".json")
    j = json.load(open(p, encoding="utf-8"))
    rows = [(str(a), b) for a, b in j["d"]]
    for (d, v), (_, w) in list(zip(rows, krx_fix(code, rows)))[-12:]:
        log(d, v, "→", w, "" if v == w else "*")


if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply()
    elif "--show" in sys.argv:
        show(sys.argv[-1])
    else:
        fetch()
