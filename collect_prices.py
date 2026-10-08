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
# 해외 — Stooq. 2026-10 부터 자바스크립트 검증이 걸려 스크립트로는 못 받는다.
# from_stooq() 와 아래 두 줄은 되살릴 때를 대비해 남겨 두지만 부르지 않는다.
STOOQ_HOSTS = ["https://stooq.com", "https://stooq.pl"]
STOOQ_PATH = "/q/d/l/?s=%s&i=m"
# 해외 — 알파밴티지 (키 필요, 하루 25회 제한)
AV = ("https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED"
      "&symbol=%s&apikey=%s")
AV_WEEK = ("https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY_ADJUSTED"
           "&symbol=%s&apikey=%s")
AV_KEY = os.environ.get("AV_KEY") or "5HNBQW8WQEJNTZWS"
AV_BUDGET = 25          # 하루 한도 25회를 그대로 쓴다 (확인용 호출을 없앴다)

# 예비 — 야후 (쿠키·토큰 필요, 자주 막힘)
CHART = "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1mo"
COOKIE_URL = "https://fc.yahoo.com/"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
RANGE = "25y"
OUT = "data/returns.json"
OUT_M = "data/monthly_us.json"   # 해외 월말 종가 — 기준점 계산용
MONTH_KEEP = 21 * 12             # 21년치 보관 (20년 카드까지 커버)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SLEEP = 0.12
YEARS_KEEP = 30


def log(*a):
    print(*a, file=sys.stderr, flush=True)

# 지수 ETF — 종목 목록에 없어서 따로 넣는다
EXTRA = [
    # --- 지수 (한·미 공통 인기) ---
    ("SPY",  "SPY",  "US", "S&P500"),
    ("VOO",  "VOO",  "US", "S&P500 뱅가드"),
    ("IVV",  "IVV",  "US", "S&P500 아이셰어즈"),
    ("SPLG", "SPLG", "US", "S&P500 저비용"),
    ("QQQ",  "QQQ",  "US", "나스닥100"),
    ("QQQM", "QQQM", "US", "나스닥100 저비용"),
    ("DIA",  "DIA",  "US", "다우존스30"),
    ("IWM",  "IWM",  "US", "러셀2000 소형주"),
    ("VTI",  "VTI",  "US", "미국 전체"),
    ("VUG",  "VUG",  "US", "성장주"),
    ("VTV",  "VTV",  "US", "가치주"),
    # --- 레버리지·인버스 (서학개미 순매수 상위) ---
    ("TQQQ", "TQQQ", "US", "나스닥100 3배"),
    ("QLD",  "QLD",  "US", "나스닥100 2배"),
    ("SQQQ", "SQQQ", "US", "나스닥100 -3배"),
    ("SSO",  "SSO",  "US", "S&P500 2배"),
    ("UPRO", "UPRO", "US", "S&P500 3배"),
    ("SOXL", "SOXL", "US", "반도체 3배"),
    ("SOXS", "SOXS", "US", "반도체 -3배"),
    ("TMF",  "TMF",  "US", "장기채 3배"),
    # --- 배당 ---
    ("SCHD", "SCHD", "US", "배당성장"),
    ("JEPI", "JEPI", "US", "S&P500 커버드콜 월배당"),
    ("JEPQ", "JEPQ", "US", "나스닥 커버드콜 월배당"),
    ("VYM",  "VYM",  "US", "고배당"),
    ("VIG",  "VIG",  "US", "배당성장 뱅가드"),
    ("DVY",  "DVY",  "US", "고배당 아이셰어즈"),
    ("O",    "O",    "US", "리얼티인컴 월배당"),
    # --- 섹터·테마 ---
    ("SOXX", "SOXX", "US", "반도체"),
    ("SMH",  "SMH",  "US", "반도체 밴엑"),
    ("XLK",  "XLK",  "US", "기술"),
    ("XLF",  "XLF",  "US", "금융"),
    ("XLE",  "XLE",  "US", "에너지"),
    ("XLV",  "XLV",  "US", "헬스케어"),
    ("XLU",  "XLU",  "US", "유틸리티"),
    ("ARKK", "ARKK", "US", "혁신기술 아크"),
    ("VNQ",  "VNQ",  "US", "리츠"),
    # --- 채권·원자재·해외 ---
    ("TLT",  "TLT",  "US", "미국 장기채"),
    ("IEF",  "IEF",  "US", "미국 중기채"),
    ("BND",  "BND",  "US", "미국 채권 전체"),
    ("AGG",  "AGG",  "US", "미국 종합채권"),
    ("GLD",  "GLD",  "US", "금"),
    ("SLV",  "SLV",  "US", "은"),
    ("VEA",  "VEA",  "US", "선진국 (미국 제외)"),
    ("VWO",  "VWO",  "US", "신흥국"),
    ("VXUS", "VXUS", "US", "미국 제외 전세계"),
    # --- 국내 상장 ETF ---
    ("069500", "KODEX 200", "KR", "코스피200"),
    ("102110", "TIGER 200", "KR", "코스피200"),
    ("229200", "KODEX 코스닥150", "KR", "코스닥150"),
    ("122630", "KODEX 레버리지", "KR", "코스피200 2배"),
    ("252670", "KODEX 200선물인버스2X", "KR", "코스피200 -2배"),
    ("233740", "KODEX 코스닥150레버리지", "KR", "코스닥150 2배"),
    ("360750", "TIGER 미국S&P500", "KR", "S&P500"),
    ("133690", "TIGER 미국나스닥100", "KR", "나스닥100"),
    ("379800", "KODEX 미국S&P500", "KR", "S&P500"),
    ("379810", "KODEX 미국나스닥100", "KR", "나스닥100"),
    ("453810", "KODEX 미국S&P500TR", "KR", "S&P500 TR"),
    ("458730", "TIGER 미국배당다우존스", "KR", "SCHD 국내판"),
    ("446720", "SOL 미국배당다우존스", "KR", "SCHD 국내판"),
    ("091160", "KODEX 반도체", "KR", "국내 반도체"),
    ("091170", "KODEX 은행", "KR", "국내 은행"),
    ("305720", "KODEX 2차전지산업", "KR", "2차전지"),
    ("132030", "KODEX 골드선물", "KR", "금"),
]

