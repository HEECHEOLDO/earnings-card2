#!/usr/bin/env python3
"""
연간 수익률 수집기 -> data/returns.json

야후 파이낸스에서 월별 조정종가를 받아 연도별 수익률을 계산한다.
조정종가라 배당과 액면분할이 모두 반영된 총수익률이다.

브라우저에서 직접 부르면 CORS 에 막히지만, 여기서는 서버에서 부르므로
그런 제약이 없다. 결과를 JSON 으로 저장해두면 화면은 그 파일만 읽으면 된다.

사용법:
    python3 collect_prices.py                # data/index.json + data/us/index.json 전체
    python3 collect_prices.py 005930 AAPL    # 종목 지정
    python3 collect_prices.py --kr           # 국내만
    python3 collect_prices.py --us           # 해외만
    python3 collect_prices.py --limit 50     # 앞에서 50종목만 (시험용)

표준 라이브러리만 사용한다.
"""

import gzip
import http.cookiejar
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# 국내 — 네이버 (수정주가, 인증 없음)
NAVER = ("https://api.finance.naver.com/siseJson.naver"
         "?symbol=%s&requestType=1&startTime=%s&endTime=%s&timeframe=month")
# 해외 — Stooq (월별 CSV, 인증 없음)
STOOQ_HOSTS = ["https://stooq.com", "https://stooq.pl"]
STOOQ_PATH = "/q/d/l/?s=%s&i=m"
# 해외 — 알파밴티지 (키 필요, 하루 25회 제한)
AV = ("https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED"
      "&symbol=%s&apikey=%s")
AV_KEY = os.environ.get("AV_KEY") or "5HNBQW8WQEJNTZWS"
AV_BUDGET = 24          # 하루 한도 25회 — 한 번은 여유로 남긴다

# 예비 — 야후 (쿠키·토큰 필요, 자주 막힘)
CHART = "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1mo"
COOKIE_URL = "https://fc.yahoo.com/"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
RANGE = "25y"
OUT = "data/returns.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SLEEP = 0.12
YEARS_KEEP = 30


def log(*a):
    print(*a, file=sys.stderr, flush=True)

# 지수 ETF — 종목 목록에 없어서 따로 넣는다
EXTRA = [
    ("SPY", "SPY", "US", "S&P500"),
    ("QQQ", "QQQ", "US", "나스닥100"),
    ("DIA", "DIA", "US", "다우존스30"),
    ("IWM", "IWM", "US", "러셀2000"),
    ("SOXX", "SOXX", "US", "반도체"),
    ("VTI", "VTI", "US", "미국 전체"),
    ("VOO", "VOO", "US", "S&P500"),
    ("SCHD", "SCHD", "US", "배당"),
    ("TLT", "TLT", "US", "미국 장기채"),
    ("GLD", "GLD", "US", "금"),
    ("069500", "KODEX 200", "KR", "코스피200"),
    ("229200", "KODEX 코스닥150", "KR", "코스닥150"),
    ("360750", "TIGER 미국S&P500", "KR", "S&P500"),
    ("133690", "TIGER 미국나스닥100", "KR", "나스닥100"),
]

_calls = 0
_session = None
USE_YAHOO = False
_crumb = ""
DEBUG = False


def open_session():
    """야후는 2024년부터 쿠키와 crumb 토큰을 요구한다.

    쿠키를 먼저 받고, 그 쿠키로 crumb 을 받아 이후 요청에 붙인다.
    """
    global _session, _crumb
    jar = http.cookiejar.CookieJar()
    _session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    _session.addheaders = [("User-Agent", UA),
                           ("Accept", "*/*"),
                           ("Accept-Language", "en-US,en;q=0.9")]
    try:
        _session.open(COOKIE_URL, timeout=15).read()
    except Exception as e:                    # noqa: BLE001
        # fc.yahoo.com 은 404 를 주기도 하는데 쿠키만 받으면 된다
        if DEBUG:
            log("  쿠키 응답: %r" % e)
    try:
        r = _session.open(CRUMB_URL, timeout=15)
        _crumb = r.read().decode("utf-8").strip()
    except Exception as e:                    # noqa: BLE001
        log("! crumb 토큰을 받지 못했습니다: %r" % e)
        _crumb = ""
    if _crumb:
        log("crumb 토큰 확보 (%s…)" % _crumb[:6])
    else:
        log("crumb 없이 진행합니다 (실패할 수 있습니다)")
    return _crumb


