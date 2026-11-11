#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미국 시가총액 — 시가총액 탭(mcap.html)·시총 순위 탭(rank.html)의 '미국' 자료를 만든다.

  python3 collect_us_mcap.py              매일: 나스닥 종목 검색표 → data/mcap_us.json + 시총 순위 '현재' 칸의 미국
  python3 collect_us_mcap.py --history    한 번만: 1996~작년 연말 미국 순위 → data/rank.json 의 연도 칸에 'us'
  python3 collect_us_mcap.py --half       해마다 6월 말 미국 순위 → data/rank_half.json (변천사 영상용)
  python3 collect_us_mcap.py --show       받아 둔 것 보기 (호출 0회)
  python3 collect_us_mcap.py --dry        매일 수집을 시험으로 — 받아서 상위 10만 보여주고 파일은 안 바꿈

· 지금 시가총액: 나스닥 종목 검색표(api.nasdaq.com) — 미국 상장 전 종목의 시총·섹터·업종, 키 필요 없음
  같은 회사의 주식 종류(GOOGL·GOOG, BRK-A·BRK-B)는 하나로 합친다 (큰 쪽).
  검색표는 장 마감 뒤 한참 지나서야 갱신돼, 아침에 받으면 하루 전 종가인 경우가 많다 (2026-10 확인).
  그래서 시총 상위 FIX_TOP 종목은 종목별 시세(api.nasdaq.com/api/quote/…/info)의 'Closed at 날짜' 종가로
  시총을 다시 계산한다: 시총 × 최신 종가 ÷ 검색표 가격 (= 주식 수 × 최신 종가).
  화면에 찍히는 기준일(asof)도 짐작하지 않고 그 종가의 날짜를 쓴다.
· 과거 연말: companiesmarketcap.com 의 회사별 '연도별 시가총액' 표.
  모든 미국 회사를 받을 수는 없어서, 역대 시총 상위에 들었던 대형주 후보(CANDIDATES)만 받는다.
  후보에 없는 회사는 과거 순위에 안 나온다 → 빠진 회사가 보이면 CANDIDATES 에 한 줄 더하면 된다.
  받은 원본은 _cmc/ 에 두고 다시 받지 않는다.