# 카드에 쓸 만한 해외 종목. 하루 25회뿐이라 순서가 전부다.
# 이 목록을 먼저 채우면 6일이면 '그때 샀다면' 해외 탭을 열 수 있고,
# 나머지 400종목은 그 뒤로 계속 채워진다.
# (연간 수익률 탭은 지금처럼 전체를 쓴다 — 목록을 쪼개지 않는다)
CARD_US = set("""
AAPL MSFT NVDA GOOGL GOOG AMZN META TSLA AVGO BRK-B LLY JPM V XOM UNH MA JNJ PG
COST HD ABBV WMT NFLX BAC KO CRM CVX AMD PEP TMO ADBE LIN MRK ACN MCD CSCO ABT
ORCL WFC DIS QCOM INTC TXN IBM GE CAT NOW VZ AMGN INTU ISRG CMCSA PFE AXP SPGI
UNP GS NEU MS RTX T PGR LOW HON BKNG ELV BLK SYK VRTX TJX C MDT SCHW LMT ADI
DE BSX PLD MMC CB ADP MDLZ REGN ETN AMT CI SBUX BA MO SO ZTS DUK PANW SHW ICE
CME EQIX ITW KLAC SNPS CDNS MU APH MSI PYPL ANET CRWD ABNB UBER PLTR COIN MRNA
SMCI DELL MAR CMG F GM NKE SQ SHOP ARM
""".split())

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


