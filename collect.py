#!/usr/bin/env python3
"""
DART OpenAPI -> data/{종목코드}.json 수집기

사용법 (설정 없이 바로 실행):
    python3 collect.py --verify            # 종목코드 확인만 (API 호출 0회)
    python3 collect.py                     # tickers.txt 의 종목 수집
    python3 collect.py 005930 000660       # 종목 직접 지정
    python3 collect.py --lookup 105560     # corpCode.xml 에서 조회
    python3 collect.py --debug 033780      # 계정 매칭 과정 출력

이 파일은 .gitignore 에 등록돼 있어 GitHub에 올라가지 않습니다.
표준 라이브러리만 사용합니다. pip install 불필요.
"""

import io
import json
import math
import os
import sys
import time
import zipfile
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

API = "https://opendart.fss.or.kr/api"
CACHE_DIR = ".cache"
OUT_DIR = "data"

# 키는 이 파일에 적지 않는다. 아래 순서로 찾는다:
#   1) 환경변수 DART_API_KEY      (GitHub Actions 에서 사용)
#   2) 같은 폴더의 key.txt 파일    (내 PC에서 사용, .gitignore 로 제외됨)
KEY_FILE = "key.txt"

DEFAULT_TICKERS = ["005930", "005380", "033780"]  # 삼성전자, 현대차, KT&G

YEARS = 10        # 연간 몇 개년
QUARTERS = 10     # 분기 몇 개
SLEEP = 0.12      # 호출 간 간격(초)

REPRT = {"Q1": "11013", "HALF": "11012", "Q3": "11014", "YEAR": "11011"}

# 계정명은 회사마다 다르다. 앞에서부터 순서대로 시도한다.
ACCOUNT_CANDIDATES = {
    "rev": {
        "ids": ["ifrs-full_Revenue", "ifrs_Revenue",
                "ifrs-full_RevenueFromContractsWithCustomers"],
        "names": ["매출액", "수익(매출액)", "영업수익", "매출",
                  "영업수익(매출액)", "수익"],
    },
    "op": {
        "ids": ["dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"],
        "names": ["영업이익", "영업이익(손실)", "영업손익"],
    },
    "ni": {
        "ids": ["ifrs-full_ProfitLoss"],
        "names": ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익",
                  "당기순손익", "연결당기순이익"],
    },
    # --- 재무상태표 (ROE / 부채비율용) ---
    "assets": {
        "ids": ["ifrs-full_Assets"],
        "names": ["자산총계", "자산총계(자산총액)"],
    },
    "liab": {
        "ids": ["ifrs-full_Liabilities"],
        "names": ["부채총계", "부채총계(부채총액)"],
    },
    "equity": {
        "ids": ["ifrs-full_Equity", "ifrs-full_EquityAttributableToOwnersOfParent"],
        "names": ["자본총계", "자본총계(자본총액)", "지배기업소유주지분"],
    },
}

BS_KINDS = {"assets", "liab", "equity"}

DEBUG = False
_call_count = 0


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def dbg(*a):
    if DEBUG:
        log("   ·", *a)


# ---------------------------------------------------------------- HTTP

def get_key():
    k = os.environ.get("DART_API_KEY", "").strip()
    src = "환경변수"
    if not k and os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            k = f.read().strip()
        src = KEY_FILE
    if not k:
        log("DART API 키를 찾을 수 없습니다.\n")
        log("  이 폴더에 key.txt 파일을 만들고 키만 한 줄 적으세요:")
        log('      echo "발급받은키" > key.txt')
        log("\n  key.txt 는 .gitignore 에 있어 GitHub에 올라가지 않습니다.")
        log("  키 발급: https://opendart.fss.or.kr")
        sys.exit(1)
    if len(k) != 40:
        log("! 키 길이가 40자가 아닙니다(%d자). 오타일 수 있습니다." % len(k))
    log("API 키: %s…%s (%s)" % (k[:6], k[-4:], src))
    return k


# DART가 정상 응답(200)으로 돌려주는 치명적 상태코드
FATAL_STATUS = {
    "020": "일일 요청 한도를 초과했습니다",
    "021": "조회 가능한 회사 개수를 초과했습니다",
    "010": "등록되지 않은 인증키입니다",
    "011": "사용할 수 없는 인증키입니다",
    "012": "접근할 수 없는 IP입니다",
    "800": "DART 시스템 점검 중입니다",
}
ABORT = None       # 치명적 상태를 만나면 사유가 담긴다


def api_get(endpoint, params, raw=False, tries=3):
    global _call_count, ABORT
    if ABORT:
        return None
    params = dict(params)
    params["crtfc_key"] = API_KEY
    url = API + "/" + endpoint + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(tries):
        try:
            _call_count += 1
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
            time.sleep(SLEEP)
            if raw:
                return body
            res = json.loads(body.decode("utf-8"))
            st = str(res.get("status", ""))
            if st in FATAL_STATUS:
                ABORT = "%s (status %s)" % (FATAL_STATUS[st], st)
                log("\n!! %s" % ABORT)
                return None
            return res
        except Exception as e:      # noqa: BLE001
            last = e
            time.sleep(1.0 + attempt)
    log("  ! 호출 실패:", endpoint, params.get("bsns_year", ""), last)
    return None


# ------------------------------------------------- corp_code 매핑

