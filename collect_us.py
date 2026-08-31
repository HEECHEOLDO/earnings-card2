#!/usr/bin/env python3
"""
SEC EDGAR(XBRL) -> data/us/{티커}.json 수집기
환율 -> data/fx.json

사용법 (설정 없이 바로 실행):
    python3 collect_us.py --verify          # 티커 -> CIK 확인만 (SEC 호출 1회)
    python3 collect_us.py                   # us_tickers.txt 의 종목 수집
    python3 collect_us.py AAPL MSFT         # 종목 직접 지정
    python3 collect_us.py --fx              # 환율만 갱신
    python3 collect_us.py --debug AAPL      # 태그 매칭 과정 출력

SEC API 는 키가 필요 없고 하루 한도도 없습니다.
User-Agent 헤더와 초당 10회 제한만 지키면 됩니다.
표준 라이브러리만 사용합니다.
"""

import io
import json
import os
import sys
import time
import zipfile
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# SEC 는 "이름 이메일" 형식의 User-Agent 를 요구한다.
# 이메일 형식이 없으면 403 을 돌려준다. 아래 주소를 본인 것으로 바꿔두면 가장 안전하다.
# 환경변수 SEC_UA 또는 --ua "이름 메일주소" 로도 지정할 수 있다.
UA = os.environ.get("SEC_UA") or "fincard personal project heecheoldo@gmail.com"

SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json"

OUT_DIR = "data/us"
FX_PATH = "data/fx.json"
CACHE_DIR = ".cache"

YEARS = 10
QUARTERS = 10
SLEEP = 0.15          # 초당 10회 제한 -> 넉넉히 여유

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]

# 회사마다 쓰는 태그가 다르다. 앞에서부터 순서대로 시도한다.
# 같은 뜻이라 합쳐도 되는 태그들.
# 회사는 중간에 태그를 바꾼다. 애플은 FY2017 까지 SalesRevenueNet,
# 그 뒤로 RevenueFromContract... 를 쓴다. 하나만 골라선 10년을 못 채운다.
TAGS = {
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet",
            "RevenuesNetOfInterestExpense", "RevenuesExcludingInterestAndDividends",
            "TotalRevenuesAndOtherIncome"],
    "op":  ["OperatingIncomeLoss"],
    "ni":  ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liab":   ["Liabilities"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "dps": ["CommonStockDividendsPerShareDeclared",
            "CommonStockDividendsPerShareCashPaid"],
}

# 뜻이 달라서 합치면 안 되는 대체 태그. 위쪽이 아예 없을 때만 쓴다.
FALLBACK = {
    "op": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
           "GrossProfit"],
    "ni": ["NetIncomeLossAvailableToCommonStockholdersBasic"],
    "rev": ["InterestAndDividendIncomeOperating", "RevenueMineralSales"],
}

INSTANT = {"assets", "liab", "equity"}     # 시점 데이터 (기간이 아님)

DEBUG = False
_calls = 0


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def dbg(*a):
    if DEBUG:
        log("   ·", *a)


def get(url, tries=3):
    global _calls
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
    })
    last = None
    for i in range(tries):
        try:
            _calls += 1
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
            time.sleep(SLEEP)
            return raw
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return None
            if e.code == 403:
                log("\n! SEC 가 403(거부)을 돌려줬습니다.")
                log("  User-Agent 에 이메일 형식 연락처가 있어야 합니다.")
                log("  현재 값: %s" % UA)
                log("  해결: collect_us.py 위쪽 UA 를 \"이름 본인메일@example.com\" 으로 바꾸거나")
                log("        SEC_UA=\"이름 본인메일@example.com\" python3 collect_us.py 로 실행하세요.")
                sys.exit(1)
            time.sleep(1.5 + i)
        except Exception as e:            # noqa: BLE001
            last = e
            time.sleep(1.5 + i)
    log("  ! 호출 실패:", url.split("/")[-1], last)
    return None


def get_json(url):
    b = get(url)
    if b is None:
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:                     # noqa: BLE001
        return None


# ------------------------------------------------- 티커 -> CIK