def refine_first_year(years, listed, fetch_fine):
    """첫해를 더 촘촘한 자료로 다시 계산한다.

    월별로는 상장 달이 빠지거나 그 달 말일부터 잡히므로,
    첫해에 한해 일별(국내)·주별(해외) 자료로 시작 종가를 바꾼다.
    fetch_fine(year) -> [(YYYYMMDD, 종가)] 또는 None
    """
    if not years or not listed:
        return years, listed
    y0 = listed[:4]
    if y0 not in years:
        return years, listed
    fine = None
    try:
        fine = fetch_fine(int(y0))
    except Exception:                         # noqa: BLE001
        fine = None
    if not fine:
        return years, listed
    fine = [(d, v) for d, v in fine if str(d)[:4] == y0 and v]
    if len(fine) < 2:
        return years, listed
    fine.sort()
    d_first, v_first = fine[0]
    v_last = fine[-1][1]
    if not v_first:
        return years, listed
    years[y0] = round((v_last / v_first - 1) * 100, 2)
    d = str(d_first)[:8]
    return years, "%s-%s-%s" % (d[:4], d[4:6], d[6:8])


def naver_daily(code, year):
    """국내 — 그해 일별 종가."""
    url = NAVER.replace("timeframe=month", "timeframe=day") % (code, "%d0101" % year, "%d1231" % year)
    txt, _ = get_text(url)
    if not txt:
        return None
    try:
        rows = json.loads(txt.strip().replace("'", '"'))
    except Exception:                         # noqa: BLE001
        return None
    out = []
    for r in rows[1:]:
        try:
            out.append((str(r[0])[:8], float(r[4])))
        except Exception:                     # noqa: BLE001
            continue
    return out


def alpha_weekly(code):
    """해외 — 주별 조정종가 전체 (첫해 정밀화용)."""
    txt, _ = get_text(AV_WEEK % (code.replace(".", "-"), AV_KEY), tries=2)
    if not txt:
        return None
    try:
        j = json.loads(txt)
    except Exception:                         # noqa: BLE001
        return None
    kind, msg = av_trouble(j)
    if kind:
        log("  !! 주별(WEEKLY_ADJUSTED) %s — %s" % (kind, str(msg)[:140]))
        return "LIMIT"
    ts = j.get("Weekly Adjusted Time Series")
    if not ts:
        return None
    out = []
    for d in sorted(ts):
        try:
            out.append((d[:10].replace("-", ""), float(ts[d]["5. adjusted close"])))
        except Exception:                     # noqa: BLE001
            continue
    return out


def month_end_series(pairs):
    """[(YYYYMMDD, 종가)] -> {"s":"YYYY-MM", "v":[...]}  (달이 비면 null)

    달마다 마지막 값만 남기고 연속된 달 배열로 눕힌다. 키를 달마다 적지 않아
    파일이 3분의 1로 줄고, 카드 쪽에서는 첨자 계산만으로 N년 전을 집는다.
    """
    by = {}
    for d, v in pairs:
        if not v:
            continue
        by[str(d)[:6]] = float(v)
    if not by:
        return None
    keys = sorted(by)[-MONTH_KEEP:]
    y0, m0 = int(keys[0][:4]), int(keys[0][4:6])
    y1, m1 = int(keys[-1][:4]), int(keys[-1][4:6])
    n = (y1 - y0) * 12 + (m1 - m0) + 1
    out = [None] * n
    for k in keys:
        i = (int(k[:4]) - y0) * 12 + int(k[4:6]) - m0
        v = by[k]
        # 유효숫자 6자리면 충분하다 — 파일 크기를 반으로 줄인다
        out[i] = round(v, max(0, 6 - len("%d" % abs(int(v) or 1))))
    return {"s": "%04d-%02d" % (y0, m0), "v": out}