def get_json(url, tries=3):
    """실패하면 이유를 문자열로 함께 돌려준다."""
    global _calls
    if _session is None:
        open_session()
    if _crumb and "crumb=" not in url:
        url += "&crumb=" + urllib.parse.quote(_crumb)

    last = ""
    for i in range(tries):
        try:
            _calls += 1
            req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
            with _session.open(req, timeout=25) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            time.sleep(SLEEP)
            return json.loads(raw.decode("utf-8")), ""
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code == 404:
                return None, last
            if e.code in (401, 403):
                # 토큰이 만료됐을 수 있으니 한 번 새로 받는다
                if i == 0:
                    open_session()
                    continue
                return None, last
            time.sleep(1.2 + i)
        except Exception as e:                # noqa: BLE001
            last = type(e).__name__
            time.sleep(1.2 + i)
    return None, last or "실패"


def get_text(url, tries=3, use_session=False):
    """본문을 문자열로 받는다."""
    global _calls
    last = ""
    for i in range(tries):
        try:
            _calls += 1
            if use_session:
                if _session is None:
                    open_session()
                r = _session.open(urllib.request.Request(
                    url, headers={"Accept-Encoding": "gzip"}), timeout=25)
            else:
                r = urllib.request.urlopen(urllib.request.Request(url, headers={
                    "User-Agent": UA, "Accept": "*/*",
                    "Accept-Encoding": "gzip",
                    "Referer": "https://finance.naver.com/"}), timeout=25)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            time.sleep(SLEEP)
            return raw.decode("utf-8", "ignore"), ""
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code == 404:
                return None, last
            if e.code == 429:                 # 너무 빠르다 — 점점 더 쉰다
                time.sleep(3 * (i + 1))
            else:
                time.sleep(1.2 + i)
        except Exception as e:                # noqa: BLE001
            last = type(e).__name__
            time.sleep(1.2 + i)
    return None, last or "실패"


def yearly_from_pairs(pairs):
    """[(연도, 종가)] -> 연도별 수익률(%)"""
    last = {}
    for y, v in pairs:
        if v:
            last[y] = v
    years = sorted(last)
    if len(years) < 2:
        return None
    out = {}
    for i in range(1, len(years)):
        a, b = years[i-1], years[i]
        if b != a + 1 or not last[a]:
            continue
        out[str(b)] = round((last[b] / last[a] - 1) * 100, 2)
    if not out:
        return None
    keep = sorted(out)[-YEARS_KEEP:]
    return {k: out[k] for k in keep}


def from_naver(code):
    """국내 — 네이버 월봉. 수정주가라 액면분할이 반영돼 있다."""
    url = NAVER % (code, "19900101", datetime.now().strftime("%Y%m%d"))
    txt, why = get_text(url)
    if not txt:
        return None, why
    # 파이썬 리터럴에 가까운 형태라 따옴표만 바꿔 읽는다
    try:
        rows = json.loads(txt.strip().replace("'", '"'))
    except Exception:                         # noqa: BLE001
        return None, "형식 오류"
    pairs = []
    for r in rows[1:]:
        try:
            pairs.append((int(str(r[0])[:4]), float(r[4])))
        except Exception:                     # noqa: BLE001
            continue
    if not pairs:
        return None, "값 없음"
    y = yearly_from_pairs(pairs)
    return (y, None) if y else (None, "기간이 짧음")