def load_cik_map():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.join(CACHE_DIR, "company_tickers.json")
    if not os.path.exists(cached):
        log("company_tickers.json 내려받는 중… (최초 1회)")
        b = get(SEC_TICKERS)
        if b is None:
            sys.exit("티커 목록을 받지 못했습니다.")
        with open(cached, "wb") as f:
            f.write(b)
    with open(cached, encoding="utf-8") as f:
        raw = json.load(f)
    m = {}
    for v in raw.values():
        m[v["ticker"].upper()] = {"cik": "%010d" % int(v["cik_str"]),
                                  "name": v["title"]}
    log("상장사 매핑 %d건" % len(m))
    return m


# ------------------------------------------------- 사실(fact) 추출

def _days(a, b):
    return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days


def fy_of(end):
    """기간 종료일에서 회계연도를 정한다.

    companyfacts 의 fy 필드는 '그 숫자의 연도'가 아니라
    '어느 보고서에 실렸는지'를 뜻한다. 10-K 하나에 3개 연도가 들어 있고
    셋 다 같은 fy 가 붙으므로, 종료일을 기준으로 삼아야 한다.
    """
    d = datetime.strptime(end, "%Y-%m-%d")
    # 1월 초에 끝나는 52/53주 회계연도는 사실상 전년도다 (1월 말 결산은 그대로)
    if d.month == 1 and d.day <= 10:
        return d.year - 1
    return d.year


# 자동 탐색용 — 알려진 태그가 하나도 없을 때 이름으로 찾는다
DISCOVER = {
    "rev": ("revenue",),
    "op": ("operatingincome", "incomelossfromcontinuingoperationsbefore"),
    "ni": ("netincomeloss",),
}
# 매출로 오인하기 쉬운 것들 (부문·이연·미수 등)
DISCOVER_SKIP = ("deferred", "unearned", "receivable", "remaining",
                 "percentage", "concentration", "segment", "peritem")

_used_tag = {}


def _usable(rows, kind):
    """이 태그로 건질 수 있는 연간 데이터가 몇 개인지 센다."""
    n = 0
    for r in rows:
        if not r.get("end"):
            continue
        if kind in INSTANT:
            n += 1
            continue
        if not r.get("start"):
            continue
        try:
            d = _days(r["start"], r["end"])
        except Exception:                 # noqa: BLE001
            continue
        if 330 <= d <= 400:
            n += 1
    return n


def pick_units(facts, kind):
    """해당 항목의 값 목록. 같은 뜻의 태그는 모두 합친다.

    태그가 '있다'고 바로 쓰지 않는다. 이름만 있고 값이 비어 있는 경우가
    흔하고, 회사가 중간에 태그를 바꾸기도 한다.
    """
    us = facts.get("facts", {}).get("us-gaap", {})

    def units_of(node):
        for unit in ("USD", "USD/shares", "USD-per-shares"):
            if unit in node.get("units", {}):
                return unit, node["units"][unit]
        return None, None

    def gather(tags):
        rows, used = [], []
        for tag in tags:
            node = us.get(tag)
            if not node:
                continue
            unit, rs = units_of(node)
            if not rs:
                continue
            n = _usable(rs, kind)
            if n == 0:
                continue
            rows.extend(rs)
            used.append("%s(%d)" % (tag, n))
        return rows, used

    rows, used = gather(TAGS[kind])

    if not rows:
        rows, used = gather(FALLBACK.get(kind, []))

    if not rows:
        keys = DISCOVER.get(kind)
        if keys:
            best, best_n, best_tag = None, 0, None
            for tag, node in us.items():
                low = tag.lower()
                if not any(k in low for k in keys):
                    continue
                if any(x in low for x in DISCOVER_SKIP):
                    continue
                unit, rs = units_of(node)
                if not rs:
                    continue
                n = _usable(rs, kind)
                if n > best_n:
                    best, best_n, best_tag = rs, n, tag
            if best_tag:
                log("  · %s 태그 자동 탐색 -> %s (%d개)" % (kind, best_tag, best_n))
                rows, used = best, ["%s(%d) 자동" % (best_tag, best_n)]

    if rows:
        _used_tag[kind] = " + ".join(used)
        dbg("%s <- %s" % (kind, _used_tag[kind]))
    else:
        dbg("%s <- 없음" % kind)
    return rows or None


def fiscal_end_month(facts):
    """이 회사의 회계연도가 몇 월에 끝나는지 알아낸다.
    연간(약 1년)에 해당하는 값들의 종료월 중 가장 흔한 달."""
    rows = pick_units(facts, "rev") or []
    counts = {}
    for r in rows:
        if not r.get("start") or not r.get("end"):
            continue
        try:
            if not (330 <= _days(r["start"], r["end"]) <= 400):
                continue
        except Exception:                 # noqa: BLE001
            continue
        m = int(r["end"][5:7])
        counts[m] = counts.get(m, 0) + 1
    if not counts:
        return 12
    return max(counts.items(), key=lambda kv: kv[1])[0]