단위: 시총은 '억 달러' (화면에서 1조 달러 이상은 '5.1조 달러', 그 아래는 '8,500억 달러').
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT_MCAP = os.path.join("data", "mcap_us.json")
OUT_RANK = os.path.join("data", "rank.json")
CACHE = "_cmc"
TOP = 60          # 시가총액 탭: 상위 몇 개
TOP_GROUP = 60    # 섹터·업종마다 몇 개
TOP_RANK = 50     # 시총 순위·시가총액 탭 과거 연도: 칸마다 몇 위까지
FIX_TOP = 150     # 최신 종가로 다시 계산할 시총 상위 종목 수 (종목마다 호출 1번)
FIX_MAX_MOVE = 0.5  # 검색표 가격과 최신 종가가 이보다 더 벌어지면 (액면분할 등) 고치지 않는다
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# 역대 미국 시총 상위 후보: 티커 → (companiesmarketcap 주소 이름, 짧은 이름)
CANDIDATES = {
    "AAPL": ("apple", "Apple"), "MSFT": ("microsoft", "Microsoft"), "NVDA": ("nvidia", "NVIDIA"),
    "GOOGL": ("alphabet-google", "Alphabet"), "AMZN": ("amazon", "Amazon"), "META": ("meta-platforms|facebook|meta", "Meta"),
    "TSLA": ("tesla", "Tesla"), "BRK-B": ("berkshire-hathaway", "Berkshire Hathaway"), "AVGO": ("broadcom", "Broadcom"),
    "LLY": ("eli-lilly", "Eli Lilly"), "JPM": ("jp-morgan-chase", "JPMorgan Chase"), "V": ("visa", "Visa"),
    "WMT": ("walmart", "Walmart"), "XOM": ("exxon-mobil", "Exxon Mobil"), "UNH": ("united-health", "UnitedHealth"),
    "MA": ("mastercard", "Mastercard"), "JNJ": ("johnson-and-johnson", "Johnson & Johnson"),
    "PG": ("procter-and-gamble", "Procter & Gamble"), "HD": ("home-depot", "Home Depot"), "ORCL": ("oracle", "Oracle"),
    "COST": ("costco", "Costco"), "CVX": ("chevron", "Chevron"), "KO": ("coca-cola", "Coca-Cola"),
    "PEP": ("pepsico", "PepsiCo"), "BAC": ("bank-of-america", "Bank of America"), "INTC": ("intel", "Intel"),
    "CSCO": ("cisco", "Cisco"), "IBM": ("ibm", "IBM"), "GE": ("general-electric", "GE"), "PFE": ("pfizer", "Pfizer"),
    "MRK": ("merck", "Merck"), "T": ("att", "AT&T"), "VZ": ("verizon", "Verizon"), "WFC": ("wells-fargo", "Wells Fargo"),
    "C": ("citigroup", "Citigroup"), "AIG": ("aig|american-international-group", "AIG"), "MO": ("altria-group", "Altria"),
    "PM": ("philip-morris", "Philip Morris"), "ABBV": ("abbvie", "AbbVie"), "NFLX": ("netflix", "Netflix"),
    "AMD": ("amd", "AMD"), "CRM": ("salesforce", "Salesforce"), "ADBE": ("adobe", "Adobe"),
    "QCOM": ("qualcomm", "Qualcomm"), "TXN": ("texas-instruments", "Texas Instruments"), "CMCSA": ("comcast", "Comcast"),
    "DIS": ("walt-disney", "Disney"), "MCD": ("mcdonald", "McDonald's"), "NKE": ("nike", "Nike"),
    "BA": ("boeing", "Boeing"), "MMM": ("3m", "3M"), "HPQ": ("hp", "HP"), "DELL": ("dell", "Dell"),
    "PLTR": ("palantir", "Palantir"), "MU": ("micron-technology", "Micron"), "ABT": ("abbott-laboratories", "Abbott"),
    "TMO": ("thermo-fisher-scientific", "Thermo Fisher"), "AMGN": ("amgen", "Amgen"), "GS": ("goldman-sachs", "Goldman Sachs"),
    "MS": ("morgan-stanley", "Morgan Stanley"), "AXP": ("american-express", "American Express"),
    "COP": ("conocophillips", "ConocoPhillips"), "SLB": ("schlumberger", "Schlumberger"), "BMY": ("bristol-myers-squibb", "Bristol-Myers"),
    "LIN": ("linde", "Linde"), "ACN": ("accenture", "Accenture"), "NOW": ("servicenow", "ServiceNow"),
    "ISRG": ("intuitive-surgical", "Intuitive Surgical"), "UPS": ("ups", "UPS"), "CAT": ("caterpillar", "Caterpillar"),
    "HON": ("honeywell", "Honeywell"), "LOW": ("lowes-companies|lowe-s|lowes", "Lowe's"), "SBUX": ("starbucks", "Starbucks"),
    "BKNG": ("booking-holdings", "Booking"), "PYPL": ("paypal", "PayPal"), "UBER": ("uber", "Uber"),
    "MDT": ("medtronic", "Medtronic"), "GILD": ("gilead-sciences", "Gilead"), "DHR": ("danaher", "Danaher"),
    "LMT": ("lockheed-martin", "Lockheed Martin"), "RTX": ("raytheon-technologies", "RTX"), "SPGI": ("sp-global", "S&P Global"),
    "BLK": ("blackrock", "BlackRock"), "SCHW": ("charles-schwab", "Charles Schwab"), "NEE": ("nextera-energy", "NextEra Energy"),
    "TMUS": ("t-mobile-us", "T-Mobile US"), "COF": ("capital-one", "Capital One"), "ANET": ("arista-networks", "Arista"),
    "AMAT": ("applied-materials", "Applied Materials"), "LRCX": ("lam-research", "Lam Research"), "KLAC": ("kla", "KLA"),
    "APP": ("applovin", "AppLovin"), "MRVL": ("marvell-technology|marvell-technology-group|marvell", "Marvell"), "HPE": ("hewlett-packard-enterprise", "HPE"),
    "F": ("ford", "Ford"), "GM": ("general-motors", "GM"), "EBAY": ("ebay", "eBay"), "YHOO": ("yahoo|altaba", "Yahoo"),
    "MDLZ": ("mondelez", "Mondelez"), "CL": ("colgate-palmolive", "Colgate"), "TGT": ("target", "Target"),
    "USB": ("us-bancorp", "U.S. Bancorp"), "EMC": ("emc-corporation|emc", "EMC"), "TWX": ("time-warner", "Time Warner"),
    "DOW": ("dow", "Dow"), "DD": ("dupont-de-nemours", "DuPont"), "ELV": ("elevance-health", "Elevance"),
    "CVS": ("cvs-health", "CVS Health"), "VRTX": ("vertex-pharmaceuticals", "Vertex"), "REGN": ("regeneron-pharmaceuticals", "Regeneron"),
    "TSM": ("tsmc", "TSMC"), "ASML": ("asml", "ASML"), "NVO": ("novo-nordisk", "Novo Nordisk"), "SHEL": ("shell", "Shell"),
    "BABA": ("alibaba", "Alibaba"), "TM": ("toyota", "Toyota"),
    # 1990년대 말~2000년대 초 상위권 (사이트에 없으면 건너뛴다)
    "LU": ("lucent-technologies|lucent", "Lucent"), "AOL": ("aol|america-online", "AOL"),
    "FNMA": ("fannie-mae", "Fannie Mae"), "SBC": ("sbc-communications", "SBC"), "WCOM": ("worldcom|mci-worldcom", "WorldCom"),
    "SUNW": ("sun-microsystems", "Sun Microsystems"), "TYC": ("tyco-international|tyco", "Tyco"),
    "NT": ("nortel-networks|nortel", "Nortel"), "VIAB": ("viacom|paramount-global", "Viacom"),
}
# 미국 회사가 아닌 후보 (미국에 상장만) — 화면에서 '미국 회사만' 을 고르면 빠진다
FOREIGN = {"TSM", "ASML", "NVO", "SHEL", "BABA", "TM", "NT"}

