#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 주가 추이 카드(price.html)용 일별·주별 종가 → data/chart/us/{티커}.json  (2026-11)

  python3 collect_chart_us.py              전 종목 (data/monthly_us.json 에 있는 미국 종목)
  python3 collect_chart_us.py AAPL TSLA    몇 종목만
  python3 collect_chart_us.py --probe AAPL 어느 출처가 열리는지만 보기 (파일 안 씀)

파일 모양 (국내 data/chart/kr 과 같다):
  {"u":"USD", "d":[[YYYYMMDD,종가]...] 최근 약 400일 일별, "w":[[YYYYMMDD,종가]...] 약 11년 주별(주 마지막 거래일)}
종가는 분할만 반영한 종가(배당 미반영) — 국내 수정주가와 같은 기준.

출처는 앞에서부터 되는 것을 쓴다 (나스닥·야후가 GitHub 에서 자주 막혀서 여러 곳을 둔다):
  1) CNBC 차트 (1년 일별 · 5년 주별)  2) 야후 (일별·주별)  3) 나스닥 과거 시세
다 막히면: 이미 있는 파일에 CNBC 오늘 시세 한 줄을 붙인다 (일별이 하루씩 쌓인다).
(CNBC '5Y' 는 실제로 약 10년 치 주별을 준다. 월말 종가는 배당 반영 기준이라 섞지 않는다)
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
OUT_DIR = os.path.join("data", "chart", "us")
IN_MON = os.path.join("data", "monthly_us.json")
DAYS = 400
YEARS = 11
PAUSE = 0.35


def log(*a):
    print(*a)
    sys.stdout.flush()


def get(url, tries=2, accept="application/json"):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept,
                                                       "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:                         # noqa: BLE001
            if i < tries - 1:
                time.sleep(1.5)
    return None


def n8(s):
    s = "".join(ch for ch in str(s) if ch.isdigit())
    return int(s[:8]) if len(s) >= 8 else None


# ---------------------------------------------------------------- 출처