def yearly_from_pairs(pairs):
    """[(YYYYMMDD, 종가)] -> (연도별 수익률(%), 첫해 시작일)

    보통 해: 전년도 말 종가 대비.
    첫해(전년도가 없음): 그해 첫 거래월 종가 → 연말 종가.
      상장이든 자료 시작이든 '몇 월부터' 인지 같이 돌려주므로
      화면에서 그만큼만 햇수로 센다.
    """
    first, last = {}, {}
    for d, v in pairs:
        if not v:
            continue
        y = int(str(d)[:4])
        if y not in first:
            first[y] = (str(d)[:8], v)
        last[y] = v
    years = sorted(last)
    if not years:
        return None, None

    out, listed = {}, None
    y0 = years[0]
    d0 = first[y0][0]
    if first[y0][1] and last[y0] != first[y0][1]:
        out[str(y0)] = round((last[y0] / first[y0][1] - 1) * 100, 2)
        listed = "%s-%s-%s" % (d0[:4], d0[4:6], d0[6:8])
    elif first[y0][1]:
        # 그해 자료가 한 달치뿐이면 수익률이 0 이라 의미가 없다 — 건너뛴다
        pass

    for i in range(1, len(years)):
        a, b = years[i - 1], years[i]
        if b != a + 1 or not last[a]:
            continue                          # 중간이 비면 잇지 않는다
        out[str(b)] = round((last[b] / last[a] - 1) * 100, 2)
    if not out:
        return None, None

    keep = sorted(out)[-YEARS_KEEP:]
    out = {k: out[k] for k in keep}
    if listed and str(y0) not in out:
        listed = None
    return out, listed


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
    pairs, last_dt = [], ""
    for r in rows[1:]:
        try:
            pairs.append((str(r[0])[:8], float(r[4])))
            last_dt = str(r[0])[:8]
        except Exception:                     # noqa: BLE001
            continue
    if not pairs:
        return None, "값 없음"
    y, listed = yearly_from_pairs(pairs)
    if not y:
        return None, "기간이 짧음"
    # 첫해는 일별 자료로 첫 거래일 종가부터 다시 계산한다 (네이버는 한도 없음)
    if listed:
        y, listed = refine_first_year(y, listed, lambda yr: naver_daily(code, yr))
    y["_asof"] = "%s-%s-%s" % (last_dt[:4], last_dt[4:6], last_dt[6:8])
    y["_listed"] = listed
    return y, None


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
    pairs, last_dt = [], ""
    for ln in lines[1:]:
        c = ln.split(",")
        if len(c) < 5:
            continue
        try:
            pairs.append((c[0][:10].replace("-", ""), float(c[4])))
            last_dt = c[0][:10]
        except Exception:                     # noqa: BLE001
            continue
    if not pairs:
        return None, "값 없음"
    y, listed = yearly_from_pairs(pairs)
    if not y:
        return None, "기간이 짧음"
    y["_asof"] = last_dt
    y["_listed"] = listed
    y["_pairs"] = pairs
    return y, None


def av_trouble(j):
    """알파밴티지가 자료 대신 보낸 안내문을 종류별로 가른다.
       예전에는 전부 '한도 초과'로 뭉뚱그려서, 키가 막힌 건지 한도인지
       구분이 안 됐다. 그래서 며칠째 안 받아져도 이유를 알 수 없었다."""
    msg = j.get("Note") or j.get("Information") or j.get("Error Message")
    if not msg:
        return None, None
    low = str(msg).lower()
    # 한도 안내문에도 'premium plans' 링크가 들어 있다. 한도를 먼저 본다.
    if ("rate limit" in low or "per day" in low or "per minute" in low
            or "call frequency" in low or "requests per" in low):
        return "한도 초과", msg
    if "premium endpoint" in low or "is a premium" in low:
        return "유료 전용", msg
    if "apikey" in low or "invalid" in low:
        return "키 문제", msg
    return "거절됨", msg