CUT = re.compile(r"\s+(Common Stock|Class [A-Z]\b|Ordinary Shares|American Depositary|Capital Stock|Depositary Shares|"
                 r"New York Registry|Units?\b|Warrants?\b).*$", re.I)
TAIL = re.compile(r"[,\s]+(Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.?|Ltd\.?|Limited|plc|PLC|N\.V\.|S\.A\.|"
                  r"AG|SE|A/S|L\.P\.|LP|Holdings?|Group|\(The\)|\(DE\)|\(new\))$", re.I)
SKIP = re.compile(r"\b(Warrant|Rights?|Units?|Preferred|Depositary Shares? .*Pref|Notes? due|% )\b", re.I)


def log(*a):
    print(*a, flush=True)


def get(url, extra=None, tries=3, wait=3):
    h = {"User-Agent": UA, "Accept": "application/json, text/html, */*", "Accept-Language": "en-US,en;q=0.9"}
    h.update(extra or {})
    for t in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60).read().decode("utf-8", "replace")
        except Exception:                          # noqa: BLE001
            if t == tries - 1:
                raise
            time.sleep(wait + 5 * t if wait <= 3 else wait * (t + 1))


def short(name):
    s = CUT.sub("", (name or "").strip())
    for _ in range(3):
        s = TAIL.sub("", s).strip(" ,")
        s = re.sub(r"\s+(&|and)$", "", s)
    return s or name


def num(x):
    try:
        return float(str(x).replace(",", "").replace("$", "") or 0)
    except ValueError:
        return 0.0


# ------------------------------------------------------------ 매일: 지금 시가총액

def screener():
    j = json.loads(get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true",
                       {"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"},
                       tries=6, wait=20))      # 나스닥이 가끔 403 을 낸다 (2026-11-11 한 번) — 20·40·60…초 쉬며 다시
    rows = (j.get("data") or {}).get("rows") or []
    best = {}
    for r in rows:
        cap = num(r.get("marketCap"))
        sym = (r.get("symbol") or "").strip().replace("/", "-").replace("^", "-")
        if cap <= 0 or not sym or SKIP.search(r.get("name") or ""):
            continue
        nm = short(r.get("name"))
        key = nm.lower()
        if key not in best or cap / 1e8 > best[key]["cap"]:   # 주식 종류가 여럿이면 큰 쪽 하나
            best[key] = {"code": sym, "raw": (r.get("symbol") or "").strip(), "name": nm, "cap": round(cap / 1e8, 1),
                         "price": num(r.get("lastsale")), "sector": r.get("sector") or "",
                         "industry": r.get("industry") or "", "country": r.get("country") or "",
                         "chg": num(r.get("pctchange", "").replace("%", "")) if r.get("pctchange") else None,
                         "date": None}
    return sorted(best.values(), key=lambda x: -x["cap"])


