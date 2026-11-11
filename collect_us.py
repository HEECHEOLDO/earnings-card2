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
import math
import re
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

# 지수 구성종목 목록 (위키백과). 표 구조가 안정적이고 자주 갱신된다.
INDEX_SOURCES = [
    ("S&P 500", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"),
    ("나스닥 100", "https://en.wikipedia.org/wiki/Nasdaq-100"),
]

# 티커가 다른 법인으로 옮겨간 경우 CIK 를 직접 지정한다
# 법인이 바뀌어 티커가 새 CIK 로 옮겨간 종목.
# '새 CIK 옛 CIK' 순서로 적으면 둘을 합쳐 10년을 채운다.
CIK_OVERRIDE = {
    "XOM": "34088",
    "BLK": "2012383 1364742",
}

BANK_REV = "zzBankTotalRevenue"
# 같은 기간 다른 매출 태그가 1.5배 넘게 크면 앞 태그는 매출 '일부'로 본다
# (번지 54억 vs 238억, 크라운캐슬 0.3억 vs 9.9억, 노던트러스트 13.7억 vs 22.9억).
# 1.5배 아래 차이(주세 포함 여부, 파생상품 손익 등)는 원래 고른 태그를 그대로 쓴다.
REV_PARTIAL = 1.5
REV_FILL = ["OperatingLeaseLeaseIncome"]
PRETAX_SUM = "zzPretaxDomesticPlusForeign"   # 세전이익 = 국내분 + 해외분 (BNY 처럼 둘로만 적는 회사)

# 회사마다 쓰는 태그가 다르다. 앞에서부터 순서대로 시도한다.
# 같은 뜻이라 합쳐도 되는 태그들.
# 회사는 중간에 태그를 바꾼다. 애플은 FY2017 까지 SalesRevenueNet,
# 그 뒤로 RevenueFromContract... 를 쓴다. 하나만 골라선 10년을 못 채운다.
TAGS = {
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet",
            "RevenuesNetOfInterestExpense", "RevenuesExcludingInterestAndDividends",
            "TotalRevenuesAndOtherIncome",
            # 전력·가스 회사 (엑셀에너지는 2019년 이후 이것만 쓴다)
            "RegulatedAndUnregulatedOperatingRevenue",
            # 은행 '매출' = 순이자이익 + 비이자이익. add_bank_revenue() 가 만들어 넣는 가상 태그
            BANK_REV],
    "op":  ["OperatingIncomeLoss"],
    "ni":  ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liab":   ["Liabilities"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "dps": ["CommonStockDividendsPerShareDeclared",
            "CommonStockDividendsPerShareCashPaid"],
    # 배당 지급액(현금흐름표). 달러 금액이라 액면분할과 무관해
    # 주당배당금·주식수가 서로 어긋나도 영향을 받지 않는다.
    "divpaid": ["PaymentsOfDividendsCommonStock",
                "PaymentsOfDividends",
                "PaymentsOfOrdinaryDividends"],
    # 배당성향 계산용 — 미국 공시에는 배당총액이 없어서 주식 수로 역산한다
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding",
               "WeightedAverageNumberOfSharesOutstandingBasic",
               "WeightedAverageNumberOfDilutedSharesOutstandingBasicAndDiluted"],
}