def annual_series(facts, kind):
    """회계연도별 값. {fy: val}

    form 이나 fp 로 거르지 않는다. 회사마다 이 값이 제각각이라
    멀쩡한 데이터가 통째로 날아간다. 기간 길이로만 판단한다.
    """
    rows = pick_units(facts, kind)
    if not rows:
        return {}
    out, seen = {}, {}
    kept = dropped = 0
    for r in rows:
        if not r.get("end"):
            continue
        if kind not in INSTANT:
            if not r.get("start"):
                continue
            d = _days(r["start"], r["end"])
            if d < 330 or d > 400:        # 1년치가 아닌 값 제외
                dropped += 1
                continue
        fy = fy_of(r["end"])
        filed = r.get("filed", "")
        if fy not in seen or filed >= seen[fy]:
            seen[fy] = filed
            out[fy] = r["val"]
        kept += 1
    dbg("%s 연간: 채택 %d, 기간 불일치 %d -> %d개 연도"
        % (kind, kept, dropped, len(out)))
    return out


def quarter_series(facts, kind, fy_end_month=12):
    """분기별 값. {(fy, q): val}

    9월 결산 회사의 12월 분기는 다음 회계연도의 1분기다.
    달력 연도로 묶으면 분기 번호가 통째로 밀린다.
    """
    rows = pick_units(facts, kind)
    if not rows:
        return {}
    byend, seen = {}, {}
    for r in rows:
        if not r.get("start") or not r.get("end"):
            continue
        try:
            d = _days(r["start"], r["end"])
        except Exception:                 # noqa: BLE001
            continue
        if d < 80 or d > 100:             # 3개월치만
            continue
        key = r["end"]
        filed = r.get("filed", "")
        if key not in seen or filed >= seen[key]:
            seen[key] = filed
            byend[key] = r["val"]

    def q_fy(end):
        y, m = int(end[:4]), int(end[5:7])
        return y + 1 if m > fy_end_month else y

    groups = {}
    for end, val in byend.items():
        groups.setdefault(q_fy(end), []).append((end, val))
    out = {}
    for fy, items in groups.items():
        items.sort()
        for i, (end, val) in enumerate(items[:4]):
            out[(fy, i + 1)] = val
    dbg("%s 분기: %d개 (결산 %d월 기준)" % (kind, len(out), fy_end_month))
    return out


def mil(v):
    """달러 -> 백만 달러, 소수 1자리."""
    return None if v is None else round(v / 1e6, 1)


# ------------------------------------------------- 종목 하나