def cnbc_bars(sym, rng):
    """CNBC 차트 — rng: 1Y(일별) · 5Y(주별). [(YYYYMMDD, 종가)]"""
    url = "https://ts-api.cnbc.com/harmony/app/charts/%s.json?symbol=%s" % (rng, urllib.parse.quote(sym.replace("-", ".")))
    t = get(url)
    if not t:
        return None
    try:
        j = json.loads(t)
        bars = ((j.get("barData") or {}).get("priceBars")) or []
        out = []
        for b in bars:
            d = n8(b.get("tradeTime") or "")
            c = float(str(b.get("close") or "0").replace(",", ""))
            if d and c > 0:
                if rng != "1Y":                   # 주별 막대는 주가 시작하는 일요일 날짜로 온다 → 그 주 금요일로
                    dt = date(d // 10000, d // 100 % 100, d % 100)
                    if dt.weekday() == 6:
                        dt = min(dt + timedelta(days=5), date.today())
                        d = int(dt.strftime("%Y%m%d"))
                out.append((d, c))
        out.sort()
        return out or None
    except Exception:                             # noqa: BLE001
        return None


def yahoo_bars(sym, rng, itv):
    for host in ("query1", "query2"):
        url = ("https://%s.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s&events=split"
               % (host, urllib.parse.quote(sym.replace(".", "-")), rng, itv))
        t = get(url, tries=1)
        if not t:
            continue
        try:
            r = (json.loads(t).get("chart") or {}).get("result") or []
            if not r:
                continue
            r = r[0]
            off = int((r.get("meta") or {}).get("gmtoffset") or 0)
            closes = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            out = []
            for ts, c in zip(r.get("timestamp") or [], closes):
                if c:
                    out.append((int(datetime.fromtimestamp(ts + off, timezone.utc).strftime("%Y%m%d")), float(c)))
            out.sort()
            if out:
                return out
        except Exception:                         # noqa: BLE001
            continue
    return None


def nasdaq_bars(sym, start):
    for cls in ("stocks", "etf"):
        url = ("https://api.nasdaq.com/api/quote/%s/historical?assetclass=%s&fromdate=%s&limit=9999"
               % (urllib.parse.quote(sym.replace("-", ".")), cls, start))
        t = get(url, tries=1)
        if not t:
            continue
        try:
            rows = ((((json.loads(t).get("data") or {}).get("tradesTable")) or {}).get("rows")) or []
            out = []
            for r in rows:
                m, d, y = (r.get("date") or "").split("/")
                c = float(str(r.get("close") or "0").replace("$", "").replace(",", ""))
                if c > 0:
                    out.append((int(y + m + d), c))
            out.sort()
            if out:
                return out
        except Exception:                         # noqa: BLE001
            continue
    return None


def cnbc_quotes(syms):
    """오늘(최근) 시세 {티커: (YYYYMMDD, 종가)} — 40종목씩."""
    out = {}
    syms = list(syms)
    for i in range(0, len(syms), 40):
        part = syms[i:i + 40]
        url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=%s"
               "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=0&output=json"   # 정규장 종가만 (시간외 가격 X)
               % urllib.parse.quote("|".join(s.replace("-", ".") for s in part), safe="|."))
        t = get(url) or (time.sleep(2) or get(url))     # 40종목 묶음이 통째로 빠지는 일이 있다 (2026-11-24 LEN~MKC) — 한 번 더
        if not t:
            log("  시세 묶음 실패: %s…" % part[0])
            continue
        try:
            q = ((json.loads(t).get("FormattedQuoteResult") or {}).get("FormattedQuote")) or []
            if isinstance(q, dict):
                q = [q]
            for x in q:
                sym = str(x.get("symbol") or "").replace(".", "-").upper()
                p = float(str(x.get("last") or "").replace(",", ""))
                lt = str(x.get("last_time") or "")
                d = n8(lt[:10])
                try:
                    ch = float(str(x.get("change") or "").replace(",", "").replace("+", ""))
                except ValueError:
                    ch = None
                hm = int(lt[11:13]) * 60 + int(lt[14:16]) if len(lt) >= 16 and lt[11:13].isdigit() else 0
                if sym and p > 0 and d:
                    out[sym] = (d, p, ch, hm)          # 날짜, 정규장 종가, 전일 대비, 시세 시각(뉴욕 분)
        except Exception:                         # noqa: BLE001
            continue
        time.sleep(PAUSE)
    return out


# ---------------------------------------------------------------- 만들기

def weekly(rows):
    out, key = [], None
    for d, v in rows:
        k = date(d // 10000, d // 100 % 100, d % 100).isocalendar()[:2]
        if k == key:
            out[-1] = [d, v]
        else:
            out.append([d, v])
            key = k
    return out


def rnd(v):
    return round(v, 4) if v < 10 else round(v, 2)


def monthly_rows(mon, sym):
    it = (mon or {}).get(sym)
    if not it or not it.get("v"):
        return []
    y0, m0 = int(it["s"][:4]), int(it["s"][5:7]) - 1
    out = []
    for i, v in enumerate(it["v"]):
        if not v:
            continue
        mm = m0 + i
        y, mo = y0 + mm // 12, mm % 12 + 1
        last = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))
        while last.weekday() >= 5:
            last -= timedelta(days=1)
        out.append((int(last.strftime("%Y%m%d")), float(v)))
    return out