def from_stooq(code):
    """해외 — Stooq 월별 CSV."""
    sym = code.replace(".", "-").lower() + ".us"
    txt, why = None, ""
    for host in STOOQ_HOSTS:                  # 한쪽이 막히면 다른 주소로
        txt, why = get_text(host + STOOQ_PATH % sym)
        if txt and txt.lower().lstrip().startswith("date"):
            break
    if not txt:
        return None, why
    txt = txt.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [x for x in txt.split("\n") if x.strip()]
    if not lines or not lines[0].lower().startswith("date"):
        head = txt[:90].replace("\n", " | ")
        if DEBUG:
            log("  Stooq(%s) 응답: %s" % (sym, head))
        if "limit" in txt.lower():
            return None, "Stooq 한도 초과"
        return None, "형식 오류(%s)" % head[:36]
    if len(lines) < 3:
        return None, "자료가 너무 적음"
    pairs = []
    for ln in lines[1:]:
        c = ln.split(",")
        if len(c) < 5:
            continue
        try:
            pairs.append((int(c[0][:4]), float(c[4])))
        except Exception:                     # noqa: BLE001
            continue
    if not pairs:
        return None, "값 없음"
    y = yearly_from_pairs(pairs)
    return (y, None) if y else (None, "기간이 짧음")


def from_alpha(code):
    """해외 — 알파밴티지 월별 조정종가. 배당 재투자가 포함된 총수익률."""
    txt, why = get_text(AV % (code.replace(".", "-"), AV_KEY))
    if not txt:
        return None, why
    try:
        j = json.loads(txt)
    except Exception:                         # noqa: BLE001
        return None, "형식 오류"
    if j.get("Note") or j.get("Information"):
        return None, "한도 초과"
    ts = j.get("Monthly Adjusted Time Series")
    if not ts:
        return None, "자료 없음"
    pairs = []
    for d in sorted(ts):
        try:
            pairs.append((int(d[:4]), float(ts[d]["5. adjusted close"])))
        except Exception:                     # noqa: BLE001
            continue
    y = yearly_from_pairs(pairs)
    return (y, None) if y else (None, "기간이 짧음")


def yahoo_symbol(code, desc=""):
    """야후 기호로 바꾼다.

    국내는 코스피 .KS, 코스닥 .KQ 로 접미사가 다르다.
    미국은 점을 대시로 바꾼다 (BRK.B -> BRK-B).
    """
    if code.isdigit():
        return code + (".KQ" if "코스닥" in (desc or "") else ".KS")
    return code.replace(".", "-")


def annual_returns(symbol):
    """연도별 수익률(%) 을 돌려준다. 조정종가 기준이라 배당이 포함된다."""
    j, why = get_json(CHART % (symbol, RANGE))
    if not j:
        return None, why or "응답 없음"
    res = (j.get("chart") or {}).get("result")
    if not res:
        return None, "데이터 없음"
    r = res[0]
    stamps = r.get("timestamp") or []
    ind = r.get("indicators") or {}
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    if not adj:
        adj = (ind.get("quote") or [{}])[0].get("close")
    if not stamps or not adj:
        return None, "종가 없음"

    # 연도별 마지막 유효 종가
    last = {}
    for t, v in zip(stamps, adj):
        if v is None:
            continue
        y = datetime.fromtimestamp(t, timezone.utc).year
        last[y] = v

    years = sorted(last)
    if len(years) < 2:
        return None, "기간이 짧음"

    out = {}
    for i in range(1, len(years)):
        a, b = years[i - 1], years[i]
        if b != a + 1:
            continue                          # 중간이 비면 잇지 않는다
        if not last[a]:
            continue
        out[str(b)] = round((last[b] / last[a] - 1) * 100, 2)
    if not out:
        return None, "계산할 값 없음"

    keep = sorted(out)[-YEARS_KEEP:]
    return {k: out[k] for k in keep}, None