def load_corp_map():
    """corpCode.xml(ZIP)을 받아 종목코드 -> 고유번호 매핑을 만든다. 한 번 받으면 캐시."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.join(CACHE_DIR, "corpCode.xml")

    if not os.path.exists(cached):
        log("corpCode.xml 내려받는 중… (최초 1회, 수십 MB)")
        blob = api_get("corpCode.xml", {}, raw=True)
        if blob is None:
            sys.exit("corpCode 다운로드 실패")
        if blob[:2] != b"PK":
            sys.exit("ZIP이 아닌 응답입니다. API 키를 확인하세요: " + blob[:200].decode("utf-8", "replace"))
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = z.namelist()[0]
            with open(cached, "wb") as f:
                f.write(z.read(name))
        log("  저장:", cached)

    root = ET.parse(cached).getroot()
    m = {}
    for node in root.iter("list"):
        stock = (node.findtext("stock_code") or "").strip()
        if not stock:
            continue           # 비상장은 종목코드가 비어 있다
        m[stock] = {
            "corp_code": (node.findtext("corp_code") or "").strip(),
            "name": (node.findtext("corp_name") or "").strip(),
        }
    log("상장사 매핑 %d건" % len(m))
    return m


# ------------------------------------------------- 재무 파싱

_fs_cache = {}


def fetch_fs(corp_code, year, reprt_code):
    """단일회사 전체 재무제표. 연결(CFS) 우선, 없으면 별도(OFS)."""
    key = (corp_code, year, reprt_code)
    if key in _fs_cache:
        return _fs_cache[key]

    rows = None
    for fs_div in ("CFS", "OFS"):
        res = api_get("fnlttSinglAcntAll.json", {
            "corp_code": corp_code, "bsns_year": str(year),
            "reprt_code": reprt_code, "fs_div": fs_div,
        })
        if res and res.get("status") == "000" and res.get("list"):
            rows = res["list"]
            dbg("FS %s %s %s -> %s (%d행)" % (corp_code, year, reprt_code, fs_div, len(rows)))
            break
    if rows and any((r.get("currency") or "").upper() == "USD" for r in rows):
        to_krw(rows, year)
        log("  [통화] 달러로 공시 — 그해 평균 환율로 원화로 바꿨습니다 (%s)" % year)
    _fs_cache[key] = rows
    return rows


_FX_AVG = None


def fx_avg(year):
    """그해 평균 원/달러 환율 (data/fx_usdkrw.json). 없으면 가장 가까운 해."""
    global _FX_AVG
    if _FX_AVG is None:
        _FX_AVG = {}
        try:
            with open(os.path.join(OUT_DIR, "fx_usdkrw.json"), encoding="utf-8") as f:
                rates = json.load(f).get("rates") or {}
            acc = {}
            for d, v in rates.items():
                acc.setdefault(int(d[:4]), []).append(v)
            _FX_AVG = {y: sum(v) / len(v) for y, v in acc.items()}
        except Exception:      # noqa: BLE001
            pass
    if not _FX_AVG:
        return 1300.0
    if year in _FX_AVG:
        return _FX_AVG[year]
    near = min(_FX_AVG, key=lambda y: abs(y - year))
    return _FX_AVG[near]


def to_krw(rows, year):
    """
    달러로 공시하는 국내 상장사(두산밥캣 2023~, 아남전자 2019~)는 숫자가 달러라
    매출 9조가 '74.8억' 처럼 1,300분의 1로 보였다 (2026-11 점검). 금액 칸을 그해 평균 환율로 원화로 바꾼다.
    당기·전기·전전기 금액은 각각 그해 환율을 쓴다.
    """
    for r in rows:
        for k, v in list(r.items()):
            if not k.endswith("_amount"):
                continue
            n = to_num(v)
            if n is None:
                continue
            y = year - (2 if k.startswith("bfefrmtrm") else 1 if k.startswith("frmtrm") else 0)
            r[k] = str(n * fx_avg(y))
        r["currency"] = "KRW"


def to_num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "—"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def pick_account(rows, kind, cumulative):
    """
    손익계산서에서 원하는 계정 하나를 뽑는다.
    cumulative=True면 누적치(thstrm_add_amount)를 우선한다.
    """
    if not rows:
        return None
    cand = ACCOUNT_CANDIDATES[kind]
    want = ("BS",) if kind in BS_KINDS else ("IS", "CIS")
    sub = [r for r in rows if r.get("sj_div") in want]
    pool = sub or rows

    def value_of(r):
        if cumulative:
            v = to_num(r.get("thstrm_add_amount"))
            if v is not None:
                return v
        return to_num(r.get("thstrm_amount"))

    def bad_name(r):
        # 현대차증권 2025 반기: ifrs-full_Revenue 에 '영업이익' 이 붙어 와 매출=영업이익이 됐다
        nm = (r.get("account_nm") or "")
        return kind == "rev" and any(w in nm for w in ("이익", "손익", "비용"))

    for aid in cand["ids"]:
        for r in pool:
            if (r.get("account_id") or "").strip() == aid and not bad_name(r):
                v = value_of(r)
                if v is not None:
                    dbg("%s <- account_id %s" % (kind, aid))
                    return v

    for nm in cand["names"]:
        for r in pool:
            if (r.get("account_nm") or "").strip().replace(" ", "") == nm.replace(" ", ""):
                v = value_of(r)
                if v is not None:
                    dbg("%s <- account_nm %s" % (kind, nm))
                    return v
    return None


FIN_IDS = {"ifrs-full_FeeAndCommissionIncome", "ifrs-full_RevenueFromInterest", "ifrs-full_InsuranceRevenue",
           "ifrs-full_InsuranceServiceResult", "ifrs-full_InterestRevenueExpense", "dart_OperatingIncomeInsurance"}
# 은행·카드·증권: 손익계산서에 '영업수익' 합계 줄이 없어진 경우(삼성카드 2025~) 총수익 = 아래 수익 줄의 합
FIN_GROSS_IDS = ["ifrs-full_RevenueFromInterest", "ifrs-full_FeeAndCommissionIncome", "ifrs-full_RevenueFromDividends",
                 "dart_LeaseIncome", "ifrs-full_ForeignExchangeGain", "ifrs-full_MiscellaneousOtherOperatingIncome",
                 "dart_OtherOperatingIncome", "dart_InsuranceFinanceIncomeFromInsuranceContractsIssued"]
_GROSS_OK = {}


def is_financial(rows):
    return any((r.get("account_id") or "").strip() in FIN_IDS for r in rows or [])


def fin_gross(rows, cumulative):
    """
    2025년부터 금융회사 상당수가 손익계산서를 순액(순이자손익·순수수료손익…)으로만 내 '영업수익' 줄이 없다
    (메리츠금융·삼성카드·한국금융지주·현대차증권 등 — 2025 사업보고서부터 매출 매칭 실패로 실적이 멈춰 있었다).
    수익 줄(이자수익·수수료수익·배당·리스·외환이익·파생/유가증권 '이익')을 더해 총수익을 만든다.
    보험사는 보험영업수익 + 투자영업수익. 이 값이 예전 '영업수익' 과 맞는지는 호출하는 쪽에서 직전 해와 비교해 확인한다.
    """
    sub = [r for r in rows or [] if r.get("sj_div") in ("IS", "CIS")]

    def val(r):
        if cumulative:
            v = to_num(r.get("thstrm_add_amount"))
            if v is not None:
                return v
        return to_num(r.get("thstrm_amount"))

    def first(aid):
        for r in sub:
            if (r.get("account_id") or "").strip() == aid:
                v = val(r)
                if v is not None:
                    return v
        return None

    ins = first("dart_OperatingIncomeInsurance")
    inv = first("ifrs-full_InvestmentIncome")
    if inv is not None and ins is not None:                 # 보험사
        return ins + inv
    total, used = 0.0, set()
    for aid in FIN_GROSS_IDS:
        v = first(aid)
        if v is not None and v > 0:
            total += v
            used.add(aid)
    for r in sub:                                           # 파생·유가증권 '이익' 줄 (손익·순액 줄은 뺀다)
        aid = (r.get("account_id") or "").strip()
        nm = (r.get("account_nm") or "").replace(" ", "")
        if aid.startswith("dart_Gain") and not aid.startswith("dart_GainLoss") and aid not in used \
                and (nm.endswith("이익") or nm.endswith("수익")):
            v = val(r)
            if v is not None and v > 0:
                total += v
                used.add(aid)
    return total if used and total > 0 else None


def eok(v):
    """원 단위 -> 억원. 소수 1자리."""
    return None if v is None else round(v / 1e8, 1)


# ------------------------------------------------- 배당

CORP_CLS = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "기타"}


def fetch_market(corp_code):
    """기업개황에서 시장 구분을 가져온다. corp_cls: Y 유가 / K 코스닥 / N 코넥스 / E 기타"""
    res = api_get("company.json", {"corp_code": corp_code})
    if not res or res.get("status") != "000":
        return ""
    return CORP_CLS.get((res.get("corp_cls") or "").strip().upper(), "")


def fetch_dividend(corp_code, year):
    """배당에 관한 사항. 보통주 기준 주당 현금배당금 / 배당성향 / 시가배당률."""
    res = api_get("alotMatter.json", {
        "corp_code": corp_code, "bsns_year": str(year), "reprt_code": REPRT["YEAR"],
    })
    if not res or res.get("status") != "000":
        return {"dps": None, "payout": None, "yield": None}

    out = {"dps": None, "payout": None, "yield": None}
    for r in res.get("list", []):
        se = (r.get("se") or "").replace(" ", "")
        knd = (r.get("stock_knd") or "").replace(" ", "")
        val = to_num(r.get("thstrm"))
        if val is None:
            continue

        # 우선주 줄은 건너뛴다. 보통주 줄이나 종류 표기가 없는 줄만 쓴다.
        if knd and "우선" in knd:
            continue
        is_common = (not knd) or ("보통" in knd)

        if "주당현금배당금" in se and is_common:
            if out["dps"] is None:          # 먼저 찾은 값을 지킨다 (덮어쓰지 않음)
                out["dps"] = val
                dbg("DPS <- se='%s' stock_knd='%s' thstrm=%s"
                    % (r.get("se"), r.get("stock_knd"), r.get("thstrm")))
        elif "현금배당성향" in se:
            if out["payout"] is None:
                out["payout"] = val
        elif "현금배당수익률" in se and is_common:
            if out["yield"] is None:
                out["yield"] = val
    return out


# ------------------------------------------------- 수집 본체

CLEAN_RATIOS = [2, 2.5, 3, 4, 5, 10, 20, 50, 100]


def adjust_for_splits(rows):
    """
    액면분할을 감지해 과거 주당배당금을 '현재 주식 수 기준'으로 환산한다.

    배당성향 = (DPS x 주식수) / 순이익  이므로
        주식수 = 배당성향 x 순이익 / DPS
    로 주식 수를 역산할 수 있다. 이 값이 어느 해에 갑자기 몇 배로 뛰면 분할이다.

    rows 각 항목에 dps_adj 를 채우고, 분할이 있었으면 True 를 반환한다.
    """
    shares = []
    for r in rows:
        d, p, n = r.get("dps"), r.get("payout"), r.get("ni")
        if d and p and n and d > 0 and p > 0:
            shares.append(p / 100.0 * (n * 1e8) / d)
        else:
            shares.append(None)

    # 뒤(최근)에서 앞으로 오면서 누적 분할배수를 만든다
    # 배당성향·순이익만으로 역산한 주식 수는 흔들린다(지주사·배당 삭감 해 등).
    # 실제 분할이면 '원래 주당배당금'도 그 배수만큼 같이 떨어진다(병합이면 뛴다) — 두 조건을 다 맞는 배수만 분할로 본다.
    # (2026-11 수정: 미스토홀딩스·CJ 등 150여 곳이 엉뚱하게 환산돼 연속 증가 연수가 틀렸다)
    factor = [1.0] * len(rows)
    cum = 1.0
    found = False
    for i in range(len(rows) - 1, 0, -1):
        a, b = shares[i - 1], shares[i]
        d0, d1 = rows[i - 1].get("dps"), rows[i].get("dps")
        if a and b and a > 0 and d0 and d1:
            ratio = b / a
            if ratio >= 1.8 or (0 < ratio <= 0.56):     # 분할 또는 병합 후보
                target = ratio if ratio >= 1 else 1 / ratio
                jump = d0 / d1 if ratio >= 1 else d1 / d0
                ok = [cand for cand in CLEAN_RATIOS
                      if 0.85 <= target / cand <= 1.1 and 0.8 * cand <= jump <= 1.35 * cand]
                if ok:      # 두 값에 가장 가까운 배수 (5:1 분할을 4배로 잡지 않게)
                    cand = min(ok, key=lambda x: abs(math.log(target / x)) + abs(math.log(jump / x)))
                    cum *= cand if ratio >= 1 else 1 / cand
                    found = True
        factor[i - 1] = cum

    for i, r in enumerate(rows):
        r["dps_adj"] = round(r["dps"] / factor[i], 1) if r.get("dps") else r.get("dps")
    return found


def collect_annual(corp_code, latest_year):
    """올해 사업보고서는 아직 없을 수 있으므로 한 해 더 넓게 훑고 뒤에서 자른다."""
    rows = []
    for y in range(latest_year - YEARS, latest_year + 1):
        fs = fetch_fs(corp_code, y, REPRT["YEAR"])
        if not fs:
            dbg("%d년 사업보고서 없음" % y)
            continue
        rev = pick_account(fs, "rev", cumulative=False)
        op = pick_account(fs, "op", cumulative=False)
        ni = pick_account(fs, "ni", cumulative=False)
        if rev is None and op is not None and is_financial(fs):
            g = fin_gross(fs, cumulative=False)
            prev = rows[-1]["rev"] if rows and rows[-1]["p"] == y - 1 and rows[-1].get("rev") else None
            if g and (_GROSS_OK.get(corp_code) or (prev and 0.7 <= eok(g) / prev <= 1.45)):
                rev = g
                _GROSS_OK[corp_code] = True
                log("  · %d년 매출 = 수익 줄 합계 %s억 (금융사, 영업수익 합계 줄 없음)" % (y, f"{eok(g):,.0f}"))
            else:
                log("  · %d년 매출 합계 줄 없음 — 영업이익·순이익만 넣는다 (금융사)" % y)
        if op is None or (rev is None and not is_financial(fs)):
            log("  - %d년 매출/영업이익 매칭 실패, 건너뜀" % y)
            continue
        assets = pick_account(fs, "assets", cumulative=False)
        liab = pick_account(fs, "liab", cumulative=False)
        equity = pick_account(fs, "equity", cumulative=False)
        div = fetch_dividend(corp_code, y)
        rows.append({
            "p": y, "rev": eok(rev), "op": eok(op), "ni": eok(ni),
            "assets": eok(assets), "liab": eok(liab), "equity": eok(equity),
            "dps": div["dps"], "payout": div["payout"], "yield": div["yield"],
        })
        log("  %d년  매출 %s억  영업이익 %s억  DPS %s" %
            (y, f"{eok(rev):,.0f}" if rev is not None else "-", f"{eok(op):,.0f}",
             f"{div['dps']:,.0f}원" if div["dps"] else "-"))
    return rows[-YEARS:]


def collect_quarterly(corp_code, latest_year):
    """
    DART엔 '2분기 단독' 보고서가 없다. 누적에서 빼서 각 분기를 만든다.
        1Q = 1분기보고서
        2Q = 반기 - 1Q
        3Q = 3분기보고서(누적) - 반기
        4Q = 사업보고서(연간) - 3Q누적

    빼야 할 앞 보고서가 없으면 그 분기는 만들지 않는다 (빈칸). 예전에는 빼지 않고
    누적값을 그대로 썼는데, 결산월이 12월이 아니거나 보고서가 빠진 회사에서
    9개월치가 '3Q' 로, 1년치가 '4Q' 로 들어갔다 (신성통상 2026.3Q 9,896억).
    틀린 숫자보다 빈칸이 낫다. 이미 받은 파일은 fix_quarters.py 로 정리한다.

    올해 분기보고서는 이미 나와 있으므로 현재 연도까지 훑는다.
    (분기보고서 마감은 분기 종료 후 45일, 반기는 60일)
    아직 안 나온 보고서는 자연스럽게 None이 되어 건너뛴다.
    """
    out = []
    for y in range(latest_year - 3, latest_year + 1):
        cum = {}
        fin_tags = set()
        for tag, code in (("Q1", REPRT["Q1"]), ("HALF", REPRT["HALF"]),
                          ("Q3", REPRT["Q3"]), ("YEAR", REPRT["YEAR"])):
            fs = fetch_fs(corp_code, y, code)
            if not fs:
                continue
            use_cum = tag != "YEAR"
            rv = pick_account(fs, "rev", cumulative=use_cum)
            if rv is None and _GROSS_OK.get(corp_code):          # 연간에서 맞는지 확인된 금융사만
                rv = fin_gross(fs, cumulative=use_cum)
            if rv is None and is_financial(fs):
                fin_tags.add(tag)
            cum[tag] = {
                "rev": rv,
                "op": pick_account(fs, "op", cumulative=use_cum),
                "ni": pick_account(fs, "ni", cumulative=use_cum),
            }

        def diff(a, b):
            if a is None or b is None:
                return None              # 앞 보고서가 없으면 이 분기를 만들 수 없다
            return a - b

        def grab(tag, k):
            return cum.get(tag, {}).get(k)

        steps = [
            (1, lambda k: grab("Q1", k)),
            (2, lambda k: diff(grab("HALF", k), grab("Q1", k))),
            (3, lambda k: diff(grab("Q3", k), grab("HALF", k))),
            (4, lambda k: diff(grab("YEAR", k), grab("Q3", k))),
        ]
        for q, fn in steps:
            rev, op, ni = fn("rev"), fn("op"), fn("ni")
            if op is None or (rev is None and not fin_tags):
                continue
            out.append({"y": y, "q": q, "rev": eok(rev), "op": eok(op), "ni": eok(ni)})
            log("  %d.%dQ  매출 %s억  영업이익 %s억" % (y, q, f"{eok(rev):,.0f}" if rev is not None else "-", f"{eok(op):,.0f}"))

    return out[-QUARTERS:]


def collect_company(code, corp_map, latest_year, alias=None):
    info = corp_map.get(code)
    if not info:
        log("! %s : corpCode.xml 에서 종목코드를 못 찾았습니다" % code)
        log("  확인:  python3 collect.py --lookup %s" % code)
        return None, "corpCode 매핑 실패"

    display = alias or info["name"]
    log("\n=== %s (%s) ===" % (display, code))
    if alias and alias != info["name"]:
        log("  표시명 '%s'  (DART 정식명칭: %s)" % (alias, info["name"]))
    corp_code = info["corp_code"]

    log(" [연간]")
    annual = collect_annual(corp_code, latest_year)
    log(" [분기]")
    quarterly = collect_quarterly(corp_code, latest_year)

    if not annual and not quarterly:
        log("! 재무 데이터가 하나도 없습니다.")
        log("  fnlttSinglAcntAll 은 '상장법인(금융업 제외)' 대상이라,")
        log("  은행·보험·증권·금융지주는 이 API로 안 나올 수 있습니다.")
        return None, "재무 데이터 없음(금융업?)"

    worst = check_quarters_vs_annual(annual, quarterly)

    split = adjust_for_splits(annual)
    if split:
        log("  [분할] 액면분할 감지 — 과거 주당배당금을 현재 주식 수 기준으로 환산했습니다")
        for a in annual:
            if a.get("dps") and a["dps"] != a.get("dps_adj"):
                log("    %d년  공시 %s원 -> 환산 %s원"
                    % (a["p"], f"{a['dps']:,.0f}", f"{a['dps_adj']:,.0f}"))

    return {
        "name": display,
        "split_adjusted": split,
        "legal_name": info["name"],
        "code": code,
        "market": fetch_market(corp_code),
        "sector": "",
        "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
        "annual": annual,
        "quarterly": quarterly,
        "q_method": "strict",          # 앞 보고서가 있을 때만 분기를 만든 파일 (fix_quarters.py 가 건너뛴다)
        "_worst_gap": worst,
    }, None


def check_quarters_vs_annual(annual, quarterly):
    """분기 4개 합이 연간과 크게 어긋나면 누적치 차감이 잘못된 것이다."""
    by_year = {}
    for q in quarterly:
        by_year.setdefault(q["y"], []).append(q)
    amap = {a["p"]: a for a in annual}
    worst = 0.0
    checked = 0
    for y, qs in sorted(by_year.items()):
        if len(qs) != 4 or y not in amap:
            continue
        if any(q.get("rev") is None for q in qs):
            continue
        s = sum(q["rev"] for q in qs)
        a = amap[y]["rev"]
        if not a:
            continue
        checked += 1
        gap = abs(s - a) / a * 100
        worst = max(worst, gap)
        mark = "OK" if gap < 2 else "!! 확인 필요"
        log("  [검산] %d년 분기합 %s억 vs 연간 %s억  (차이 %.1f%%) %s"
            % (y, f"{s:,.0f}", f"{a:,.0f}", gap, mark))
    if checked == 0:
        return None
    return worst


def build_tickers_file(corp_map, path="tickers_all.txt"):
    """corpCode.xml 의 상장사 전체를 tickers_all.txt 로 뽑는다."""
    rows = sorted(corp_map.items())
    with open(path, "w", encoding="utf-8") as f:
        f.write("# corpCode.xml 에서 자동 생성한 전체 종목 목록\n")
        f.write("# 생성: %s / %d종목\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M"), len(rows)))
        f.write("# 상장폐지된 종목도 섞여 있습니다. 수집하면 자동으로 걸러집니다.\n")
        f.write("# 사용:  python3 collect.py --all --budget 12000\n\n")
        for code, info in rows:
            f.write("%s  %s\n" % (code, info["name"]))
    log("%s 생성 완료 — %d종목" % (path, len(rows)))
    log("사용:  python3 collect.py --all --budget 12000")


def data_unchanged(path, new):
    """updated 날짜를 뺀 나머지가 기존 파일과 같으면 True."""
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:      # noqa: BLE001
        return False
    a = {k: v for k, v in old.items() if k != "updated"}
    b = {k: v for k, v in new.items() if k != "updated"}
    return a == b


def clean_annual(rows):
    """
    연간 숫자 중 단위가 틀린 해(원·천원으로 들어와 1천 배·1백만 배로 튄 해)를 바로잡는다 (2026-11 점검:
    엘에이티 2017 매출 68,923,935억·소프트센 2022·대산F&B 2023·네오크레마 2022·제이앤케이 2021).
    나머지 해 중앙값의 200배 넘게 크면 1,000 또는 1,000,000 으로 나눠 중앙값에 가장 가까운 쪽을 쓴다. 반환: 고친 해 수
    """
    n = 0
    vals = [abs(r["rev"]) for r in rows if r.get("rev")]
    if len(vals) < 4:
        return 0
    def is_out(r):
        v = r.get("rev")
        if not v:
            return False
        others = sorted(abs(x["rev"]) for x in rows if x is not r and x.get("rev"))
        med = others[len(others) // 2]
        return med > 0 and abs(v) > 200 * med
    flags = [is_out(r) for r in rows]
    for i, r in enumerate(rows):
        if not flags[i]:
            continue
        # 단위 오류는 한 해짜리다. 이웃한 해도 같이 튀면(통화가 바뀐 경우 등) 손대지 않는다
        if (i > 0 and flags[i - 1]) or (i + 1 < len(rows) and flags[i + 1]):
            continue
        v = r["rev"]
        others = sorted(abs(x["rev"]) for x in rows if x is not r and x.get("rev"))
        med = others[len(others) // 2]
        f = min((1e3, 1e6), key=lambda k: abs(math.log(abs(v) / k / med)))
        if abs(math.log(abs(v) / f / med)) > math.log(20):
            continue
        for k in ("rev", "op", "ni", "assets", "liab", "equity"):
            if r.get(k) is not None:
                r[k] = round(r[k] / f, 1)
        n += 1
    return n


def clean_quarters(q):
    """
    분기 숫자 중 '단위가 틀린' 칸을 비운다 (2026-11 점검).
    공시 한 건이 백만원 대신 원 단위로 들어오면 그 분기는 수천 배로 튀고, 다음 분기는 그만큼 음수가 된다
    (예: 이큐셀 2025.2Q 매출 6,202억억 → 3Q -6,202억억). 정상 성장·급감은 많아야 수십 배라
    '나머지 분기 중앙값의 200배 넘게 벗어난 칸' 만 고장으로 본다. 반환: 비운 칸 수
    """
    n = 0
    # 매출이 음수인 분기는 계산 결과일 뿐 실제 값이 아니다 (2026-11 점검: 69곳).
    # 누적에서 앞 분기를 빼 만드는데, 연간 보고서에서 중단사업을 빼고 다시 쓰면 '연간 - 3분기 누적' 이 음수가 된다
    # (현대차증권 2025.2Q 매출 -3,713억, 동국S&C 2024.4Q -1,685억). 그 분기의 영업이익·순이익도 같은 이유로 믿을 수 없어 함께 비운다
    for x in q:
        if x.get("rev") is not None and x["rev"] < 0:
            x["rev"] = x["op"] = x["ni"] = None
            n += 1
    for key in ("rev", "op", "ni"):
        vals = [abs(x[key]) for x in q if x.get(key)]
        if len(vals) < 5:
            continue
        for x in q:
            v = x.get(key)
            if not v:
                continue
            others = sorted(abs(y[key]) for y in q if y is not x and y.get(key))
            med = others[len(others) // 2] if others else 0
            ref = med if key == "rev" else max(med, max((abs(y.get("rev") or 0) for y in q), default=0) * 0.01)
            if ref > 0 and abs(v) > 200 * ref:
                x[key] = None
                n += 1
    return n


def save_company(code, data):
    """
    값이 그대로면 파일을 건드리지 않는다.
    (updated 날짜만 바뀌는 커밋이 매번 쌓이는 걸 막는다)
    반환: True면 실제로 썼음
    """
    path = os.path.join(OUT_DIR, code + ".json")
    if data.get("annual"):
        clean_annual(data["annual"])
    if data.get("quarterly"):
        clean_quarters(data["quarterly"])
    if os.path.exists(path) and data_unchanged(path, data):
        return False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return True


CHECKED_PATH = os.path.join(OUT_DIR, "_checked.json")


def load_checked():
    try:
        with open(CHECKED_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:      # noqa: BLE001
        return {}


def save_checked(d):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CHECKED_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def recent_filers(days=12):
    """
    최근 며칠 사이 정기보고서(분기·반기·사업보고서)를 낸 상장사 {종목코드: 접수일 'YYYY-MM-DD'}.
    실적 시즌(5·8·11·3월 중순)에 막 발표한 회사부터 먼저 받기 위해 쓴다. 호출은 페이지당 1회(100건).
    """
    today = datetime.now(timezone(timedelta(hours=9))).date()
    bgn = (today - timedelta(days=days)).strftime("%Y%m%d")
    out = {}
    for page in range(1, 60):
        res = api_get("list.json", {"bgn_de": bgn, "end_de": today.strftime("%Y%m%d"), "pblntf_ty": "A",
                                    "page_no": page, "page_count": 100})
        if not res or str(res.get("status")) != "000":
            break
        for it in res.get("list") or []:
            code = (it.get("stock_code") or "").strip()
            nm = it.get("report_nm") or ""
            if not code or not any(k in nm for k in ("분기보고서", "반기보고서", "사업보고서")):
                continue
            d = it.get("rcept_dt") or ""
            d = "%s-%s-%s" % (d[:4], d[4:6], d[6:8]) if len(d) == 8 else ""
            if d > out.get(code, ""):
                out[code] = d
        if page >= int(res.get("total_page") or 1):
            break
    return out


def load_done(refresh_days=None):
    """
    이미 data/ 에 파일이 있는 종목.
    refresh_days 를 주면 그보다 오래된 파일은 '안 받은 것'으로 취급해 다시 받는다.
    반환: (건너뛸 코드 집합, {코드: updated날짜} — 오래된 것만)
    """
    done, stale = set(), {}
    if not os.path.isdir(OUT_DIR):
        return done, stale
    today = datetime.now(timezone(timedelta(hours=9))).date()
    checked = load_checked()
    for fn in os.listdir(OUT_DIR):
        if not (fn.endswith(".json") and fn[:-5].isdigit()):
            continue
        code = fn[:-5]
        if refresh_days is None:
            done.add(code)
            continue
        # 마지막으로 '확인한' 날 기준. 값이 안 바뀌어도 확인은 한 것으로 친다.
        ref = checked.get(code)
        if not ref:
            try:
                with open(os.path.join(OUT_DIR, fn), encoding="utf-8") as f:
                    ref = json.load(f).get("updated", "")
            except Exception:      # noqa: BLE001
                ref = ""
        try:
            age = (today - datetime.strptime(ref, "%Y-%m-%d").date()).days
        except Exception:      # noqa: BLE001
            age = 9999
        if age >= refresh_days:
            stale[code] = age
        else:
            done.add(code)
    return done, stale


FAILED_PATH = os.path.join(OUT_DIR, "_failed.json")


def load_failed():
    try:
        with open(FAILED_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:      # noqa: BLE001
        return {}
    # 6자리 종목코드가 아닌 항목은 잘못 기록된 것이므로 버린다
    return {k: v for k, v in d.items() if k.isdigit() and len(k) == 6}


def save_failed(d):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(FAILED_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


SCREEN_FIELDS = [
    "code", "name", "market", "years",
    "rev", "op", "ni", "margin", "netMargin",
    "roe", "roeAvg", "roa", "debt",
    "revCagr3", "revCagr5", "revCagr10", "opCagr5",
    "revStreak", "profitStreak", "lossCount", "marginStd", "turnaround",
    "dps", "payout", "yield", "dpsCagr5", "divYears", "divGrowYears",
    "qRev", "qOp", "qMargin", "qRevYoy", "qOpYoy",
    "yieldDart", "qPeriod", "qNew", "qTurn",
]


def _cagr(rows, key, n):
    """n년 연평균 성장률(%). 시작값이 0 이하면 계산 불가."""
    if len(rows) < n + 1:
        return None
    a, b = rows[-(n + 1)].get(key), rows[-1].get(key)
    if not a or not b or a <= 0 or b <= 0:
        return None
    return round((pow(b / a, 1.0 / n) - 1) * 100, 1)


def _r(v, nd=1):
    if v is None:
        return None
    x = round(v, nd)
    # 소수점이 필요 없으면 정수로 — screen.json 크기를 줄인다
    return int(x) if x == int(x) else x


def _equity(x):
    """자본총계. 공시의 계정 태그가 틀려 자본금(예: 현대백화점 2020~22년 1,170억)이
    잡힌 해가 있다. 자산 - 부채 와 5% 넘게 어긋나면 자산 - 부채 를 쓴다."""
    e, a, l = x.get("equity"), x.get("assets"), x.get("liab")
    if a and l is not None and a - l > 0 and (not e or abs(e - (a - l)) / (a - l) > 0.05):
        return round(a - l, 1)
    return e


def _yield_now(dps, px, dart):
    """시가배당률 = 최근 결산 주당배당금 ÷ 전일 종가.
    결산 뒤 액면분할을 하면 배당금은 옛 주식 기준, 주가는 새 주식 기준이라 몇 배로 튄다
    (대한제분 2026 분할: 37% ↔ 공시 2.6%). 10%를 넘고 공시값의 4배를 넘으면 분할로 보고 공시값을 쓴다.
    주가가 많이 오르내려 생긴 차이(삼성전기 0.9% → 0.2%)는 그대로 둔다. 공시값이 20%를 넘으면 그 값도 믿지 않는다."""
    ok_dart = _r(dart) if (dart is not None and 0 <= dart <= 20) else None
    if not (dps and px):
        return ok_dart
    y = dps / px * 100
    if y > 10 and (ok_dart is None or y > ok_dart * 4):
        return ok_dart
    return _r(y, 2)


def build_screen():
    """data/ 를 훑어 스크리닝용 지표를 미리 계산해 screen.json 으로 저장한다.
    API를 쓰지 않는다 — 이미 받아둔 파일만 읽는다.

    검증(2026-11)에서 고친 것:
      · 자본총계가 자본금으로 잘못 잡힌 해 → 자산 - 부채 로 바로잡는다 (_equity)
      · 분기 YoY 를 '다섯 칸 앞' 이 아니라 '작년 같은 분기' 와 견준다 (빠진 분기가 있으면 엉뚱한 분기와 비교했다)
      · 최근 사업보고서가 2년 넘게 없는 회사(상장폐지·금융업 등)는 뺀다
      · 최근 분기가 너무 오래된 회사는 분기 지표를 비운다
      · 해외기업(코드 9로 시작)은 외화 단위라 금액(매출·이익)을 비운다 — 비율 지표는 그대로"""
    this_year = datetime.now(timezone(timedelta(hours=9))).year
    files = []
    for fn in sorted(os.listdir(OUT_DIR)):
        if not (fn.endswith(".json") and fn[:-5].isdigit()):
            continue
        try:
            with open(os.path.join(OUT_DIR, fn), encoding="utf-8") as f:
                d0 = json.load(f)
            if d0.get("annual"):          # 분할 환산은 매번 다시 — 판정 규칙을 고치면 바로 반영된다
                adjust_for_splits(d0["annual"])
            if d0.get("annual"):          # 단위가 틀린 해는 바로잡는다
                clean_annual(d0["annual"])
            if d0.get("quarterly"):       # 단위가 틀린 분기는 비운다
                clean_quarters(d0["quarterly"])
            files.append((fn, d0))
        except Exception:      # noqa: BLE001
            continue
    # 가장 많은 회사의 최근 분기 (예: 2026.2Q) — 이보다 한 분기 넘게 늦으면 분기 지표를 비운다
    from collections import Counter
    lastq = Counter((d["quarterly"][-1]["y"], d["quarterly"][-1]["q"]) for _, d in files if d.get("quarterly"))
    ref_q = lastq.most_common(1)[0][0] if lastq else None
    # 가장 최근 분기 (3곳 이상 낸 분기 중) — 실적 시즌에 '이번 분기 발표' 회사만 고르기 위해
    # (결산월이 다른 회사는 분기 번호가 어긋나므로 '가장 많은 분기의 바로 다음 분기' 만 본다)
    newest_q = ref_q
    if ref_q:
        nxt = (ref_q[0], ref_q[1] + 1) if ref_q[1] < 4 else (ref_q[0] + 1, 1)
        if lastq.get(nxt, 0) >= 30:      # 시즌이 시작돼 30곳 넘게 냈을 때부터
            newest_q = nxt
    min_q = None
    if ref_q:
        min_q = (ref_q[0], ref_q[1] - 1) if ref_q[1] > 1 else (ref_q[0] - 1, 4)
    # 시가배당률은 현재 주가로 — 그때 샀다면 탭이 매일(평일 16:40) 받는 국내 종가(data/anchor.json)를 쓴다.
    # 사업보고서의 '현금배당수익률' 은 회사가 지난 결산 무렵 주가로 적은 값이라 지금과 다르고
    # (삼성전자 공시 1.5% / 지금 0.7%), 분기배당 회사는 기말배당만 넣은 경우도 있다 (현대차 1.9% / 3.4%).
    price, price_asof = {}, None
    try:
        with open(os.path.join(OUT_DIR, "anchor.json"), encoding="utf-8") as f:
            kr = (json.load(f).get("kr") or {})
        price_asof = kr.get("asof")
        for c, it in (kr.get("items") or {}).items():
            v = ((it or {}).get("now") or {}).get("v")
            if v and v > 0:
                price[c] = v
    except Exception:      # noqa: BLE001
        pass
    out = []
    for fn, d in files:
        if not (fn.endswith(".json") and fn[:-5].isdigit()):
            continue
        a = d.get("annual") or []
        q = d.get("quarterly") or []
        if not a:
            continue
        last = a[-1]
        if last.get("p", 0) < this_year - 2:          # 2024년 사업보고서도 없으면 지금 고르기엔 낡았다
            continue
        foreign = fn.startswith("9")

        rev, op, ni = last.get("rev"), last.get("op"), last.get("ni")
        eq, li, asset = _equity(last), last.get("liab"), last.get("assets")

        margin = _r(op / rev * 100) if rev else None
        netMargin = _r(ni / rev * 100) if (rev and ni is not None) else None
        roe = _r(ni / eq * 100) if (eq and eq > 0 and ni is not None) else None
        roa = _r(ni / asset * 100) if (asset and asset > 0 and ni is not None) else None
        debt = _r(li / eq * 100) if (eq and eq > 0 and li is not None) else None

        # 5년 평균 ROE
        roes = [x["ni"] / _equity(x) * 100 for x in a[-5:]
                if _equity(x) and _equity(x) > 0 and x.get("ni") is not None]
        roeAvg = _r(sum(roes) / len(roes)) if roes else None

        # 영업이익률 시계열 → 변동성
        margins = [x["op"] / x["rev"] * 100 for x in a if x.get("rev")]
        if len(margins) >= 3:
            mu = sum(margins) / len(margins)
            marginStd = _r((sum((m - mu) ** 2 for m in margins) / len(margins)) ** 0.5)
        else:
            marginStd = None

        # 연속 매출 증가
        revStreak = 0
        for i in range(len(a) - 1, 0, -1):
            if a[i].get("rev") and a[i - 1].get("rev") and a[i]["rev"] > a[i - 1]["rev"]:
                revStreak += 1
            else:
                break

        # 연속 흑자 / 적자 횟수 / 턴어라운드
        profitStreak = 0
        for x in reversed(a):
            if (x.get("op") or 0) > 0:
                profitStreak += 1
            else:
                break
        lossCount = sum(1 for x in a if (x.get("op") or 0) <= 0)
        turnaround = 1 if (len(a) >= 2 and (a[-1].get("op") or 0) > 0
                           and (a[-2].get("op") or 0) <= 0) else 0

        # 배당
        def dps_of(x):
            v = x.get("dps_adj")
            return v if v is not None else x.get("dps")
        dps = dps_of(last)
        if dps and dps > 1e6:          # 주당배당금이 100만원 넘으면 총액이 잘못 들어온 것 (와이엔텍 18억 '원')
            dps = None
        divYears = 0
        for x in reversed(a):
            if (dps_of(x) or 0) > 0:
                divYears += 1
            else:
                break
        divGrowYears = 0
        for i in range(len(a) - 1, 0, -1):
            c, pv = dps_of(a[i]) or 0, dps_of(a[i - 1]) or 0
            if c > pv > 0:
                divGrowYears += 1
            else:
                break
        paid = [x for x in a if (dps_of(x) or 0) > 0]
        if len(paid) >= 6:
            s0, s1 = dps_of(paid[-6]), dps_of(paid[-1])
            dpsCagr5 = _r((pow(s1 / s0, 1 / 5.0) - 1) * 100) if s0 and s0 > 0 else None
        else:
            dpsCagr5 = None

        # 분기
        qRev = qOp = qMargin = qRevYoy = qOpYoy = qPeriod = qNew = qTurn = None
        if q and (min_q is None or (q[-1]["y"], q[-1]["q"]) >= min_q):
            lq = q[-1]
            qPeriod = lq["y"] * 10 + lq["q"]                     # 20263 = 2026년 3분기
            qNew = 1 if (lq["y"], lq["q"]) == newest_q else 0
            qRev, qOp = lq.get("rev"), lq.get("op")
            qMargin = _r(qOp / qRev * 100) if (qRev and qOp is not None) else None
            y0 = next((x for x in q if x["y"] == lq["y"] - 1 and x["q"] == lq["q"]), None)   # 작년 같은 분기
            if y0:
                if y0.get("rev") and qRev is not None:
                    qRevYoy = _r((qRev / y0["rev"] - 1) * 100)
                if y0.get("op") and y0["op"] > 0 and qOp is not None:
                    qOpYoy = _r((qOp / y0["op"] - 1) * 100)
                if y0.get("op") is not None and qOp is not None:   # 작년 같은 분기 대비 흑자·적자 전환
                    qTurn = 1 if (y0["op"] < 0 < qOp) else -1 if (qOp < 0 < y0["op"]) else 0
        if foreign:                                     # 외화 단위 — 금액은 비우고 비율만 남긴다
            rev = op = ni = qRev = qOp = None

        out.append([
            d.get("code", fn[:-5]), d.get("name", ""), d.get("market", ""), len(a),
            _r(rev, 0), _r(op, 0), _r(ni, 0), margin, netMargin,
            roe, roeAvg, roa, debt,
            _cagr(a, "rev", 3), _cagr(a, "rev", 5), _cagr(a, "rev", 9), _cagr(a, "op", 5),
            revStreak, profitStreak, lossCount, marginStd, turnaround,
            _r(dps, 0), _r(last.get("payout")),
            # 최근 결산 주당배당금 ÷ 전일 종가. 종가가 없으면 공시값
            _yield_now(dps, price.get(d.get("code", fn[:-5])), last.get("yield")),
            dpsCagr5, divYears, divGrowYears,
            _r(qRev, 0), _r(qOp, 0), qMargin, qRevYoy, qOpYoy,
            _r(last.get("yield")), qPeriod, qNew, qTurn,
        ])

    path = os.path.join(OUT_DIR, "screen.json")
    payload = {"updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
               "price_asof": price_asof, "fields": SCREEN_FIELDS, "rows": out}
    if not (os.path.exists(path) and data_unchanged(path, payload)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return len(out)


def rebuild_index():
    """data/ 폴더를 통째로 훑어 index.json 을 다시 만든다.
    이번 실행에서 받은 것만이 아니라 그동안 모은 전부가 들어간다."""
    items = []
    for fn in sorted(os.listdir(OUT_DIR)):
        if not fn.endswith(".json") or not fn[:-5].isdigit():
            continue
        try:
            with open(os.path.join(OUT_DIR, fn), encoding="utf-8") as f:
                d = json.load(f)
            items.append({"name": d.get("name", fn[:-5]), "code": d.get("code", fn[:-5]),
                          "market": d.get("market", ""), "sector": d.get("sector", ""),
                          "updated": d.get("updated", "")})
        except Exception:  # noqa: BLE001
            continue
    items.sort(key=lambda x: x["name"])
    by_market = {}
    for it in items:
        key = it.get("market") or "미분류"
        by_market[key] = by_market.get(key, 0) + 1
    path = os.path.join(OUT_DIR, "index.json")
    payload = {"updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
               "count": len(items), "markets": by_market, "companies": items}
    # 목록이 그대로면 날짜만 바꿔 다시 쓰지 않는다
    if not (os.path.exists(path) and data_unchanged(path, payload)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return len(items)


def show_dividend(corp_map, code, year):
    """특정 종목·연도의 배당 원본 응답을 그대로 보여준다."""
    info = corp_map.get(code)
    if not info:
        log("%s : corpCode.xml 에 없습니다" % code)
        return
    log("\n=== %s (%s) %d년 배당 원본 ===" % (info["name"], code, year))
    res = api_get("alotMatter.json", {
        "corp_code": info["corp_code"], "bsns_year": str(year),
        "reprt_code": REPRT["YEAR"],
    })
    if not res:
        log("응답 없음")
        return
    if res.get("status") != "000":
        log("status=%s  %s" % (res.get("status"), res.get("message")))
        return
    log("%-26s %-10s %14s %14s" % ("구분(se)", "주식종류", "당기", "전기"))
    log("-" * 68)
    for r in res.get("list", []):
        log("%-26s %-10s %14s %14s" % (
            (r.get("se") or "")[:24], (r.get("stock_knd") or "-")[:8],
            r.get("thstrm") or "-", r.get("frmtrm") or "-"))
    log("-" * 68)
    got = fetch_dividend(info["corp_code"], year)
    log("스크립트가 고른 값 -> DPS=%s  배당성향=%s  시가배당률=%s"
        % (got["dps"], got["payout"], got["yield"]))


def verify(tickers, corp_map):
    """API를 쓰지 않고 종목코드가 실제로 어떤 회사에 붙는지만 확인한다."""
    ok, bad, mismatch = [], [], []
    for code, alias in tickers:
        info = corp_map.get(code)
        if not info:
            bad.append((code, alias))
        else:
            ok.append((code, alias, info["name"]))
            if alias and alias.replace(" ", "") != info["name"].replace(" ", ""):
                mismatch.append((code, alias, info["name"]))

    log("\n%-8s %-22s %s" % ("코드", "내가 지정한 이름", "DART 정식명칭"))
    log("-" * 64)
    for code, alias, name in ok:
        flag = "  <- 다름" if any(m[0] == code for m in mismatch) else ""
        log("%-8s %-22s %s%s" % (code, alias or "(없음)", name, flag))

    if bad:
        log("\n!! corpCode.xml 에 없는 코드 %d개 — 오타이거나 상장폐지되었습니다" % len(bad))
        for code, alias in bad:
            log("   %s  %s" % (code, alias or ""))
        log("   tickers.txt 에서 이 줄들을 지우거나 코드를 고치세요.")

    log("\n확인됨 %d개 / 못 찾음 %d개 / 이름 다름 %d개" % (len(ok), len(bad), len(mismatch)))
    log("이름이 다른 건 대부분 정상입니다 (KT&G ↔ 케이티앤지).")
    log("전혀 다른 회사가 보이면 그 코드가 잘못된 것이니 고쳐주세요.")
    log("\nAPI 호출: 0회 (캐시된 corpCode.xml만 읽음)")


def lookup(term):
    """corpCode.xml에서 종목코드 또는 회사명으로 검색해 원본 항목을 보여준다."""
    cached = os.path.join(CACHE_DIR, "corpCode.xml")
    if not os.path.exists(cached):
        load_corp_map()
    root = ET.parse(cached).getroot()

    total = with_stock = 0
    hits = []
    for node in root.iter("list"):
        total += 1
        stock = (node.findtext("stock_code") or "").strip()
        name = (node.findtext("corp_name") or "").strip()
        if stock:
            with_stock += 1
        if term == stock or term in name:
            hits.append((
                (node.findtext("corp_code") or "").strip(),
                name, stock,
                (node.findtext("modify_date") or "").strip(),
            ))

    log("전체 항목 %d건 / 종목코드 있는 항목 %d건" % (total, with_stock))
    log("검색어 '%s' 일치: %d건" % (term, len(hits)))
    if not hits:
        log("  -> corpCode.xml 안에 없습니다. 캐시가 오래됐을 수 있으니")
        log("     .cache/corpCode.xml 을 지우고 다시 실행해 보세요.")
    for corp, name, stock, mod in hits[:20]:
        log("  corp_code=%s  stock_code=%-8s  %s  (수정 %s)"
            % (corp, stock or "(없음)", name, mod))


def load_tickers(args):
    """
    인자 > tickers.txt > 기본 3종목 순으로 목록을 정한다.
    tickers.txt 는 "코드  표시할이름" 형식이며, 이름을 적으면
    DART 정식명칭(케이티앤지) 대신 그 이름(KT&G)이 카드에 쓰인다.
    """
    if args:
        return [(c, None) for c in args]
    path = "tickers_all.txt" if "--all" in sys.argv else "tickers.txt"
    if os.path.exists(path):
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                code = parts[0].strip()
                alias = parts[1].strip() if len(parts) > 1 else None
                if code.isdigit() and len(code) == 6:
                    out.append((code, alias or None))
                else:
                    log("  ? 무시된 줄: %s" % line)
        if out:
            named = sum(1 for _, a in out if a)
            log("tickers.txt 에서 %d종목 읽음 (표시명 지정 %d건)" % (len(out), named))
            return out
    return [(c, None) for c in DEFAULT_TICKERS]


def parse_args():
    """--budget 3000 처럼 옵션이 값을 가지는 경우, 그 값을 종목코드로 오인하지 않게 한다."""
    takes_value = {"--budget", "--refresh-days", "--dividend", "--max-minutes"}
    args, skip = [], False
    for i, a in enumerate(sys.argv[1:]):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            if a in takes_value:
                skip = True
            continue
        args.append(a)
    return args


def main():
    global DEBUG, API_KEY
    args = parse_args()
    DEBUG = "--debug" in sys.argv
    API_KEY = get_key()

    if "--lookup" in sys.argv:
        if not args:
            log("사용법: python3 collect.py --lookup 105560   (또는 --lookup KB금융)")
            return
        for t in args:
            log("\n--- '%s' 조회 ---" % t)
            lookup(t)
        return

    tickers = load_tickers(args)
    latest_year = datetime.now().year     # 분기보고서는 올해 것도 이미 나와 있다

    corp_map = load_corp_map()

    if "--dividend" in sys.argv:
        # 사용법: python3 collect.py --dividend 2025 005930
        yr = None
        for i, a in enumerate(sys.argv):
            if a == "--dividend" and i + 1 < len(sys.argv):
                try:
                    yr = int(sys.argv[i + 1])
                except ValueError:
                    pass
        if yr is None or not args:
            log("사용법: python3 collect.py --dividend 2025 005930")
            return
        for code in args:
            show_dividend(corp_map, code, yr)
        return

    if "--build-tickers" in sys.argv:
        build_tickers_file(corp_map)
        return

    if "--verify" in sys.argv:
        verify(tickers, corp_map)
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- 이번 실행에서 쓸 호출 예산 ----
    budget = 15000
    for i, a in enumerate(sys.argv):
        if a == "--budget" and i + 1 < len(sys.argv):
            try:
                budget = int(sys.argv[i + 1])
            except ValueError:
                pass

    # ---- 시간 상한 (분) ----
    max_minutes = None
    for i, a in enumerate(sys.argv):
        if a == "--max-minutes" and i + 1 < len(sys.argv):
            try:
                max_minutes = float(sys.argv[i + 1])
            except ValueError:
                pass

    # ---- 갱신 주기 ----
    refresh_days = None
    for i, a in enumerate(sys.argv):
        if a == "--refresh-days" and i + 1 < len(sys.argv):
            try:
                refresh_days = int(sys.argv[i + 1])
            except ValueError:
                pass

    # ---- 이미 받은 것 / 이전에 실패한 것은 건너뛴다 ----
    force = "--force" in sys.argv
    if force:
        done, stale = set(), {}
    else:
        done, stale = load_done(refresh_days)
    failed = load_failed()
    skip_reasons = ("재무 데이터 없음(금융업?)", "corpCode 매핑 실패")

    fresh, refresh = [], []
    for code, alias in tickers:
        if code in done:
            continue
        if not force and failed.get(code, {}).get("reason") in skip_reasons:
            continue
        if code in stale:
            refresh.append((stale[code], code, alias))
        else:
            fresh.append((code, alias))

    # 아직 한 번도 안 받은 종목이 먼저, 그다음 오래된 순서로 갱신
    refresh.sort(reverse=True)
    todo = fresh + [(c, a) for _, c, a in refresh]

    # 실적 시즌: 최근 정기보고서를 냈는데 그 뒤로 아직 안 받은 회사를 맨 앞으로 (오늘의 실적 발표 카드용)
    if not force and "--no-filers" not in sys.argv:
        try:
            filers = recent_filers()
        except Exception as e:      # noqa: BLE001
            filers = {}
            log("최근 공시 목록을 못 받았습니다: %r" % e)
        if filers:
            chk = load_checked()
            alias_of = dict(tickers)
            first = [(c, alias_of.get(c)) for c, d in sorted(filers.items(), key=lambda x: x[1])
                     if c in alias_of and chk.get(c, "") <= d
                     and failed.get(c, {}).get("reason") not in skip_reasons]
            if first:
                fc = set(c for c, _ in first)
                todo = first + [(c, a) for c, a in todo if c not in fc]
                log("최근 정기보고서 제출 %d곳 중 %d곳을 먼저 받습니다." % (len(filers), len(first)))

    log("\n목록 %d종목 | 최신 %d | 미수집 %d | 갱신대상 %d | 이전 실패(건너뜀) %d"
        % (len(tickers), len(done), len(fresh), len(refresh), len(failed)))
    if refresh_days is not None:
        log("갱신 주기 %d일 — %d일 넘은 데이터는 다시 받습니다." % (refresh_days, refresh_days))
        if refresh:
            log("가장 오래된 데이터: %d일 전" % refresh[0][0])

    if not todo:
        n = rebuild_index()
        build_screen()
        log("받을 종목이 없습니다. index.json / screen.json 갱신 완료 (%d종목)" % n)
        if refresh_days is None:
            log("주기적으로 갱신하려면 --refresh-days 9 를 붙이세요.")
        else:
            log("모든 데이터가 %d일 이내입니다." % refresh_days)
        return

    can_do = min(budget // 43, len(todo))
    log("예산 %s회 -> 이번에 약 %d종목 처리 예상 (%.0f분)"
        % (f"{budget:,}", can_do, can_do * 10.6 / 60))
    if max_minutes:
        log("시간 상한 %.0f분" % max_minutes)

    started = time.time()
    report = []
    stopped_early = False
    unchanged = 0
    checked = load_checked()
    today_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    for i, (code, alias) in enumerate(todo, 1):
        if ABORT:
            log("\n>> 중단: %s" % ABORT)
            stopped_early = True
            break

        if max_minutes and (time.time() - started) / 60 >= max_minutes:
            log("\n>> 시간 상한 %.0f분에 도달했습니다. 다음 실행에서 이어갑니다." % max_minutes)
            stopped_early = True
            break

        if _call_count + 45 > budget:
            log("\n>> 예산 %s회에 도달했습니다. 여기서 멈추고 다음 실행에서 이어갑니다."
                % f"{budget:,}")
            stopped_early = True
            break

        log("\n[%d/%d] (호출 %d/%s)" % (i, len(todo), _call_count, f"{budget:,}"))
        try:
            data, reason = collect_company(code, corp_map, latest_year, alias)
        except Exception as e:                       # noqa: BLE001
            log("! 예외 발생: %r" % e)
            failed[code] = {"name": alias or "?", "reason": "예외: %s" % type(e).__name__}
            report.append((code, alias or "?", "실패", 0, 0, "예외"))
            continue

        if not data:
            if ABORT:
                # 한도 초과·키 오류 때문에 비어 있는 것이므로 실패로 남기지 않는다
                log(">> 중단: %s" % ABORT)
                stopped_early = True
                break
            failed[code] = {"name": alias or "?", "reason": reason}
            report.append((code, alias or "?", "실패", 0, 0, reason))
            continue

        failed.pop(code, None)
        worst = data.pop("_worst_gap", None)
        wrote = save_company(code, data)
        checked[code] = today_str
        if not wrote:
            unchanged += 1

        na, nq = len(data["annual"]), len(data["quarterly"])
        if na < YEARS or nq < QUARTERS:
            status, note = "부분", "연간 %d/%d, 분기 %d/%d" % (na, YEARS, nq, QUARTERS)
        elif worst is not None and worst >= 2:
            status, note = "검산", "분기합 차이 %.1f%%" % worst
        elif not wrote:
            status, note = "동일", "값 변동 없음"
        else:
            status, note = "정상", ""
        report.append((code, data["name"], status, na, nq, note))

    save_failed(failed)
    save_checked(checked)
    total_in_index = rebuild_index()
    screen_n = build_screen()

    # ---- 요약 ----
    log("\n" + "=" * 62)
    log("%-8s %-16s %-6s %-5s %-5s %s" % ("코드", "기업명", "상태", "연간", "분기", "비고"))
    log("-" * 62)
    for code, name, status, na, nq, note in report:
        log("%-8s %-16s %-6s %-5s %-5s %s" % (code, name[:14], status, na, nq, note))
    log("-" * 62)

    counts = {}
    for r in report:
        counts[r[2]] = counts.get(r[2], 0) + 1
    log("전체 %d종목  |  " % len(report) +
        "  ".join("%s %d" % (k, v) for k, v in sorted(counts.items())))
    log("소요 %.1f분  |  API 호출 %d회" % ((time.time() - started) / 60, _call_count))

    log("index.json 총 %d종목  |  screen.json %d종목  |  누적 실패 %d종목"
        % (total_in_index, screen_n, len(failed)))
    try:
        with open(os.path.join(OUT_DIR, "index.json"), encoding="utf-8") as f:
            mk = json.load(f).get("markets", {})
        if mk:
            log("  시장별: " + "  ".join("%s %d" % (k, v) for k, v in sorted(mk.items())))
    except Exception:      # noqa: BLE001
        pass
    if unchanged:
        log("값이 그대로여서 파일을 다시 쓰지 않은 종목: %d개" % unchanged)

    remaining = len(todo) - len(report)
    if ABORT:
        log("\n중단 사유: %s" % ABORT)
        log("남은 종목 %d개. 한도는 매일 자정(한국시간)에 초기화되니," % remaining)
        log("내일 같은 명령을 그대로 다시 실행하면 이어서 받습니다.")
        log("여기까지 받은 종목은 이미 저장됐고 실패로 기록되지 않았습니다.")
    elif stopped_early or remaining > 0:
        log("\n남은 종목 %d개. 같은 명령을 다시 실행하면 이어서 받습니다." % remaining)
    else:
        log("\n목록의 모든 종목을 처리했습니다.")

    bad = [r for r in report if r[2] != "정상"]
    if bad:
        log("\n확인이 필요한 종목: " + ", ".join("%s(%s)" % (r[1], r[2]) for r in bad))
        log("자세히 보려면:  python3 collect.py --debug %s" % bad[0][0])
    else:
        log("\n전 종목 정상입니다.")


API_KEY = ""

if __name__ == "__main__":
    main()