def build(sym, mon, today, probe=False):
    """돌려주는 값: (파일 dict 또는 None, 출처 이름)"""
    d0 = int((today - timedelta(days=DAYS)).strftime("%Y%m%d"))
    w0 = int((today - timedelta(days=int(YEARS * 365.25))).strftime("%Y%m%d"))
    daily = wk = None
    src = []
    daily = cnbc_bars(sym, "1Y")
    if daily:
        src.append("cnbc-1y")
        wk = cnbc_bars(sym, "5Y")
        if wk:
            src.append("cnbc-5y")
    time.sleep(PAUSE)
    if not daily:
        daily = yahoo_bars(sym, "2y", "1d")
        if daily:
            src.append("yahoo-1d")
            wk = yahoo_bars(sym, "10y", "1wk")
            if wk:
                src.append("yahoo-1wk")
    if not daily:
        rows = nasdaq_bars(sym, (today - timedelta(days=int(YEARS * 365.25))).strftime("%Y-%m-%d"))
        if rows:
            src.append("nasdaq")
            daily, wk = rows, weekly(rows)
    if probe:
        return {"daily": len(daily or []), "weekly": len(wk or []),
                "first_d": (daily or [[0]])[0][0], "last_d": (daily or [[0]])[-1][0]}, "+".join(src)
    if not daily:
        return None, ""
    d = [[a, rnd(b)] for a, b in daily if a >= d0]
    # 일별이 있는 기간은 일별로 주를 만든다 (CNBC 이번 주 막대는 값이 늦게 바뀌는 일이 있다)
    wk = weekly(sorted(set(tuple(x) for x in (wk or []) if x[0] < daily[0][0]) | set(daily)))
    # 월말 종가(알파밴티지, 배당까지 고친 값)는 기준이 달라 이어 붙이면 계단이 생긴다 (알트리아 33 → 62).
    # CNBC 5년 차트가 실제로는 약 10년 치 주별을 주므로 그것만 쓴다
    w = [[a, rnd(b)] for a, b in wk if a >= w0]
    mm = mon_map(mon, sym)
    # 다른 종목 자료가 섞였는지: 최근 6개월 월말 종가(알파밴티지)와 일별 마지막 날 값이 2배 넘게 다르면 버린다
    # (2026-11 켄뷰 KVUE — 상장 폐지 뒤 CNBC 가 276~376 달러 자료를 줬다 · 실제 주가는 19 달러 안팎)
    dm = {}
    for a, b in d:
        dm[a // 100] = b
    ks = [k for k in sorted(mm)[-6:] if k in dm and mm[k]]
    rs = [dm[k] / mm[k] for k in ks[:-1]] if len(ks) > 2 else []   # 마지막 달은 월 중간 값일 수 있어 뺀다
    # 배율이 달마다 고르면(분할 반영 차이, 아이셰어즈 SOXX 3배) 같은 종목이다 — 달마다 들쭉날쭉할 때만 버린다
    if rs and sum(1 for r in rs if not 0.5 <= r <= 2) * 2 > len(rs) and max(rs) / min(rs) > 1.05:
        log("  %-6s 일별 자료가 월말 종가와 2배 넘게 달라 버림 (다른 종목 자료로 보임)" % sym)
        return None, ""
    d, w = fix_jumps(d, w, mm)
    out = {"u": "USD", "d": d, "w": w, "src": "+".join(src)}
    r = long_rank(sym, today, daily if "nasdaq" in src else None, w)
    if r:
        out["r"] = r
    return out, "+".join(src)


def long_rank(sym, today, rows, w):
    """3·5·10년 하루 등락률 상위 5일 (주가 탭 '역대 상승폭·하락폭 순위'). 나스닥 10년 일별 종가를 받아
    주별 파일과 같은 날 값이 98% 넘게 1% 안에서 맞을 때만 쓴다 (분할 반영 기준이 다르면 틀린 날이 순위에 오른다).
    못 받으면 있던 파일의 r 을 30일까지 그대로 둔다."""
    import daily_rank
    try:
        if not rows:
            time.sleep(PAUSE)
            rows = nasdaq_bars(sym, (today - timedelta(days=int(10.2 * 365.25))).strftime("%Y-%m-%d"))
        if rows:
            wm = {a: b for a, b in w}
            m = [abs(b / wm[a] - 1) < 0.01 for a, b in rows if a in wm]
            if len(m) >= 50 and sum(m) >= len(m) * 0.98:
                return daily_rank.rank(rows)
            log("  %-6s 10년 일별이 주별과 안 맞음 (%d/%d) — 순위 안 만듦" % (sym, sum(m), len(m)))
    except Exception as e:                        # noqa: BLE001
        log("  %-6s 10년 일별 오류 %s" % (sym, e))
    try:
        with open(os.path.join(OUT_DIR, sym + ".json"), encoding="utf-8") as f:
            old = json.load(f).get("r")
        if old and int(old.get("end", 0)) >= int((today - timedelta(days=30)).strftime("%Y%m%d")):
            return old
    except Exception:                             # noqa: BLE001
        pass
    return None


def mon_map(mon, sym):
    """{YYYYMM: 월말 종가} — 뜀 확인용 참고값"""
    return {a // 100: b for a, b in monthly_rows(mon, sym)}


def fix_jumps(d, w, mm):
    """CNBC 오래된 주별에 분할을 두 번 반영하는 등 계단이 끼는 일이 있다 (브라운앤브라운 2018 12→25,
    QLD·SSO·SQQQ 2020, SOXS 2022). 판별: 주별 값 ÷ 같은 달 월말 종가(따로 받은 값)의 비율이 뜀 앞뒤로
    뛴 배수만큼 바뀌면 자료 오류(또는 분사 미반영) — 그 앞을 모두 맞춘다. 실제로 크게 뛴 날은 비율이 그대로라 손대지 않는다.
    맨 앞 점이 혼자 동떨어진 경우(상장 첫 주 공모가)는 그 점을 뺀다."""
    def mid(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None

    def offset(s, lo, hi):                       # lo < 달 < hi 범위에서 (그 달 마지막 값 ÷ 월말 종가) 중앙값
        last = {}
        for a, b in s:
            last[a // 100] = b
        return mid([last[k] / mm[k] for k in last if lo < k < hi and mm.get(k)])

    def mshift(k, n):
        y, m = divmod(k, 100)
        t = y * 12 + m - 1 + n
        return (t // 12) * 100 + t % 12 + 1

    for _ in range(6):
        if len(w) > 2 and not 0.6 <= w[1][1] / w[0][1] <= 1.6:
            w = w[1:]
            continue
        hit = None
        for i in range(len(w) - 1):
            r = w[i + 1][1] / w[i][1]
            if 0.6 <= r <= 1.6:
                continue
            k = w[i + 1][0] // 100
            ob = offset(w[:i + 1], mshift(k, -7), k)
            oa = offset(w[i + 1:], k, mshift(k, 7))
            if ob and oa and 0.8 <= (oa / ob) / r <= 1.25:
                hit = (w[i + 1][0], oa / ob)          # 다음 주 표시일 앞까지가 옛 기준
                break
        if not hit:
            break
        cut, f = hit
        w = [[a, rnd(b * f) if a < cut else b] for a, b in w]
        d = [[a, rnd(b * f) if a < cut else b] for a, b in d]
    return d, w


def done_session(d):
    """미국 정규장이 끝난 날인가 — 장중 가격을 종가로 넣지 않는다 (뉴욕 16:20 뒤부터 그날을 넣는다)"""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:                             # noqa: BLE001
        now = datetime.now(timezone.utc) - timedelta(hours=5)
    t = int(now.strftime("%Y%m%d"))
    return d < t or (d == t and now.hour * 60 + now.minute >= 16 * 60 + 20)


def add_latest(syms, path_of, proxy=None):
    """CNBC 1년 일별은 마지막 거래일 막대가 몇 시간~하루 늦게 붙는다 → 정규장 종가(시간외 제외)로 그날을 채운다.
    붙이는 조건 (어긋나면 안 붙이고 다음 수집 때 CNBC 일별 막대를 기다린다):
      · 장이 끝난 날이고 파일 마지막 날보다 뒤
      · 시세의 '종가 − 전일 대비'가 파일의 마지막 종가와 같다 (0.05% 안 · 분할·하루 건너뜀 걸러냄)
      · proxy {지수: ETF} 가 있으면 (지수) — 뉴욕 16:15 뒤 확정 시세이고 등락률이 같은 지수 ETF 와 0.3%p 안
        (2026-11-23 S&P 500 시세가 한때 7,260.30 으로 나왔다 — 확정 종가 7,237.17, SPY 등락률과 0.35%p 차이)
    붙인 종목 수를 돌려준다."""
    proxy = proxy or {}
    q = cnbc_quotes(list(syms) + [e for e in proxy.values() if e not in syms])
    n = 0
    for s in syms:
        if s not in q or not done_session(q[s][0]):
            continue
        d, p, ch, hm = q[s]
        try:
            with open(path_of(s), encoding="utf-8") as f:
                last = (json.load(f).get("d") or [[0, 0]])[-1]
        except Exception:                         # noqa: BLE001
            continue
        if last[0] >= d or ch is None or not last[1] or abs((p - ch) / last[1] - 1) > 0.0005:
            if last[0] < d:
                log("  %-6s 시세 %s %.2f (전일 대비 %s) 가 파일 마지막 %s 와 안 이어짐 — 안 붙임" % (s, d, p, ch, last))
            continue
        if s in proxy:
            e = q.get(proxy[s])
            if hm < 16 * 60 + 15 or not e or e[0] != d or e[2] is None or e[1] == e[2]:
                log("  %-6s 확정 시세 확인 못 함 (시각 %d:%02d · ETF %s) — 안 붙임" % (s, hm // 60, hm % 60, e))
                continue
            gap = abs(ch / (p - ch) - e[2] / (e[1] - e[2])) * 100
            if gap > 0.3:
                log("  %-6s 등락률이 %s 와 %.2f%%p 달라 안 붙임 (시세 %.2f)" % (s, proxy[s], gap, p))
                continue
        if append_quote(path_of(s), (d, p)):
            n += 1
    return n


def append_quote(path, q):
    """출처가 다 막힌 날: 있는 파일에 오늘 시세 한 줄만 붙인다."""
    try:
        with open(path, encoding="utf-8") as f:
            j = json.load(f)
    except Exception:                             # noqa: BLE001
        return False
    d, p = q
    if not j.get("d") or j["d"][-1][0] >= d:
        return False
    j["d"].append([d, rnd(p)])
    j["d"] = j["d"][-300:]
    w = j.get("w") or []
    wk_new = date(d // 10000, d // 100 % 100, d % 100).isocalendar()[:2]
    if w:
        lw = w[-1][0]
        if date(lw // 10000, lw // 100 % 100, lw % 100).isocalendar()[:2] == wk_new:
            w[-1] = [d, rnd(p)]
        else:
            w.append([d, rnd(p)])
    j["w"] = w
    with open(path, "w", encoding="utf-8") as f:
        json.dump(j, f, separators=(",", ":"))
    return True


def main():
    argv = [a for a in sys.argv[1:]]
    probe = "--probe" in argv
    syms = [a.upper() for a in argv if not a.startswith("--")]
    try:
        with open(IN_MON, encoding="utf-8") as f:
            mon = json.load(f).get("items") or {}
    except Exception:                             # noqa: BLE001
        mon = {}
    if not syms:
        syms = sorted(mon)
    today = date.today()
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = fail = 0
    srcs = {}
    failed = []
    for i, s in enumerate(syms, 1):
        got, src = build(s, mon, today, probe)
        if probe:
            log("  %-6s %-24s %s" % (s, src or "(막힘)", got))
            continue
        if got and len(got["d"]) >= 2:
            with open(os.path.join(OUT_DIR, s + ".json"), "w", encoding="utf-8") as f:
                json.dump(got, f, separators=(",", ":"))
            ok += 1
            srcs[src] = srcs.get(src, 0) + 1
        else:
            fail += 1
            failed.append(s)
        if i % 25 == 0 or i == len(syms):
            log("  %d/%d  성공 %d · 실패 %d  %s" % (i, len(syms), ok, fail, srcs))
        # 처음 15종목이 전부 실패면 출처가 다 막힌 것 — 오래 돌지 말고 시세 한 줄 붙이기로 넘어간다
        if i == 15 and ok == 0:
            log("  처음 15종목이 모두 실패 — 과거 시세 출처가 막혔습니다. 오늘 시세만 붙입니다.")
            failed = syms
            break
    if probe:
        q = cnbc_quotes(syms)
        for s in syms:
            log("  %-6s 오늘 시세 %s · 장 끝난 날 %s" % (s, q.get(s), q.get(s) and done_session(q[s][0])))
        return
    path_of = lambda s: os.path.join(OUT_DIR, s + ".json")   # noqa: E731
    n = add_latest(syms, path_of)
    log("  마지막 거래일 종가를 붙인 종목 %d / %d (CNBC 정규장 시세 · 일별 막대가 아직 안 붙은 종목)" % (n, len(syms)))
    log("끝: 새로 받은 종목 %d · 출처 %s" % (ok, srcs))


if __name__ == "__main__":
    main()