def collect_one(ticker, info):
    log("\n=== %s (%s) ===" % (ticker, info["name"]))
    facts = get_json(SEC_FACTS % info["cik"])
    if not facts:
        return None, "SEC 데이터 없음"

    _used_tag.clear()
    A = {k: annual_series(facts, k) for k in
         ("rev", "op", "ni", "assets", "liab", "equity", "dps")}
    dbg("사용 태그:", _used_tag)
    if not A["rev"]:
        return None, "매출 태그를 못 찾음"

    fys = sorted(A["rev"].keys())[-(YEARS + 1):]
    annual = []
    for fy in fys:
        rev, op = A["rev"].get(fy), A["op"].get(fy)
        if rev is None:
            continue
        annual.append({
            "p": fy, "rev": mil(rev), "op": mil(op), "ni": mil(A["ni"].get(fy)),
            "assets": mil(A["assets"].get(fy)), "liab": mil(A["liab"].get(fy)),
            "equity": mil(A["equity"].get(fy)),
            "dps": A["dps"].get(fy), "payout": None, "yield": None,
        })
        log("  FY%d  매출 %s M$  영업이익 %s M$  DPS %s" % (
            fy, f"{mil(rev):,.0f}",
            (f"{mil(op):,.0f}" if op is not None else "-"),
            (f"${A['dps'][fy]:.2f}" if fy in A["dps"] else "-")))
    annual = annual[-YEARS:]

    # 배당성향 = DPS x 주식수 / 순이익 은 주식수가 필요하므로,
    # 여기서는 순이익 대비 배당총액을 알 수 없어 비워 둔다.
    # (카드에서 배당성향을 쓰지 않으면 문제 없음)

    fem = fiscal_end_month(facts)
    dbg("결산월: %d월" % fem)
    Q = {k: quarter_series(facts, k, fem) for k in ("rev", "op", "ni")}
    quarterly = []
    fys = sorted(set(k[0] for k in Q["rev"].keys()))[-5:]
    for fy in fys:
        have = sorted(q for (y, q) in Q["rev"].keys() if y == fy)
        for q in have:
            quarterly.append({"y": fy, "q": q, "rev": mil(Q["rev"].get((fy, q))),
                              "op": mil(Q["op"].get((fy, q))),
                              "ni": mil(Q["ni"].get((fy, q)))})
        # 4분기를 따로 보고하지 않는 회사는 연간에서 빼서 만든다
        if 4 not in have and have == [1, 2, 3]:
            def q4(key):
                ann = A[key].get(fy)
                parts = [Q[key].get((fy, i)) for i in (1, 2, 3)]
                if ann is None or any(x is None for x in parts):
                    return None
                return ann - sum(parts)
            r4 = q4("rev")
            if r4 is not None:
                quarterly.append({"y": fy, "q": 4, "rev": mil(r4),
                                  "op": mil(q4("op")), "ni": mil(q4("ni"))})
    quarterly.sort(key=lambda x: (x["y"], x["q"]))
    quarterly = [x for x in quarterly if x["rev"] is not None][-QUARTERS:]
    for x in quarterly:
        log("  FY%d %dQ  매출 %s M$" % (x["y"], x["q"], f"{x['rev']:,.0f}"))

    if not annual and not quarterly:
        return None, "쓸 수 있는 데이터 없음"

    return {
        "name": ticker,
        "legal_name": info["name"],
        "code": ticker,
        "cik": info["cik"],
        "market": "미국",
        "currency": "USD",
        "unit": "백만달러",
        "fiscal": True,
        "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
        "annual": annual,
        "quarterly": quarterly,
    }, None


# ------------------------------------------------- 환율

FX_SOURCES = [
    ("frankfurter", "https://api.frankfurter.app/latest?from=USD&to=KRW",
     lambda j: j.get("rates", {}).get("KRW")),
    ("open.er-api", "https://open.er-api.com/v6/latest/USD",
     lambda j: j.get("rates", {}).get("KRW")),
]


def update_fx():
    """USD -> KRW 환율. 실패하면 직전 값을 유지한다."""
    prev = None
    try:
        with open(FX_PATH, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:                     # noqa: BLE001
        pass

    for name, url, pick in FX_SOURCES:
        j = get_json(url)
        if not j:
            continue
        rate = pick(j)
        if rate and 500 < float(rate) < 3000:     # 터무니없는 값 방어
            data = {"usdkrw": round(float(rate), 2),
                    "source": name,
                    "updated": datetime.now(timezone(timedelta(hours=9)))
                    .strftime("%Y-%m-%d")}
            os.makedirs(os.path.dirname(FX_PATH), exist_ok=True)
            with open(FX_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            log("환율 %s원 (%s)" % (data["usdkrw"], name))
            return data
        log("  ? %s 응답이 이상함" % name)

    if prev:
        log("환율 갱신 실패 — 직전 값 %s원 유지" % prev.get("usdkrw"))
        return prev
    log("! 환율을 못 받았고 직전 값도 없습니다.")
    return None


# ------------------------------------------------- 목록 · 인덱스

def load_tickers(args):
    """[(티커, CIK지정or None)] 목록.

    us_tickers.txt 에서 'AAPL' 처럼 티커만 써도 되고,
    'XOM 34088' 처럼 CIK 를 직접 지정할 수도 있다.
    같은 티커를 다른 회사가 물려받은 경우에 쓴다.
    """
    def parse(line):
        parts = line.split()
        t = parts[0].upper()
        cik = None
        if len(parts) > 1 and parts[1].isdigit():
            cik = "%010d" % int(parts[1])
        return (t, cik)

    if args:
        return [parse(a) for a in args]
    path = "us_tickers.txt"
    if os.path.exists(path):
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    out.append(parse(line))
        if out:
            log("us_tickers.txt 에서 %d종목 읽음" % len(out))
            return out
    return [(t, None) for t in DEFAULT_TICKERS]


def rebuild_index():
    items = []
    for fn in sorted(os.listdir(OUT_DIR)):
        if not fn.endswith(".json") or fn.startswith("_") or fn == "index.json":
            continue
        try:
            with open(os.path.join(OUT_DIR, fn), encoding="utf-8") as f:
                d = json.load(f)
            items.append({"name": d.get("name"), "code": d.get("code"),
                          "legal_name": d.get("legal_name", ""),
                          "market": "미국", "updated": d.get("updated", "")})
        except Exception:                 # noqa: BLE001
            continue
    items.sort(key=lambda x: x["code"])
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone(timedelta(hours=9)))
                   .strftime("%Y-%m-%d"), "count": len(items),
                   "companies": items}, f, ensure_ascii=False, indent=1)
    return len(items)