def from_alpha(code):
    """해외 — 알파밴티지 월별 조정종가. 배당 재투자가 포함된 총수익률."""
    txt, why = get_text(AV % (code.replace(".", "-"), AV_KEY), tries=2)
    if not txt:
        return None, why
    try:
        j = json.loads(txt)
    except Exception:                         # noqa: BLE001
        return None, "형식 오류"
    kind, msg = av_trouble(j)
    if kind:
        if kind != "한도 초과":
            log("  !! 알파밴티지 %s — %s" % (kind, str(msg)[:160]))
        return None, kind
    ts = j.get("Monthly Adjusted Time Series")
    if not ts:
        return None, "자료 없음"
    pairs, last_dt = [], ""
    for d in sorted(ts):
        try:
            pairs.append((d[:10].replace("-", ""), float(ts[d]["5. adjusted close"])))
            last_dt = d[:10]
        except Exception:                     # noqa: BLE001
            continue
    y, listed = yearly_from_pairs(pairs)
    if not y:
        return None, "기간이 짧음"
    # 첫해가 1월이 아니면(상장 가능성) 주별 자료로 시작을 바로잡는다.
    # 호출 1회가 더 들어가므로 예산이 남아 있을 때만.
    # 주별 자료는 '있으면 좋은' 보정이다. 이것 때문에 월별 수집까지
    # 멈추면 안 된다. 예전에는 여기서 예산을 0으로 밀어버려서
    # 하루에 딱 한 종목만 받아지고 있었다.
    y["_pairs"] = pairs
    if (listed and listed[5:7] != "01"
            and not _refine_off[0] and _av_extra[0] > 2):
        _av_extra[0] -= 1
        wk = alpha_weekly(code)
        if wk == "LIMIT":
            _refine_off[0] = True             # 정밀화만 끈다
            log("  첫해 정밀화를 끕니다 — 월별 수집은 계속합니다")
        elif wk:
            y, listed = refine_first_year(y, listed, lambda yr: wk)
    y["_asof"] = last_dt
    y["_listed"] = listed
    return y, None


_av_extra = [0]           # 남은 알파밴티지 호출 수 (수집 루프와 같은 리스트를 가리킨다)
_refine_off = [False]     # 주별 자료가 막히면 첫해 정밀화만 끈다


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


def check():
    """알파밴티지가 실제로 무슨 답을 주는지 한 번만 불러 그대로 보여준다.
       한도인지, 유료 전용으로 바뀐 건지, 키가 막힌 건지 여기서 갈린다."""
    log("키 %s…%s 로 AAPL 월별 조정종가를 한 번 부릅니다\n"
        % (AV_KEY[:4], AV_KEY[-4:]))
    txt, why = get_text(AV % ("AAPL", AV_KEY))
    if not txt:
        log("연결 실패: %s" % why); return
    try:
        j = json.loads(txt)
    except Exception:                         # noqa: BLE001
        log("JSON 이 아닙니다. 앞부분:\n%s" % txt[:400]); return

    kind, msg = av_trouble(j)
    if kind:
        log("판정: %s\n" % kind)
        log("원문: %s\n" % msg)
        if kind == "한도 초과":
            log("→ 오늘 25회를 다 썼습니다. 정상입니다. 내일 이어서 받습니다.")
        elif kind == "유료 전용":
            log("→ 이 엔드포인트가 유료로 바뀌었습니다. 무료로는 더 못 받습니다.")
            log("   무료 대안(Stooq 등)으로 갈아타거나 유료 요금제가 필요합니다.")
        elif kind == "키 문제":
            log("→ 키가 막혔거나 잘못됐습니다. 새 키를 받아 AV_KEY 를 바꾸세요.")
        return

    ts = j.get("Monthly Adjusted Time Series") or {}
    if not ts:
        log("알 수 없는 응답입니다. 키 목록: %s" % list(j)[:6]); return
    d = sorted(ts)
    log("월별(MONTHLY_ADJUSTED)  정상 · %d개월치 · %s ~ %s" % (len(d), d[0][:10], d[-1][:10]))

    # 주별도 쓴다. 이게 막히면 첫해 정밀화가 안 되고,
    # 예전에는 그것 때문에 수집 전체가 하루 한 종목으로 줄었다.
    log("")
    txt2, why2 = get_text(AV_WEEK % ("AAPL", AV_KEY), tries=2)
    if not txt2:
        log("주별(WEEKLY_ADJUSTED)   연결 실패: %s" % why2); return
    try:
        j2 = json.loads(txt2)
    except Exception:                         # noqa: BLE001
        log("주별(WEEKLY_ADJUSTED)   JSON 아님: %s" % txt2[:200]); return
    k2, m2 = av_trouble(j2)
    if k2:
        log("주별(WEEKLY_ADJUSTED)   %s" % k2)
        log("  원문: %s" % m2)
        if k2 == "유료 전용":
            log("  → 주별은 유료입니다. 첫해 정밀화는 포기하고 월별만 씁니다.")
            log("     (새 판에서는 이래도 월별 수집이 계속됩니다)")
        elif k2 == "한도 초과":
            log("  → 방금 월별로 1회를 썼으니 한도에 걸렸을 수 있습니다.")
        return
    w = j2.get("Weekly Adjusted Time Series") or {}
    log("주별(WEEKLY_ADJUSTED)   정상 · %d주치" % len(w))
    log("\n→ 둘 다 정상이면 알파밴티지 문제는 아닙니다.")