# 뜻이 달라서 합치면 안 되는 대체 태그. 위쪽이 아예 없을 때만 쓴다.
FALLBACK = {
    "op": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
           # ...Domestic / ...Foreign 은 세전이익의 국내·해외 일부라 따로는 쓰지 않는다
           # (엑손 2025 영업이익이 국내분 110억 달러로 나왔다 — 전체 413억). 둘을 더한 값만 쓴다
           PRETAX_SUM,
           "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
           "OperatingIncomeLossBeforeDepreciationDepletionAmortizationAndExplorationExpense"],
    # GrossProfit(매출총이익)은 쓰지 않는다 — 영업이익보다 몇 배 커서 이익률이 엉터리가 된다
    # (나이키 영업이익률이 43%로 나왔다. 실제 약 10%). 영업이익이 없으면 빈칸이 낫다.
    "ni": ["NetIncomeLossAvailableToCommonStockholdersBasic"],
    # 은행·보험·리츠는 '매출'이라는 항목 자체를 안 쓰는 경우가 많다
    "rev": ["InterestAndDividendIncomeOperating",
            "InterestIncomeExpenseNet",
            "InterestIncomeExpenseAfterProvisionForLoanLoss",
            "RevenuesNetOfInterestExpense",
            "PremiumsEarnedNet",
            "RealEstateRevenueNet",
            "RevenueMineralSales"],
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
    "op": ("operatingincome", "incomelossfromcontinuingoperationsbefore",
           "incomebeforeincometax", "incomelossbeforeincometax"),
    "ni": ("netincomeloss",),
}
# 매출로 오인하기 쉬운 것들 (부문·이연·미수 등)
DISCOVER_SKIP = ("deferred", "unearned", "receivable", "remaining",
                 # 인수 가정(pro forma) 매출, 세전이익의 국내·해외 일부 — 회사 전체 값이 아니다
                 # (APA 매출이 인수 가정 매출로, JPM 영업이익이 국내분으로 들어가 있었다)
                 "proforma", "domestic", "foreign",
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
    """해당 항목의 값 목록을 태그별로, 실한 순서대로 돌려준다.

    여러 태그를 뒤섞으면 뜻이 조금씩 다른 값이 섞여 숫자가 틀어진다.
    주력 태그를 먼저 쓰고 빈 해만 다른 태그로 메운다.
    """
    us = facts.get("facts", {}).get("us-gaap", {})
    want = ("shares",) if kind == "shares" else ("USD", "USD/shares", "USD-per-shares")

    def units_of(node):
        for unit in want:
            if unit in node.get("units", {}):
                return unit, node["units"][unit]
        return None, None

    def gather(tags):
        out = []
        for tag in tags:
            node = us.get(tag)
            if not node:
                continue
            unit, rs = units_of(node)
            if not rs:
                continue
            n = _usable(rs, kind)
            if not n and kind not in INSTANT and any(
                    r.get("start") and r.get("end") and 80 <= _days(r["start"], r["end"]) <= 100
                    for r in rs):
                n = 0.5                   # 연간은 아직 없고 분기만 있는 새 태그
            if n:
                out.append((n, tag, rs))
        out.sort(key=lambda x: -x[0])
        return out

    groups = gather(TAGS[kind])
    if not any(n >= 1 for n, _, _ in groups):
        # 연간 값이 있는 주 태그가 없으면 대체 태그를 앞에, 분기만 있는 새 태그는 뒤에
        groups = gather(FALLBACK.get(kind, [])) + groups
    elif FALLBACK.get(kind):
        # 주 태그를 예전에만 쓰고 그만둔 회사: 대체 태그가 1년 넘게 더 최근까지 있으면 대체 태그를 앞에
        # (버크셔: 영업이익 태그는 2013년이 마지막, 세전이익은 지금까지 — 영업이익이 전부 비어 있었다)
        def last_end(gs):
            return max((r.get("end", "") for _, _, rows in gs for r in rows), default="")
        fb = gather(FALLBACK[kind])
        le_main, le_fb = last_end(groups), last_end(fb)
        if fb and le_main and le_fb and le_fb > le_main and _days(le_main, le_fb) > 365:
            have = {t for _, t, _ in fb}
            groups = fb + [g for g in groups if g[1] not in have]
    if kind == "rev" and groups:
        # 빈 기간만 메우는 태그 (리츠 임대수익: 비브마크는 2021년 이후 이것만 쓴다)
        have = {t for _, t, _ in groups}
        groups = groups + [g for g in gather(REV_FILL) if g[1] not in have]
    if kind == "ni" and groups:
        # 순이익은 대체 태그(보통주 귀속 순이익)를 뒤에 붙여 빈 분기만 메운다
        # (부킹홀딩스는 분기 순이익을 그 태그로만 적어 분기 순이익이 전부 비어 있었다)
        have = {t for _, t, _ in groups}
        groups = groups + [g for g in gather(FALLBACK.get(kind, [])) if g[1] not in have]

    if not groups:
        keys = DISCOVER.get(kind)
        if keys:
            cands = []
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
                if n:
                    cands.append((n, tag, rs))
            cands.sort(key=lambda x: -x[0])
            if cands:
                log("  · %s 태그 자동 탐색 -> %s (%d개)" % (kind, cands[0][1], cands[0][0]))
                groups = cands[:1]

    if groups:
        _used_tag[kind] = " > ".join("%s(%d)" % (t, n) for n, t, _ in groups)
        dbg("%s <- %s" % (kind, _used_tag[kind]))
    else:
        dbg("%s <- 없음" % kind)
    return groups


def all_rows(facts, kind):
    """태그 구분 없이 전부 이어붙인 목록 (기간 판단 등 보조용)."""
    out = []
    for _, _, rows in pick_units(facts, kind) or []:
        out.extend(rows)
    return out


def fiscal_end_month(facts):
    """이 회사의 회계연도가 몇 월에 끝나는지 알아낸다.
    연간(약 1년)에 해당하는 값들의 종료월 중 가장 흔한 달."""
    rows = all_rows(facts, "rev")
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

    앞선 태그가 값을 가진 해는 그대로 두고, 없는 해만 뒤 태그로 채운다.
    """
    groups = pick_units(facts, kind)
    if not groups:
        return {}
    out = {}
    kept = dropped = 0
    for _, _, rows in groups:
        one, seen = {}, {}
        for r in rows:
            if not r.get("end"):
                continue
            if kind not in INSTANT:
                if not r.get("start"):
                    continue
                try:
                    d = _days(r["start"], r["end"])
                except Exception:         # noqa: BLE001
                    continue
                if d < 330 or d > 400:
                    dropped += 1
                    continue
            fy = fy_of(r["end"])
            filed = r.get("filed", "")
            if fy not in seen or filed >= seen[fy]:
                seen[fy] = filed
                one[fy] = r["val"]
            kept += 1
        for fy, v in one.items():
            if kind == "rev" and fy in out and v is not None and out[fy] is not None:
                if v > out[fy] * REV_PARTIAL:
                    out[fy] = v               # 앞 태그가 매출 일부만 적은 경우 (리츠의 고객계약수익 등)
            else:
                out.setdefault(fy, v)         # 앞 태그 우선
    dbg("%s 연간: 채택 %d, 기간 불일치 %d -> %d개 연도" % (kind, kept, dropped, len(out)))
    return out


def quarter_series(facts, kind, fy_end_month=12):
    """분기별 값. {(fy, q): val}"""
    groups = pick_units(facts, kind)
    if not groups:
        return {}
    byend, tagof = {}, {}
    for _, tag, rows in groups:
        seen = {}
        one = {}
        for r in rows:
            if not r.get("start") or not r.get("end"):
                continue
            try:
                d = _days(r["start"], r["end"])
            except Exception:             # noqa: BLE001
                continue
            if d < 80 or d > 100:
                continue
            key = r["end"]
            filed = r.get("filed", "")
            if key not in seen or filed >= seen[key]:
                seen[key] = filed
                one[key] = r["val"]
        for k, v in one.items():
            if kind == "rev" and k in byend and v is not None and byend[k] is not None:
                if v > byend[k] * REV_PARTIAL:
                    byend[k], tagof[k] = v, tag
            elif k not in byend:
                byend[k], tagof[k] = v, tag

    def q_fy(end):
        y, m = int(end[:4]), int(end[5:7])
        return y + 1 if m > fy_end_month else y

    groups2 = {}
    for end, val in byend.items():
        groups2.setdefault(q_fy(end), []).append((end, val))
    out = {}
    for fy, items in groups2.items():
        items.sort()
        for i, (end, val) in enumerate(items[:4]):
            out[(fy, i + 1)] = val
            QTAG[(kind, fy, i + 1)] = tagof.get(end)
    dbg("%s 분기: %d개 (결산 %d월 기준)" % (kind, len(out), fy_end_month))
    return out


QTAG = {}       # (항목, 회계연도, 분기) -> 그 값을 가져온 태그


def annual_of_tag(facts, tag, fy):
    """특정 태그의 연간 값 (4분기를 '연간 - 1~3분기'로 만들 때 같은 태그끼리 빼려고)."""
    if tag == BANK_REV:
        node = (facts.get("facts", {}).get("us-gaap", {}) or {}).get(BANK_REV)
    else:
        node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return None
    best, seen = None, ""
    for r in node.get("units", {}).get("USD", []):
        if not r.get("start") or not r.get("end"):
            continue
        try:
            if not 330 <= _days(r["start"], r["end"]) <= 400:
                continue
        except Exception:                 # noqa: BLE001
            continue
        if fy_of(r["end"]) == fy and r.get("filed", "") >= seen:
            best, seen = r["val"], r.get("filed", "")
    return best


def mil(v):
    """달러 -> 백만 달러, 소수 1자리."""
    return None if v is None else round(v / 1e6, 1)


# ------------------------------------------------- 종목 하나

def normalize_shares(shares):
    """주식 수 단위를 맞춘다.

    같은 회사가 어떤 해는 '주', 어떤 해는 '백만 주'로 공시하는 경우가 있다.
    연도별 값이 서로 비슷해지도록 1000의 거듭제곱으로 눈금을 맞춘다.
    """
    vals = [v for v in shares.values() if v and v > 0]
    if len(vals) < 2:
        return shares
    # 가장 큰 값을 기준으로 삼는다. 단위가 섞이면 '주' 단위 쪽이 크고,
    # 그게 실제 주식 수이므로 작은 쪽을 끌어올려야 한다.
    med = max(vals)
    out = {}
    for fy, v in shares.items():
        if not v or v <= 0:
            out[fy] = v
            continue
        best, bestdiff = v, abs(math.log10(v / med))
        for e in (-6, -3, 3, 6):
            cand = v * (10 ** e)
            diff = abs(math.log10(cand / med))
            if diff < bestdiff:
                best, bestdiff = cand, diff
        out[fy] = best
    return out


def find_restatement(annual):
    """사업 분할 등으로 과거 실적 기준이 바뀐 지점을 찾는다.

    SEC 에는 원본과 재작성본이 모두 있고 우리는 최근 제출본을 쓴다.
    그런데 재작성이 최근 몇 년만 이뤄지면 그 앞뒤로 기준이 갈려
    매출이 갑자기 20% 넘게 꺾인 것처럼 보인다.
    """
    for i in range(len(annual) - 1, 0, -1):
        a, b = annual[i - 1].get("rev"), annual[i].get("rev")
        if not a or not b or a <= 0:
            continue
        drop = (a - b) / a
        if drop >= 0.14:                  # 한 해 만에 14% 넘게 감소
            # 앞뒤 모두 안정적이어야 '기준이 바뀐 것'이다.
            # 경기민감주처럼 원래 오르내리는 회사와 구분하기 위함.
            before = [x.get("rev") for x in annual[:i] if x.get("rev")]
            after = [x.get("rev") for x in annual[i:] if x.get("rev")]
            if len(before) < 2 or len(after) < 2:
                continue
            if max(before) / min(before) < 1.35 and max(after) / min(after) < 1.20:
                return annual[i]["p"]
    return None


def payout_of(fy, A):
    """배당성향(%) = 주당배당금 x 주식수 / 순이익.

    미국 공시에는 배당총액 항목이 없어서 주식 수로 역산한다.
    """
    ni = A["ni"].get(fy)
    if not ni or ni <= 0:
        return None

    paid = A.get("divpaid", {}).get(fy)
    if paid:
        v = abs(paid) / ni * 100          # 현금흐름표는 음수로 적히기도 한다
    else:
        dps, sh = A["dps"].get(fy), A["shares"].get(fy)
        if not dps or not sh or sh <= 0:
            return None
        v = dps * sh / ni * 100
    # 일회성 손실로 순이익이 급감한 해는 배당성향이 수백 %가 되기도 한다.
    # (코카콜라 2017 세제개편, 알트리아 JUUL 상각 등) 그것도 사실이므로 살린다.
    # 다만 자릿수가 어긋난 수준(2000% 초과)은 데이터 오류로 보고 버린다.
    if v <= 0 or v > 2000:
        return None
    return round(v, 1)


CLEAN_RATIOS = [2, 3, 4, 5, 7, 10, 20]


def fix_dps_scale(annual, A):
    """주당배당금이 연간 값이 아닌 해를 찾아 바로잡는다.

    분기 배당금이 연간 자리에 들어가는 일이 잦다.
    같은 해의 '배당 지급액 ÷ 주식 수' 와 대조하면 몇 배 어긋났는지 알 수 있다.
    깔끔한 배수(2·4·10 등)로 어긋날 때만 고친다.
    """
    paid, sh = A.get("divpaid", {}), A.get("shares", {})

    # 먼저 연도별로 '지급액 ÷ 주식수' 가 주당배당금의 몇 배인지 잰다
    ratios = {}
    for r in annual:
        y = r["p"]
        dv, pv, s2 = r.get("dps"), paid.get(y), sh.get(y)
        if dv and pv and s2 and s2 > 0 and dv > 0:
            ratios[y] = abs(pv) / s2 / dv

    if len(ratios) < 3:
        return False

    # 대부분의 해가 1 근처면 정상. 그 기준에서 벗어난 해만 고친다.
    ok_years = [y for y, v in ratios.items() if 0.8 <= v <= 1.25]
    if len(ok_years) < len(ratios) * 0.6:
        # 전체가 어긋나면 우선주 배당 등 구조적 차이다. 손대지 않는다.
        return False

    fixed = []
    for r in annual:
        y = r["p"]
        v = ratios.get(y)
        if v is None or 0.8 <= v <= 1.25:
            continue
        for cand in (2, 4, 10, 12, 40):
            for mult in (cand, 1.0 / cand):
                if abs(v / mult - 1) <= 0.06:
                    before = r["dps"]
                    r["dps"] = round(before * mult, 4)
                    fixed.append((y, before, r["dps"], cand, 1))
                    break
            else:
                continue
            break

    for y, before, after, cand, _ in fixed:
        log("  [보정] FY%d 주당배당금 $%.4f -> $%.4f (연간 값이 아니었음, %d배)"
            % (y, before, after, cand))
    return bool(fixed)


def adjust_splits(annual, shares):
    """액면분할을 감지해 과거 주당배당금을 현재 주식 수 기준으로 환산한다.

    국내와 달리 주식 수를 직접 받아오므로 역산할 필요가 없다.
    주식 수가 어느 해에 갑자기 몇 배로 뛰면 분할이다.
    """
    n = len(annual)
    factor = [1.0] * n
    cum, found = 1.0, False
    for i in range(n - 1, 0, -1):
        a = shares.get(annual[i - 1]["p"])
        b = shares.get(annual[i]["p"])
        if a and b and a > 0:
            ratio = b / a
            if ratio >= 1.8 or 0 < ratio <= 0.56:
                target = ratio if ratio >= 1 else 1 / ratio
                # 분할과 자사주 매입이 겹치면 배수가 정확히 안 떨어진다.
                # 깔끔한 배수의 0.85~1.06 배 안이면 그 배수로 인정한다.
                best = None
                for cand in CLEAN_RATIOS:
                    if 0.85 <= target / cand <= 1.06:
                        best = cand
                        break
                # 어떤 배수에도 안 맞으면 분할이 아니다.
                # (주식 수를 어떤 해는 '주', 어떤 해는 '백만 주'로 적는 회사가 있는데
                #  그걸 분할로 착각하면 배당금이 백만 배로 부푼다)
                if best is None:
                    continue
                cum *= best if ratio >= 1 else 1 / best
                found = True
        factor[i - 1] = cum
    # 보정 폭이 상식을 벗어나면(100배 이상) 아예 적용하지 않는다
    if max(factor) > 100:
        log("  ! 분할 배수가 비정상(%.0f배)이라 보정을 건너뜁니다" % max(factor))
        for r in annual:
            r["dps_adj"] = r.get("dps")
        return False

    for i, r in enumerate(annual):
        r["dps_adj"] = round(r["dps"] / factor[i], 4) if r.get("dps") else r.get("dps")

    return found


def merge_facts(a, b):
    """두 CIK 의 companyfacts 를 합친다.

    법인이 바뀌면(스핀오프·지주회사 전환) 과거는 옛 CIK 에,
    최근은 새 CIK 에 나뉘어 있다. 합쳐야 10년이 이어진다.
    같은 기간이 겹치면 뒤에서 '가장 최근 제출본'이 이긴다.
    """
    if not a:
        return b
    if not b:
        return a
    A = a.setdefault("facts", {}).setdefault("us-gaap", {})
    B = b.get("facts", {}).get("us-gaap", {})
    for tag, node in B.items():
        if tag not in A:
            A[tag] = node
            continue
        for unit, rows in node.get("units", {}).items():
            A[tag].setdefault("units", {}).setdefault(unit, []).extend(rows)
    return a


# ------------------------------------------------- companyfacts 에 빠진 최근 공시 보충
# SEC companyfacts API 에 최근 10-Q 가 몇 달째 안 들어오는 회사가 있다
# (2026-11 점검: 넥스트에라·듀크·서던·엑손·프롤로지스 등 25곳이 1분기에서 멈춤).
# 공시 자체는 있으니 그 공시의 XBRL 원본(…_htm.xml)을 직접 읽어 채운다.
SEC_SUBMIT = "https://data.sec.gov/submissions/CIK%s.json"
SEC_ARCH = "https://www.sec.gov/Archives/edgar/data/%d/%s/"
PATCH_TAGS = None


def _patch_tags():
    global PATCH_TAGS
    if PATCH_TAGS is None:
        t = set()
        for k in ("rev", "op", "ni"):
            t.update(TAGS[k])
            t.update(FALLBACK.get(k, []))
        t.update(("NoninterestIncome", "InterestIncomeExpenseNet",
                  "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
                  "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign"))
        t.discard(BANK_REV)
        t.discard(PRETAX_SUM)
        PATCH_TAGS = t
    return PATCH_TAGS


def parse_instance(text, cik):
    """XBRL 원본에서 '회사 전체'(부문 구분 없는) 기간 값만 뽑는다. {태그: [{start,end,val}]}"""
    units = {}
    for m in re.finditer(r'<(?:\w+:)?unit\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</(?:\w+:)?unit>', text, re.S):
        units[m.group(1)] = "USD" if re.search(r"iso4217:USD\s*<", m.group(2)) and "divide" not in m.group(2) else ""
    ctx = {}
    for m in re.finditer(r'<(?:\w+:)?context\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</(?:\w+:)?context>', text, re.S):
        body = m.group(2)
        if "segment" in body or "scenario" in body:
            continue                      # 부문·자회사별 값
        idm = re.search(r"<(?:\w+:)?identifier[^>]*>\s*0*(\d+)\s*<", body)
        if idm and int(idm.group(1)) != int(cik):
            continue
        a = re.search(r"<(?:\w+:)?startDate>\s*([\d-]+)", body)
        b = re.search(r"<(?:\w+:)?endDate>\s*([\d-]+)", body)
        if a and b:
            ctx[m.group(1)] = (a.group(1), b.group(1))
    out = {}
    want = _patch_tags()
    for m in re.finditer(r"<us-gaap:(\w+)\b([^>]*)>([^<]*)</us-gaap:\1>", text):
        tag, attrs, val = m.group(1), m.group(2), m.group(3).strip()
        if tag not in want:
            continue
        c = re.search(r'contextRef="([^"]+)"', attrs)
        u = re.search(r'unitRef="([^"]+)"', attrs)
        if not c or c.group(1) not in ctx or not u or units.get(u.group(1)) != "USD":
            continue
        try:
            v = float(val)
        except ValueError:
            continue
        st, en = ctx[c.group(1)]
        out.setdefault(tag, []).append({"start": st, "end": en, "val": v})
    return out


def _latest_end(facts):
    """매출·영업이익·순이익 각각의 최신 기간 중 가장 이른 것.
    (콘에디슨: 순이익은 3분기까지 들어왔는데 매출은 2분기에서 멈춰 3분기가 통째로 빠졌다)"""
    us = facts.get("facts", {}).get("us-gaap", {})
    ends = []
    for k in ("rev", "op", "ni"):
        tags = set(TAGS[k]) | set(FALLBACK.get(k, []))
        best = ""
        for tag in tags:
            for r in (us.get(tag) or {}).get("units", {}).get("USD", []):
                if r.get("start") and r.get("end", "") > best:
                    best = r["end"]
        if best:
            ends.append(best)
    if not ends:
        return ""
    # 2년 넘게 안 쓴 항목(예전에 쓰다 그만둔 태그)은 기준에서 뺀다 — 매일 옛 공시를 받는 일이 없게
    top = max(ends)
    cut = (datetime.strptime(top, "%Y-%m-%d") - timedelta(days=730)).strftime("%Y-%m-%d")
    return min(e for e in ends if e >= cut)


def patch_recent_filings(facts, ciks):
    latest = _latest_end(facts)
    if not latest:
        return 0
    age = (datetime.now(timezone.utc).date() - datetime.strptime(latest, "%Y-%m-%d").date()).days
    if age < 105:                         # 최근 분기까지 있으면 확인할 필요 없음
        return 0
    cik = ciks[-1]
    sub = get_json(SEC_SUBMIT % cik)
    if not sub:
        return 0
    rc = sub.get("filings", {}).get("recent", {})
    todo = []
    for i, form in enumerate(rc.get("form", [])):
        if form not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
            continue
        rd = rc["reportDate"][i]
        if rd and rd > latest:
            todo.append((rd, rc["filingDate"][i], rc["accessionNumber"][i], form))
    todo = sorted(todo)[-4:]
    us = facts.setdefault("facts", {}).setdefault("us-gaap", {})
    added = 0
    for rd, filed, acc, form in todo:
        base = SEC_ARCH % (int(cik), acc.replace("-", ""))
        idx = get_json(base + "index.json")
        names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
        inst = [n for n in names if n.endswith("_htm.xml")]
        if not inst:
            skip = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")
            inst = [n for n in names if n.endswith(".xml") and not n.endswith(skip)
                    and n not in ("FilingSummary.xml",) and not n.startswith("Financial")]
        if not inst:
            continue
        raw = get(base + inst[0])
        if not raw:
            continue
        got = parse_instance(raw.decode("utf-8", "replace"), cik)
        for tag, rows in got.items():
            node = us.setdefault(tag, {"units": {}})
            lst = node.setdefault("units", {}).setdefault("USD", [])
            for r in rows:
                lst.append(dict(r, filed=filed, form=form.split("/")[0], accn=acc))
                added += 1
        log("  · companyfacts 에 없는 %s(%s) 를 공시 원본에서 보충: %d개 값" % (form, rd, sum(len(v) for v in got.values())))
    return added


def _sum_tags(facts, a_tag, b_tag, out_tag):
    us = facts.get("facts", {}).get("us-gaap", {})
    a = (us.get(a_tag) or {}).get("units", {}).get("USD", [])
    b = (us.get(b_tag) or {}).get("units", {}).get("USD", [])
    if not a or not b:
        return 0

    def latest(rows):
        d = {}
        for r in rows:
            if not r.get("start") or not r.get("end"):
                continue
            k = (r["start"], r["end"])
            if k not in d or r.get("filed", "") >= d[k].get("filed", ""):
                d[k] = r
        return d
    A, B = latest(a), latest(b)
    rows = [{"start": k[0], "end": k[1], "val": A[k]["val"] + B[k]["val"],
             "filed": max(A[k].get("filed", ""), B[k].get("filed", "")),
             "form": A[k].get("form", "")} for k in A.keys() & B.keys()]
    if rows:
        us[out_tag] = {"units": {"USD": rows}}
    return len(rows)


def add_bank_revenue(facts):
    """은행 매출 = 순이자이익 + 비이자이익, 세전이익 = 국내분 + 해외분 (같은 기간끼리)."""
    _sum_tags(facts, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
              "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign", PRETAX_SUM)
    return _sum_tags(facts, "NoninterestIncome", "InterestIncomeExpenseNet", BANK_REV)


PROXY_FORMS = ("DEF 14A", "DEFA14A", "DEFM14A", "DEFR14A", "PRE 14A", "PRER14A")


def drop_proxy_facts(j):
    """주주총회 안내서(DEF 14A)의 '보수 대 성과' 표 숫자는 버린다.
    순이익이 천 달러 단위로 잘못 적혀 들어오고(슈왑 2025 순이익 88.5억 → 885만 달러),
    10-K 보다 늦게 제출돼 '가장 최근 값'으로 뽑혔다 (슈왑·아리스타·메드트로닉·페덱스·페이첵스·콘에드 등)."""
    for ns in (j or {}).get("facts", {}).values():
        for node in ns.values():
            for unit, rows in list(node.get("units", {}).items()):
                node["units"][unit] = [r for r in rows if (r.get("form") or "") not in PROXY_FORMS]
    return j


def fetch_facts(ciks):
    """CIK 여러 개를 받아 합친 companyfacts 를 돌려준다."""
    merged, names = None, []
    for cik in ciks:
        j = get_json(SEC_FACTS % cik)
        if not j:
            log("  ! CIK %s 데이터 없음" % cik)
            continue
        nm = j.get("entityName") or "?"
        names.append("%s(%s)" % (nm, cik))
        merged = merge_facts(merged, drop_proxy_facts(j))
    if names:
        log("  법인: " + " + ".join(names))
    return merged


def blank_bad_revenue(rows):
    """
    은행·리츠 일부는 '매출' 태그에 수수료 같은 일부 수익만 적는다 (피프스서드 매출 577 vs 영업이익 2,988).
    그러면 영업이익률이 500%가 넘게 나온다. 영업이익이 매출보다 크면 매출을 비운다
    — 엉터리 숫자보다 빈칸이 낫다 (2026-11 점검: CCI·CPT·EXR·FITB·HBAN·MTB·RF). 반환: 비운 칸 수
    """
    n = 0
    for r in rows:
        rev, op, ni = r.get("rev"), r.get("op"), r.get("ni")
        # 영업이익은 매출보다 클 수 없다. 순이익은 일회성 이익(사업 매각 등)으로 클 수 있어 영업이익이 없을 때만 본다
        if rev and rev > 0 and ((op is not None and op > rev * 1.05) or (op is None and ni and ni > rev * 3)):
            r["rev"] = None
            n += 1
    return n


def collect_one(ticker, info):
    log("\n=== %s (%s) ===" % (ticker, info["name"]))
    ciks = info["cik"] if isinstance(info["cik"], list) else [info["cik"]]
    facts = fetch_facts(ciks)
    if not facts:
        return None, "SEC 데이터 없음"
    try:
        patch_recent_filings(facts, ciks)
    except Exception as e:                # noqa: BLE001
        log("  ! 최근 공시 보충 실패: %r" % e)
    add_bank_revenue(facts)
    ent = facts.get("entityName")
    if ent:
        info = dict(info, name=ent)

    _used_tag.clear()
    A = {k: annual_series(facts, k) for k in
         ("rev", "op", "ni", "assets", "liab", "equity", "dps", "shares", "divpaid")}
    A["shares"] = normalize_shares(A["shares"])
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
            "dps": A["dps"].get(fy), "payout": payout_of(fy, A), "yield": None,
        })
        po = payout_of(fy, A)
        log("  FY%d  매출 %s M$  영업이익 %s M$  DPS %s  배당성향 %s" % (
            fy, f"{mil(rev):,.0f}",
            (f"{mil(op):,.0f}" if op is not None else "-"),
            (f"${A['dps'][fy]:.2f}" if fy in A["dps"] else "-"),
            (f"{po}%" if po is not None else "-")))
    annual = annual[-YEARS:]

    fix_dps_scale(annual, A)

    restated = find_restatement(annual)
    if restated:
        log("  [주의] FY%d 부터 실적 기준이 바뀐 것으로 보입니다" % restated)
        log("         (사업 분할 등으로 과거를 다시 쓴 경우. 그 이전 연도와 직접 비교하기 어렵습니다)")

    split = adjust_splits(annual, A["shares"])

    if split:
        log("  [분할] 액면분할 감지 — 과거 주당배당금을 현재 주식 수 기준으로 환산")
        for r in annual:
            if r.get("dps") and r["dps"] != r.get("dps_adj"):
                log("    FY%d  공시 $%.2f -> 환산 $%.2f" % (r["p"], r["dps"], r["dps_adj"]))

    fem = fiscal_end_month(facts)
    dbg("결산월: %d월" % fem)
    QTAG.clear()
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
                parts = [Q[key].get((fy, i)) for i in (1, 2, 3)]
                if any(x is None for x in parts):
                    return None
                # 1~3분기와 같은 태그의 연간 값에서 뺀다. 태그가 다르면 뜻이 달라 엉터리가 된다
                # (엑손 4분기 영업이익이 -222억 달러로 나왔다: 연간은 국내분, 분기는 전체 세전이익)
                tags = {QTAG.get((key, fy, i)) for i in (1, 2, 3)}
                if len(tags) != 1 or None in tags:
                    return None
                ann = annual_of_tag(facts, tags.pop(), fy)
                if ann is None:
                    return None
                return ann - sum(parts)
            r4 = q4("rev")
            if r4 is not None:
                quarterly.append({"y": fy, "q": 4, "rev": mil(r4),
                                  "op": mil(q4("op")), "ni": mil(q4("ni"))})
    # 연간 매출이 1~3분기 합보다 작으면 연간 값이 틀린 것이다 (FIX 2025: 연간 매출이 1분기 값 1,831으로 공시 태그됨
    # → 4분기 = 연간 - 3분기 누적이 -4,624). 그 해 연간 줄과 거기서 만든 4분기를 뺀다
    for a in list(annual):
        parts = [x["rev"] for x in quarterly if x["y"] == a["p"] and x["q"] in (1, 2, 3)]
        if len(parts) == 3 and None not in parts and a.get("rev") and sum(parts) > a["rev"] * 1.02:
            log("  [버림] FY%d 연간 매출 %s 이 1~3분기 합 %s 보다 작다 — 연간·4분기 값 제외"
                % (a["p"], f"{a['rev']:,.0f}", f"{sum(parts):,.0f}"))
            annual.remove(a)
            quarterly = [x for x in quarterly if not (x["y"] == a["p"] and x["q"] == 4)]
    quarterly.sort(key=lambda x: (x["y"], x["q"]))
    quarterly = [x for x in quarterly if x["rev"] is not None][-QUARTERS:]
    for x in quarterly:
        log("  FY%d %dQ  매출 %s M$" % (x["y"], x["q"], f"{x['rev']:,.0f}"))

    if not annual and not quarterly:
        return None, "쓸 수 있는 데이터 없음"
    blank_bad_revenue(annual + quarterly)

    return {
        "name": ticker,
        "split_adjusted": split,
        "restated_from": restated,
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

TICKER_RE = re.compile(r"^[A-Z][-A-Z.]{0,6}$")


def strip_tags(html):
    out, depth = [], 0
    for ch in html:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()


def parse_wiki_tickers(html):
    """위키백과 구성종목 표에서 티커를 뽑는다.

    표의 '첫 칸이 티커인 행'이 충분히 많은 표만 구성종목 표로 본다.
    """
    found = []
    for table in re.findall(r"<table[^>]*>.*?</table>", html, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        hits = []
        for row in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
            if not cells:
                continue
            t = strip_tags(cells[0]).replace("\u200b", "").strip()
            if TICKER_RE.match(t) and t not in ("SYMBOL", "TICKER"):
                hits.append(t.replace(".", "-"))
        if len(hits) >= 50:
            found.extend(hits)
    seen, out = set(), []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_tickers():
    """S&P 500 + 나스닥 100 구성종목으로 us_tickers.txt 를 만든다."""
    groups = []
    for name, url in INDEX_SOURCES:
        b = get(url)
        if not b:
            log("! %s 목록을 받지 못했습니다" % name)
            continue
        try:
            html = b.decode("utf-8", "ignore")
        except Exception:                 # noqa: BLE001
            continue
        ts = parse_wiki_tickers(html)
        log("%s: %d종목" % (name, len(ts)))
        if ts:
            groups.append((name, ts))

    if not groups:
        log("!! 목록을 하나도 받지 못해 파일을 건드리지 않았습니다.")
        return

    allt, seen = [], set()
    for name, ts in groups:
        for t in ts:
            if t not in seen:
                seen.add(t)
                allt.append(t)

    path = "us_tickers.txt"
    if os.path.exists(path):
        os.replace(path, path + ".bak")
        log("기존 파일을 %s.bak 로 옮겼습니다" % path)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# S&P 500 + 나스닥 100 구성종목 — collect_us.py --build-tickers 로 생성\n")
        f.write("# 생성일 %s\n" % datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"))
        f.write("# 'TICKER 34088' 처럼 뒤에 숫자를 적으면 그 CIK 를 직접 씁니다.\n\n")
        for name, ts in groups:
            f.write("# --- %s (%d) ---\n" % (name, len(ts)))
        f.write("\n")
        for t in allt:
            ov = CIK_OVERRIDE.get(t)
            f.write("%s %s\n" % (t, ov) if ov else "%s\n" % t)
    log("\nus_tickers.txt 생성 — 중복 제거 후 %d종목" % len(allt))
    log("다음: python3 collect_us.py --verify  로 등록명을 확인하세요.")


def load_tickers(args):
    """[(티커, CIK지정or None)] 목록.

    us_tickers.txt 에서 'AAPL' 처럼 티커만 써도 되고,
    'XOM 34088' 처럼 CIK 를 직접 지정할 수도 있다.
    같은 티커를 다른 회사가 물려받은 경우에 쓴다.
    """
    def parse(line):
        parts = line.split()
        t = parts[0].upper()
        ciks = ["%010d" % int(x) for x in parts[1:] if x.isdigit()]
        if not ciks and t in CIK_OVERRIDE:
            # 목록 파일에 안 적혀 있어도 알려진 법인 전환은 자동 적용
            ciks = ["%010d" % int(x) for x in CIK_OVERRIDE[t].split()]
        return (t, ciks or None)

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
            ok.append((t, "CIK 직접 지정 " + ", ".join(cik)))
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

    if "--build-tickers" in argv:
        build_tickers()
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
            old = os.path.join(OUT_DIR, t + ".json")
            if reason == "매출 태그를 못 찾음" and os.path.exists(old):
                # 예전 규칙으로 엉뚱한 태그(인수 가정 매출 등)를 매출로 썼던 파일 — 남겨 두면 틀린 숫자가 계속 보인다
                os.remove(old)
                log("  ! %s: 쓸 수 있는 매출이 없어 예전 파일을 지웁니다" % t)
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