def verify(tickers, cmap):
    ok, bad = [], []
    for t, cik in tickers:
        if cik:
            ok.append((t, "CIK 직접 지정 %s" % cik))
        elif t in cmap:
            ok.append((t, cmap[t]["name"]))
        else:
            bad.append(t)
    log("\n%-10s %s" % ("티커", "SEC 등록명"))
    log("-" * 64)
    for t, name in ok:
        log("%-10s %s" % (t, name))
    if bad:
        log("\n!! SEC 목록에 없는 티커 %d개: %s" % (len(bad), ", ".join(bad)))
        log("   us_tickers.txt 에서 지우거나 철자를 고치세요.")
    log("\n확인됨 %d개 / 못 찾음 %d개 · SEC 호출 %d회" % (len(ok), len(bad), _calls))
    log("\n등록명이 엉뚱하면 'XOM 34088' 처럼 CIK 를 직접 적어주세요.")


def main():
    global DEBUG, UA
    argv = sys.argv[1:]
    if "--ua" in argv:
        i = argv.index("--ua")
        if i + 1 < len(argv):
            UA = argv[i + 1]
            del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    DEBUG = "--debug" in argv
    log("User-Agent: %s" % UA)

    if "--fx" in argv:
        update_fx()
        return

    cmap = load_cik_map()
    tickers = load_tickers(args)

    if "--verify" in argv:
        verify(tickers, cmap)
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    started = time.time()
    report = []

    for i, (t, cik) in enumerate(tickers, 1):
        log("\n[%d/%d]" % (i, len(tickers)))
        info = {"cik": cik, "name": t} if cik else cmap.get(t)
        if not info:
            log("! %s : SEC 목록에 없습니다" % t)
            report.append((t, "실패", 0, 0, "티커 없음"))
            continue
        try:
            data, reason = collect_one(t, info)
        except Exception as e:            # noqa: BLE001
            log("! 예외: %r" % e)
            report.append((t, "실패", 0, 0, "예외 %s" % type(e).__name__))
            continue
        if not data:
            report.append((t, "실패", 0, 0, reason))
            continue
        with open(os.path.join(OUT_DIR, t + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        na, nq = len(data["annual"]), len(data["quarterly"])
        status = "정상" if (na >= YEARS and nq >= QUARTERS) else "부분"
        note = "" if status == "정상" else "연간 %d/%d, 분기 %d/%d" % (na, YEARS, nq, QUARTERS)
        report.append((t, status, na, nq, note))

    fx = update_fx()
    total = rebuild_index()

    log("\n" + "=" * 58)
    log("%-10s %-6s %-5s %-5s %s" % ("티커", "상태", "연간", "분기", "비고"))
    log("-" * 58)
    for t, st, na, nq, note in report:
        log("%-10s %-6s %-5s %-5s %s" % (t, st, na, nq, note))
    log("-" * 58)
    counts = {}
    for r in report:
        counts[r[1]] = counts.get(r[1], 0) + 1
    log("전체 %d종목  |  %s" % (len(report),
        "  ".join("%s %d" % kv for kv in sorted(counts.items()))))
    log("index.json %d종목  |  소요 %.1f분  |  SEC 호출 %d회"
        % (total, (time.time() - started) / 60, _calls))
    if fx:
        log("환율 1 USD = %s KRW (%s)" % (fx["usdkrw"], fx["updated"]))

    bad = [r for r in report if r[1] != "정상"]
    if bad:
        log("\n확인이 필요한 종목: " + ", ".join("%s(%s)" % (r[0], r[1]) for r in bad))


if __name__ == "__main__":
    main()