def status():
    """저장된 자료가 언제 받아진 건지 본다."""
    try:
        with open(OUT, encoding="utf-8") as f:
            j = json.load(f)
    except Exception as e:                    # noqa: BLE001
        log("%s 를 못 읽었습니다 (%s)" % (OUT, e)); return
    items = j.get("items", {})
    us = {c: v for c, v in items.items() if not c.isdigit()}
    kr = len(items) - len(us)
    log("파일 기록 %s · 전체 %d종목 (국내 %d · 해외 %d)"
        % (j.get("updated", "?"), len(items), kr, len(us)))

    known = [(c, v) for c, v in us.items() if not c.isdigit()]
    todo = [c for c, n, m, d in load_universe([], "US") if c not in items]
    by = {}
    for c, v in known:
        by[v.get("fetched") or "(기록 없음)"] = by.get(v.get("fetched") or "(기록 없음)", 0) + 1
    log("\n해외 종목을 받아온 날")
    for k in sorted(by, reverse=True)[:14]:
        log("  %-12s %4d종목" % (k, by[k]))
    if todo:
        log("\n아직 한 번도 못 받은 해외 종목 %d개" % len(todo))
        log("  %s%s" % (" ".join(todo[:20]), " …" if len(todo) > 20 else ""))
        log("  하루 %d개씩이면 약 %d일" % (AV_BUDGET, -(-len(todo) // AV_BUDGET)))
    else:
        log("\n해외 종목은 모두 한 번씩은 받았습니다.")


def main():
    global DEBUG
    argv = sys.argv[1:]
    global USE_YAHOO
    if "--check" in argv:
        return check()
    if "--status" in argv:
        return status()
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
        # Stooq 는 2026-10 부터 자바스크립트 검증을 걸어 스크립트로는
        # 뚫을 수 없다(probe_sources.py 에 근거). 부르지 않는다.
        stooq_blocked[0] = True
        checks.append(("해외(알파밴티지)", True, ""))
    if only in (None, "KR"):
        p, w = from_naver("005930")
        checks.append(("국내(네이버)", p, w))

    okAny = False
    for label, p, w in checks:
        if p is True:                          # 확인을 건너뛴 경우
            okAny = True
            log("%s 사용 (첫 종목에서 한도를 확인합니다)" % label)
        elif p:
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

    # 월말 종가도 같은 방식으로 이어 붙인다 (못 받은 종목은 옛 값 유지)
    prevm = {}
    try:
        with open(OUT_M, encoding="utf-8") as f:
            prevm = json.load(f).get("items", {})
    except Exception:                         # noqa: BLE001
        pass
    series = dict(prevm)

    # 이미 받아둔 종목은 그대로 유지하고, 이번에 받은 것만 덮어쓴다.
    # (국내만·해외만 돌려도 나머지가 날아가지 않도록)
    items, fails = dict(prev), []
    av_left = _av_extra                          # 같은 리스트 — 정밀화 호출도 여기서 뺀다
    av_left[0] = max(0, AV_BUDGET - av_used[0])
    stooq_miss, stooq_dead = [0], [stooq_blocked[0]]
    av_dry, warned, av_stop = [False], [False], [""]
    started = time.time()
    # 해외는 하루 25개만 받을 수 있다. 아직 없는 종목을 먼저 채우고,
    # 다 채운 뒤에는 '가장 오래된 것부터' 돌아가며 새로 받는다.
    # (예전에는 순서가 고정이라 늘 같은 25종목만 새로 받고 나머지는
    #  영영 그대로였다)
    TODAY = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    def order(x):
        code = x[0]
        # 해외를 먼저 돈다. 하루 25회뿐이라 1~2분이면 끝나고, 그 뒤에
        # 한도 없는 국내가 몇 시간 돈다. 예전에는 국내가 앞에 있어서
        # 작업이 중간에 끊기면 해외는 한두 종목 만에 잘렸다.
        if not code.isdigit():
            if code not in prev:
                return (0 if code in CARD_US else 1, "")   # 카드용부터
            return (2, prev[code].get("fetched") or "")    # 오래된 것부터
        return (3, "")                          # 국내는 한도가 없으니 맨 뒤

    universe.sort(key=order)

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
            years, why = None, "건너뜀"       # Stooq 폐기 — 알파밴티지만 쓴다
            # 하루 한도가 있어 아껴 쓴다
            if av_left[0] > 0:
                av_left[0] -= 1
                y2, w2 = from_alpha(code)
                if y2:
                    years, why = y2, None
                elif w2 in ("한도 초과", "유료 전용", "키 문제", "거절됨"):
                    av_left[0] = 0
                    av_dry[0] = True
                    av_stop[0] = w2
                    why = "알파밴티지 " + w2
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
                    if av_stop[0] == "한도 초과":
                        log("\n오늘 알파밴티지 한도(하루 25회)를 다 썼습니다.")
                        log("남은 종목은 내일 이어서 받습니다. 이미 받아둔 자료는 그대로 있습니다.\n")
                    else:
                        log("\n!! 알파밴티지가 '%s' 로 거절했습니다. 내일도 같을 겁니다." % av_stop[0])
                        log("   python3 collect_prices.py --check 로 원문을 확인하세요.\n")
        else:
            asof = years.pop("_asof", "")
            listed = years.pop("_listed", None)
            pr = years.pop("_pairs", None)
            if pr and mk == "US":
                ms = month_end_series(pr)
                if ms:
                    ms["asof"] = asof
                    series[code] = ms
            items[code] = {"name": name, "market": mk, "desc": desc,
                           "years": years, "asof": asof, "fetched": TODAY}
            if listed:
                items[code]["listed"] = listed

        if i % 100 == 0 or i == len(universe):
            log("  %d/%d  (%.1f분)" % (i, len(universe), (time.time()-started)/60))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
            "source": "네이버 금융(국내 수정주가) · 알파밴티지(해외 조정종가)",
            "count": len(items),
            "items": items,
        }, f, ensure_ascii=False, separators=(",", ":"))

    if series:
        with open(OUT_M, "w", encoding="utf-8") as f:
            json.dump({
                "updated": TODAY,
                "note": "해외 월말 조정종가 · 배당 재투자 포함 · 21년치",
                "count": len(series),
                "items": series,
            }, f, ensure_ascii=False, separators=(",", ":"))
        log("월말 종가 %d종목 · %.1fMB -> %s"
            % (len(series), os.path.getsize(OUT_M) / 1024 / 1024, OUT_M))

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
                % (AV_BUDGET, -(-left // max(1, AV_BUDGET))))
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