def last_us_close(now_kst):
    """가장 최근에 끝난 미국 정규장 날짜 (뉴욕 16시 마감, 주말 건너뜀. 공휴일은 무시)."""
    ny = now_kst.astimezone(timezone(timedelta(hours=-5)))       # 대략 ET (서머타임 1시간 차이는 마감 판정에만 영향)
    d = ny.date() if ny.hour >= 16 else ny.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def screener_cmc():
    """나스닥이 막힌 날의 대신: companiesmarketcap 전 세계 시총 표(CSV). 섹터·업종은 전날 파일에서 가져온다.
    미국에 상장된 것(종목 코드에 '.' 이 없는 것)만 쓴다 — 아람코 2222.SR 같은 해외 상장은 뺀다."""
    import csv
    import io
    try:
        with open(OUT_MCAP, encoding="utf-8") as f:
            prev = json.load(f).get("stocks") or {}
    except Exception:                              # noqa: BLE001
        prev = {}
    txt = get("https://companiesmarketcap.com/?download=csv", tries=4, wait=10)
    # 전날 나스닥 표에 있던 종목만 쓴다 — companiesmarketcap 에는 장외(OTC) ADR(텐센트 TCEHY 등)도 섞여 있다.
    # 같은 회사가 다른 주식 종류로 올라 있으면(구글 GOOG↔GOOGL, 버크셔 BRK-A↔BRK-B) 전날 코드로 맞춘다
    first = {}
    for code, v in prev.items():
        w = (v.get("n") or "").split(" ")[0].lower()
        first.setdefault(w, []).append(code)
    best = {}
    for r in csv.DictReader(io.StringIO(txt)):
        k = {(kk or "").strip().lower(): v for kk, v in r.items()}
        sym = (k.get("symbol") or "").strip().upper()
        cap = num(k.get("marketcap"))
        if not sym or "." in sym or cap <= 0 or SKIP.search(k.get("name") or ""):
            continue
        if sym not in prev:
            w = (k.get("name") or "").split(" ")[0].lower()
            cand = [c for c in first.get(w, []) if c.split("-")[0][:3] == sym.split("-")[0][:3]
                    and 0.5 < cap / 1e8 / max(prev[c].get("c") or 1, 1) < 2]
            if len(cand) != 1:
                continue
            sym = cand[0]
        nm = short(k.get("name"))
        pv = prev.get(sym) or {}
        key = nm.lower()
        if key not in best or cap / 1e8 > best[key]["cap"]:
            best[key] = {"code": sym, "raw": sym, "name": pv.get("n") or nm, "cap": round(cap / 1e8, 1),
                         "price": num(k.get("price (usd)") or k.get("price")), "sector": pv.get("s") or "",
                         "industry": pv.get("i") or "",
                         "country": "United States" if (k.get("country") or "").strip() in ("United States", "USA") else (k.get("country") or "").strip(),
                         "chg": None, "date": None}
    return sorted(best.values(), key=lambda x: -x["cap"])


CLOSED = re.compile(r"Closed at ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})")