def load_universe(args, only):
    """[(코드, 이름, 시장, 설명)] 목록."""
    items, seen = [], set()

    def add(code, name, market, desc=""):
        if code in seen:
            return
        seen.add(code)
        items.append((code, name, market, desc))

    if args:
        for a in args:
            mk = "KR" if a.isdigit() else "US"
            add(a.upper() if mk == "US" else a, a, mk)
        return items

    for code, name, market, desc in EXTRA:
        if only in (None, market):
            add(code, name, market, desc)

    if only in (None, "KR"):
        try:
            with open("data/index.json", encoding="utf-8") as f:
                for c in json.load(f).get("companies", []):
                    add(c["code"], c.get("name") or c["code"], "KR", c.get("market") or "")
        except Exception:                     # noqa: BLE001
            log("! data/index.json 을 읽지 못했습니다 (국내 건너뜀)")

    if only in (None, "US"):
        try:
            with open("data/us/index.json", encoding="utf-8") as f:
                for c in json.load(f).get("companies", []):
                    add(c["code"], c["code"], "US", c.get("legal_name") or "")
        except Exception:                     # noqa: BLE001
            log("! data/us/index.json 을 읽지 못했습니다 (해외 건너뜀)")

    return items


def main():
    global DEBUG
    argv = sys.argv[1:]
    global USE_YAHOO
    DEBUG = "--debug" in argv
    USE_YAHOO = "--yahoo" in argv
    only = "KR" if "--kr" in argv else ("US" if "--us" in argv else None)
    global SLEEP
    if "--sleep" in argv:
        i = argv.index("--sleep")
        if i + 1 < len(argv):
            SLEEP = float(argv[i + 1])
            del argv[i:i + 2]
    limit = 0
    if "--limit" in argv:
        i = argv.index("--limit")
        if i + 1 < len(argv):
            limit = int(argv[i + 1])
            del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]

    av_used = [0]
    stooq_blocked = [False]
    universe = load_universe(args, only)

    # 본격 수집 전에 출처별로 한 종목씩 확인한다
    checks = []
    if only in (None, "US"):
        p, w = from_stooq("AAPL")
        if p:
            checks.append(("해외(Stooq)", p, w))
        else:
            # Stooq 가 막혀 있으면 알파밴티지로 확인한다
            log("해외(Stooq) 막힘: %s — 알파밴티지로 확인합니다" % w)
            stooq_blocked[0] = True
            p2, w2 = from_alpha("AAPL")
            checks.append(("해외(알파밴티지)", p2, w2))
            av_used[0] += 1                   # 확인에 쓴 1회도 예산에서 뺀다
    if only in (None, "KR"):
        p, w = from_naver("005930")
        checks.append(("국내(네이버)", p, w))

    okAny = False
    for label, p, w in checks:
        if p:
            okAny = True
            log("%s 확인 OK — %d개 연도 (%s~%s)" % (label, len(p), min(p), max(p)))
        else:
            log("!! %s 확인 실패: %s" % (label, w))
    if not okAny and "--force" not in argv:
        quota = any("한도" in (w or "") for _, p, w in checks)
        if quota:
            log("\n오늘 알파밴티지 한도(하루 25회)를 다 썼습니다.")
            log("내일 다시 실행하면 이어서 받습니다.")
            log("국내만 먼저 받으려면:  python3 collect_prices.py --kr")
        else:
            log("\n어느 출처도 열리지 않습니다. 인터넷 연결을 확인하거나")
            log("잠시 뒤 다시 시도하세요. 그래도 진행하려면 --force 를 붙이세요.")
        return
    log("")

    if limit:
        universe = universe[:limit]
    log("대상 %d종목" % len(universe))

    # 기존 결과를 불러와 실패한 종목은 옛 값을 유지한다
    prev = {}
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f).get("items", {})
    except Exception:                         # noqa: BLE001
        pass

    items, fails = {}, []
    av_left = [max(0, AV_BUDGET - av_used[0])]   # 확인에 쓴 만큼 뺀다
    stooq_miss, stooq_dead = [0], [stooq_blocked[0]]
    av_dry, warned = [False], [False]
    started = time.time()
    # 해외는 하루 한도가 있어, 아직 없는 종목부터 채운다
    universe.sort(key=lambda x: (0 if x[0].isdigit() else (0 if x[0] not in prev else 1)))

    for i, (code, name, market, desc) in enumerate(universe, 1):
        # 해외만 남았는데 한도가 없으면 더 돌 이유가 없다
        if av_dry[0] and not code.isdigit():
            if code in prev:
                items[code] = prev[code]
            continue
        mk = "KR" if code.isdigit() else "US"
        if mk == "KR":
            years, why = from_naver(code)
        else:
            years, why = (None, "건너뜀") if stooq_dead[0] else from_stooq(code)
            # Stooq 는 봇을 막는 날이 있다. 두 번 막히면 그날은 더 안 부른다.
            if years is None and not stooq_dead[0]:
                stooq_miss[0] += 1
                if stooq_miss[0] >= 2:
                    stooq_dead[0] = True
                    log("  Stooq 가 막혀 있어 알파밴티지만 씁니다")
            # 하루 한도가 있어 아껴 쓴다
            if years is None and av_left[0] > 0:
                av_left[0] -= 1
                y2, w2 = from_alpha(code)
                if y2:
                    years, why = y2, None
                elif w2 == "한도 초과":
                    av_left[0] = 0
                    av_dry[0] = True
                    why = "알파밴티지 한도 소진"
                else:
                    why = w2

        # 야후는 자주 막혀서 기본으로는 쓰지 않는다 (--yahoo 로 켠다)
        if years is None and USE_YAHOO:
            y2, w2 = annual_returns(yahoo_symbol(code, desc))
            if y2:
                years, why = y2, None
            else:
                why = why + " / 야후 " + (w2 or "실패")

        if years is None:
            if code in prev:
                items[code] = prev[code]      # 옛 값 유지
            else:
                fails.append((code, name, why))
                if av_dry[0] and not warned[0]:
                    warned[0] = True
                    log("\n오늘 알파밴티지 한도(하루 25회)를 다 썼습니다.")
                    log("남은 종목은 내일 이어서 받습니다. 이미 받아둔 자료는 그대로 있습니다.\n")
        else:
            items[code] = {"name": name, "market": mk, "desc": desc, "years": years}

        if i % 100 == 0 or i == len(universe):
            log("  %d/%d  (%.1f분)" % (i, len(universe), (time.time()-started)/60))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
            "source": "네이버 금융 · Stooq · 수정주가 기준",
            "count": len(items),
            "items": items,
        }, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT) / 1024 / 1024
    log("\n" + "=" * 52)
    log("저장 %d종목 · %.1fMB · 소요 %.1f분 · 호출 %d회"
        % (len(items), size, (time.time()-started)/60, _calls))
    us_have = sum(1 for c in items if not c.isdigit())
    us_all = sum(1 for x in universe if not x[0].isdigit())
    if us_all:
        log("해외 %d/%d종목 확보" % (us_have, us_all))
        if av_dry[0]:
            left = us_all - us_have
            log("  오늘 한도를 다 썼습니다. 하루 %d개씩 채우면 약 %d일 남았습니다."
                % (AV_BUDGET - 1, -(-left // max(1, AV_BUDGET - 1))))
    fails = [f for f in fails if f[2] not in ("건너뜀",)]
    if fails:
        by = {}
        for _, _, why in fails:
            by[why] = by.get(why, 0) + 1
        log("실패 %d종목  |  %s" % (len(fails),
            "  ".join("%s %d건" % kv for kv in sorted(by.items(), key=lambda x: -x[1]))))
        for code, name, why in fails[:25]:
            log("  %-10s %-16s %s" % (code, name[:16], why))
        if len(fails) > 25:
            log("  … 외 %d종목" % (len(fails) - 25))


if __name__ == "__main__":
    main()