def latest_close(raw_sym):
    """종목별 시세에서 가장 최근 정규장 종가와 그 날짜 → (가격, 'YYYY-MM-DD') 또는 None.
    장 전·장 중·장 후 어느 때든 'Closed at Oct 30, 2026 4:00 PM ET' 처럼 날짜가 붙은 칸을 쓴다."""
    sym = raw_sym.replace("/", ".").replace("^", ".")
    j = json.loads(get("https://api.nasdaq.com/api/quote/%s/info?assetclass=stocks" % urllib.request.quote(sym),
                       {"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}, tries=2))
    d = j.get("data") or {}
    for part in ("primaryData", "secondaryData"):
        p = d.get(part) or {}
        m = CLOSED.search(p.get("lastTradeTimestamp") or "")
        price = num(p.get("lastSalePrice"))
        if m and price > 0:
            day = datetime.strptime("%s %s %s" % m.groups(), "%b %d %Y").strftime("%Y-%m-%d")
            return price, day
    return None


def refresh(rows):
    """시총 상위 FIX_TOP 종목을 최신 종가로 다시 계산한다 (rows 를 고친다).
    돌려주는 것: (기준일, 요약). 기준일은 고친 종목들의 종가 날짜 중 가장 많은 것."""
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor

    targets = [r for r in rows[:FIX_TOP] if r["price"] > 0]

    def one(r):
        try:
            return r, latest_close(r["raw"]), None
        except Exception as e:                     # noqa: BLE001
            return r, None, repr(e)

    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(one, targets))
    dates, same, fixed, skipped, failed = Counter(), 0, 0, [], []
    for r, q, err in res:
        if not q:
            failed.append(r["code"] + (" (%s)" % err[:60] if err else ""))
            continue
        close, day = q
        dates[day] += 1
        ratio = close / r["price"]
        if abs(ratio - 1) < 0.0005:
            same += 1                                # 검색표 가격이 이미 최신 종가
        if abs(ratio - 1) > FIX_MAX_MOVE:
            skipped.append("%s %.2f→%.2f" % (r["code"], r["price"], close))
            continue
        r["cap"] = round(r["cap"] * ratio, 1)
        r["price"], r["date"] = close, day
        fixed += 1
    got = sum(dates.values())
    if not got or got < len(targets) * 0.5:
        return None, {"fixed": fixed, "failed": failed, "targets": len(targets)}
    asof = dates.most_common(1)[0][0]
    info = {"fixed": fixed, "targets": len(targets), "dates": dict(dates), "screener_fresh": same >= got * 0.8,
            "failed": failed, "skipped": skipped}
    rows.sort(key=lambda x: -x["cap"])
    return asof, info


def groups(rows, field):
    g = {}
    for r in rows:
        if r[field]:
            g.setdefault(r[field], []).append(r)
    out = [{"no": i, "name": k, "short": None, "n": len(v), "sum": round(sum(x["cap"] for x in v)),
            "codes": [x["code"] for x in v[:TOP_GROUP]]} for i, (k, v) in enumerate(g.items())]
    return sorted(out, key=lambda x: -x["sum"])


def daily(dry=False):
    src = "나스닥 종목 검색표 + 종목별 종가 (상위 %d)" % FIX_TOP
    try:
        rows = screener()
    except Exception as e:                         # noqa: BLE001
        # 나스닥이 GitHub 서버를 막는 날(2026-11-11 하루 종일 403) — companiesmarketcap 표로 대신 받는다
        log("!! 나스닥 검색표를 못 받음 (%s) — companiesmarketcap 시총 표로 대신합니다" % str(e)[:80])
        rows = screener_cmc()
        src = "companiesmarketcap 시총 표 (나스닥이 막힌 날)"
    if len(rows) < 1000:
        sys.exit("!! 시총 표가 이상합니다 (%d종목). 파일을 바꾸지 않습니다." % len(rows))
    today = datetime.now(KST)
    before = {r["code"]: r["cap"] for r in rows[:FIX_TOP]}
    if src.startswith("나스닥"):
        asof, info = refresh(rows)
    else:
        asof, info = None, {"fixed": 0, "targets": 0, "failed": []}   # 종목별 시세도 나스닥이라 건너뛴다
    if asof:
        log("최신 종가로 다시 계산: %d/%d종목 · 종가 날짜 %s · 검색표가 이미 최신%s"
            % (info["fixed"], info["targets"], info["dates"], "이었음" if info["screener_fresh"] else " 아니었음 (하루 늦은 값)"))
        if info["skipped"]:
            log("  ! 가격 차이가 너무 커서 그대로 둔 종목: %s" % ", ".join(info["skipped"]))
    elif not src.startswith("나스닥"):
        asof = last_us_close(today)
        log("  기준일 = 가장 최근 미국 장 마감 %s" % asof)
    else:
        asof = (today - timedelta(hours=16)).strftime("%Y-%m-%d")
        log("  ! 종목별 시세를 충분히 받지 못했습니다 (%d/%d) — 검색표 값 그대로, 기준일은 짐작(%s)"
            % (info["fixed"], info["targets"], asof))
    if info.get("failed"):
        log("  시세 못 받은 종목 %d개: %s" % (len(info["failed"]), ", ".join(info["failed"][:10])))
    if dry:
        log("\n[시험 실행 — 파일은 바꾸지 않음] 기준일 %s" % asof)
        for i, r in enumerate(rows[:10], 1):
            log("  %2d %-6s %-28s %10s  (검색표 %s, 종가 %s)" % (i, r["code"], r["name"][:28], fmt(r["cap"]),
                                                       fmt(before.get(r["code"], r["cap"])), r["date"] or "-"))
        return rows, asof, info
    us_only = [r for r in rows if r["country"] in ("United States", "")]
    keep = rows[:TOP] + [r for r in us_only[:TOP] if r not in rows[:TOP]]
    for kind in ("sector", "industry"):
        for gg in groups(rows, kind)[:200]:
            keep += [r for r in rows if r["code"] in gg["codes"]]
    stocks = {r["code"]: {"n": r["name"], "c": r["cap"], "y": None, "s": r["sector"], "i": r["industry"],
                          "f": r["country"] not in ("United States", "")} for r in keep}
    out = {"updated": today.strftime("%Y-%m-%d"), "asof": asof,
           "unit": "억달러", "source": src,
           "fix": {k: info.get(k) for k in ("fixed", "targets", "dates", "screener_fresh")},
           "us": [{"code": r["code"], "name": r["name"], "cap": r["cap"], "ytd": None} for r in rows[:TOP]],
           "us_only": [{"code": r["code"], "name": r["name"], "cap": r["cap"], "ytd": None} for r in us_only[:TOP]],
           "groups": {"sector": groups(rows, "sector"), "industry": groups(rows, "industry")},
           "stocks": stocks}
    os.makedirs("data", exist_ok=True)
    with open(OUT_MCAP, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log("저장 %s · 전 종목 %d · 1~5위 %s" % (OUT_MCAP, len(rows), " · ".join("%s %s" % (r["code"], fmt(r["cap"])) for r in rows[:5])))
    log("  섹터 %d개 · 업종 %d개" % (len(out["groups"]["sector"]), len(out["groups"]["industry"])))

    # 시총 순위 탭의 '현재' 칸에도 미국을 넣는다
    try:
        rk = json.load(open(OUT_RANK, encoding="utf-8"))
    except Exception:                              # noqa: BLE001
        rk = {"cols": {}}
    now = rk.setdefault("cols", {}).setdefault("now", {"date": out["asof"], "src": "nasdaq"})
    now["us"] = [[r["code"], r["name"], r["cap"]] for r in rows[:TOP_RANK]]
    now["us_only"] = [[r["code"], r["name"], r["cap"]] for r in us_only[:TOP_RANK]]
    now["us_date"] = out["asof"]
    with open(OUT_RANK, "w", encoding="utf-8") as f:
        json.dump(rk, f, ensure_ascii=False, separators=(",", ":"))
    log("  시총 순위 '현재' 칸에 미국 %d개" % len(now["us"]))


def fmt(c):
    return ("%.1f조$" % (c / 10000)) if c >= 10000 else ("%s억$" % format(round(c), ","))


# ------------------------------------------------------------ 한 번: 과거 연말

def cmc_years(slugs):
    """주소 이름 후보를 차례로 — 연도별 표를 읽은 것을 쓴다. 표가 있는 것만 _cmc/ 에 남긴다."""
    os.makedirs(CACHE, exist_ok=True)
    last = "표 없음"
    for slug in slugs.split("|"):
        path = os.path.join(CACHE, slug + ".html")
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            h = open(path, encoding="utf-8").read()
        else:
            try:
                h = get("https://companiesmarketcap.com/%s/marketcap/" % slug, tries=1)
            except Exception as e:                 # noqa: BLE001
                last = "%s: %r" % (slug, e)
                time.sleep(1)
                continue
            time.sleep(1.5)
        out = {}
        for y, v in re.findall(r"<td[^>]*>\s*((?:19|20)\d\d)\s*</td>\s*<td[^>]*>\s*\$?\s*([\d.,]+\s*[TBM])", h):
            n, u = float(v[:-1].replace(",", "")), v.strip()[-1]
            out[int(y)] = round(n * {"T": 1e4, "B": 10, "M": 0.01}[u], 1)     # 억 달러
        if out:
            if not os.path.exists(path):
                open(path, "w", encoding="utf-8").write(h)
            return out
        last = "%s: 표 없음" % slug
    raise RuntimeError(last)


def year_end_fx():
    """미 연준(FRED) 원/달러 환율(DEXKOUS) — 해마다 마지막 값"""
    txt = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXKOUS")
    out = {}
    for line in txt.splitlines()[1:]:
        p = line.split(",")
        if len(p) == 2 and p[1] not in ("", "."):
            try:
                out[int(p[0][:4])] = round(float(p[1]), 2)      # 날짜 순이라 마지막 값이 남는다
            except ValueError:
                pass
    if len(out) < 10:
        raise RuntimeError("환율 표가 이상합니다")
    return out


def history():
    this_year = datetime.now(KST).year
    only_redo = set()
    caps, bad = {}, []
    for i, (sym, (slug, nm)) in enumerate(CANDIDATES.items(), 1):
        if sym in only_redo:
            for sl in slug.split("|"):
                pth = os.path.join(CACHE, sl + ".html")
                if os.path.exists(pth):
                    os.remove(pth)
        try:
            ys, why = cmc_years(slug), ""
        except Exception as e:                     # noqa: BLE001
            ys, why = {}, str(e)
        if not ys:
            bad.append("%s(%s): %s" % (sym, slug, why))
            continue
        caps[sym] = ys
        if i % 20 == 0:
            log("  %d/%d …" % (i, len(CANDIDATES)))
    try:
        rk = json.load(open(OUT_RANK, encoding="utf-8"))
    except Exception:                              # noqa: BLE001
        rk = {"cols": {}}
    cols = rk.setdefault("cols", {})
    years = sorted({y for v in caps.values() for y in v if y < this_year})
    for y in years:
        allr = sorted(((s, CANDIDATES[s][1], v[y]) for s, v in caps.items() if y in v), key=lambda r: -r[2])
        col = cols.setdefault(str(y), {"date": "%d-12-31" % y, "src": "cmc"})
        col["us"] = [[s, n, c] for s, n, c in allr[:TOP_RANK]]
        col["us_only"] = [[s, n, c] for s, n, c in allr if s not in FOREIGN][:TOP_RANK]
        col["us_date"] = "%d-12-31" % y
        top = col["us"][:3]
        log("  %d  %s" % (y, " · ".join("%s %s" % (r[1], fmt(r[2])) for r in top)))
    # 해마다 연말 환율 (시가총액 탭에서 미국 합계를 그해 환율로 원화 환산할 때)
    try:
        fx = year_end_fx()
        for y, v in fx.items():
            if str(y) in cols:
                cols[str(y)]["usdkrw"] = v
        log("  연말 환율 %d개 해 (예: 2000년 %s원 · 2025년 %s원)" % (len(fx), fx.get(2000, "-"), fx.get(2025, "-")))
    except Exception as e:                         # noqa: BLE001
        log("  ! 연말 환율을 받지 못했습니다 (%r) — 과거 연도 원화 환산은 빠집니다" % e)
    with open(OUT_RANK, "w", encoding="utf-8") as f:
        json.dump(rk, f, ensure_ascii=False, separators=(",", ":"))
    log("\n후보 %d곳 중 %d곳 받음 · 연도 %d개(%s~%s) → %s" % (len(CANDIDATES), len(caps), len(years),
                                                    years[0] if years else "-", years[-1] if years else "-", OUT_RANK))
    if bad:
        log("못 받은 후보 %d곳 (주소 이름이 다를 수 있음):\n  %s" % (len(bad), "\n  ".join(bad)))
    ig = open(".gitignore", encoding="utf-8").read() if os.path.exists(".gitignore") else ""
    if "/_cmc/" not in ig.split():
        open(".gitignore", "a", encoding="utf-8").write(("" if ig.endswith("\n") or not ig else "\n") + "/_cmc/\n")


# ── 6월 말(반기 말) — 변천사 영상용 → data/rank_half.json 의 us·us_only ─────────────────────
# 회사 페이지의 차트 자료 data = [{"d": 유닉스시각, "m": 시총}, ...] (매달 하나) 에서 해마다 6월 마지막 값을 쓴다.
OUT_HALF = os.path.join("data", "rank_half.json")
JUNE_FX_OLD = {1996: 810.7, 1997: 888.1, 1998: 1373.6}   # 한국은행 6월 말 원/달러 (유럽중앙은행 자료가 1999년부터라)


def cmc_page(slugs):
    """연도별 표가 있는 회사 페이지 (받아 둔 것 먼저)"""
    os.makedirs(CACHE, exist_ok=True)
    for slug in slugs.split("|"):
        path = os.path.join(CACHE, slug + ".html")
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            return open(path, encoding="utf-8").read()
        try:
            h = get("https://companiesmarketcap.com/%s/marketcap/" % slug, tries=1)
        except Exception:                          # noqa: BLE001
            time.sleep(1)
            continue
        time.sleep(1.5)
        if '"d":' in h:
            open(path, "w", encoding="utf-8").write(h)
            return h
    return ""


def cmc_monthly(h):
    """[(날짜, 시총 원래 단위)] — 차트 자료"""
    return [(datetime.fromtimestamp(int(d), timezone.utc).date(), int(m))
            for d, m in re.findall(r'\{\s*"d"\s*:\s*(\d{9,10})\s*,\s*"m"\s*:\s*(\d+)\s*\}', h)]


def june_fx(years):
    out = {}
    for y in years:
        if y in JUNE_FX_OLD:
            out[y] = JUNE_FX_OLD[y]
            continue
        try:
            j = json.loads(get("https://api.frankfurter.app/%d-06-30?from=USD&to=KRW" % y, tries=2))
            out[y] = round(float(j["rates"]["KRW"]), 2)
        except Exception as e:                     # noqa: BLE001
            log("  ! %d년 6월 말 환율 못 받음 (%r)" % (y, e))
        time.sleep(0.3)
    return out


def half(only_if_needed=False):
    today = datetime.now(KST).date()
    last = today.year if (today.month, today.day) > (7, 1) else today.year - 1
    try:
        hj = json.load(open(OUT_HALF, encoding="utf-8"))
    except Exception:                              # noqa: BLE001
        hj = {"cols": {}}
    hcols = hj.setdefault("cols", {})
    if only_if_needed and (hcols.get(str(last)) or {}).get("us"):
        log("미국 6월 말: %d년까지 이미 있음 — 할 일 없음" % last)
        return
    caps, units, bad = {}, [], []
    for i, (sym, (slug, nm)) in enumerate(CANDIDATES.items(), 1):
        h = cmc_page(slug)
        pts = cmc_monthly(h) if h else []
        if not pts:
            bad.append(sym)
            continue
        # 단위 맞추기: 같은 페이지의 연도별 표(억 달러)와 12월 값을 견준다
        tab = {}
        for y, v in re.findall(r"<td[^>]*>\s*((?:19|20)\d\d)\s*</td>\s*<td[^>]*>\s*\$?\s*([\d.,]+\s*[TBM])", h):
            n, u = float(v[:-1].replace(",", "")), v.strip()[-1]
            tab[int(y)] = n * {"T": 1e4, "B": 10, "M": 0.01}[u]
        for d, m in pts:
            if d.month == 12 and d.year in tab and m:
                units.append(tab[d.year] / m)
        caps[sym] = pts
        if i % 25 == 0:
            log("  %d/%d …" % (i, len(CANDIDATES)))
    if not units:
        sys.exit("!! 차트 자료의 단위를 맞추지 못했습니다")
    units.sort()
    u = units[len(units) // 2]                      # 가운데 값 (보통 0.001 = 시총 m 이 10만 달러 단위)
    log("단위: m × %.6g = 억 달러 (견준 값 %d개, 범위 %.4g~%.4g)" % (u, len(units), units[0], units[-1]))
    years = list(range(1996, last + 1))
    fx = june_fx(years)
    for y in years:
        rows = []
        for sym, pts in caps.items():
            jun = [(d, m) for d, m in pts if d.year == y and d.month == 6]
            if not jun:                              # 6월 값이 없으면 6월 15일~7월 15일 사이 가장 가까운 것
                near = [(abs((d - datetime(y, 6, 30).date()).days), d, m) for d, m in pts if d.year == y and d.month in (6, 7)]
                near = [x for x in near if x[0] <= 15]
                jun = [(x[1], x[2]) for x in sorted(near)[:1]]
            if jun:
                d, m = max(jun)
                if m > 0:
                    rows.append((sym, CANDIDATES[sym][1], round(m * u, 1)))
        if not rows:
            continue
        rows.sort(key=lambda r: -r[2])
        col = hcols.setdefault(str(y), {})
        col["us"] = [list(r) for r in rows[:TOP_RANK]]
        col["us_only"] = [list(r) for r in rows if r[0] not in FOREIGN][:TOP_RANK]
        col["us_date"] = "%d-06-30" % y
        col.setdefault("date", "%d-06-30" % y)
        if y in fx:
            col["usdkrw"] = fx[y]
        log("  %d.06  %s  (환율 %s)" % (y, " · ".join("%s %s" % (r[1], fmt(r[2])) for r in rows[:3]), fx.get(y, "-")))
    hj["updated"] = today.isoformat()
    os.makedirs("data", exist_ok=True)
    with open(OUT_HALF, "w", encoding="utf-8") as f:
        json.dump(hj, f, ensure_ascii=False, separators=(",", ":"))
    log("\n미국 6월 말 %d개 해 → %s%s" % (len([y for y in years if (hcols.get(str(y)) or {}).get("us")]), OUT_HALF,
                                       ("\n차트 자료가 없는 후보 %d곳: %s" % (len(bad), ", ".join(bad))) if bad else ""))


def show():
    j = json.load(open(OUT_MCAP, encoding="utf-8"))
    log("%s 기준 · 상위 10" % j["asof"])
    for i, r in enumerate(j["us"][:10], 1):
        log("  %2d %-6s %-24s %s" % (i, r["code"], r["name"][:24], fmt(r["cap"])))


if __name__ == "__main__":
    if "--show" in sys.argv:
        show()
    elif "--history" in sys.argv:
        history()
    elif "--half" in sys.argv:
        half()
    elif "--half-if-needed" in sys.argv:
        half(only_if_needed=True)
    elif "--dry" in sys.argv:
        daily(dry=True)
    else:
        try:
            daily()
        except urllib.error.HTTPError as e:
            # 나스닥이 GitHub 서버를 막는 날이 있다(2026-11-11 하루 종일 403). 며칠 안 된 파일이면
            # 실패로 표시하지 않고 그대로 둔다 — 사흘 넘게 못 받으면 그때는 실패로 알린다
            try:
                with open(OUT_MCAP, encoding="utf-8") as f:
                    last = json.load(f).get("asof") or ""
                age = (datetime.now(KST).date() - datetime.strptime(last, "%Y-%m-%d").date()).days
            except Exception:                  # noqa: BLE001
                age = 99
            if age <= 3:
                log("!! 나스닥 검색표 %s — %s 자료(%d일 전)를 그대로 둡니다. 다음 실행에서 다시 받습니다." % (e.code, last, age))
                sys.exit(0)
            raise
