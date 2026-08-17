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
}

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
    _fs_cache[key] = rows
    return rows


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
    is_rows = [r for r in rows if r.get("sj_div") in ("IS", "CIS")]
    pool = is_rows or rows

    def value_of(r):
        if cumulative:
            v = to_num(r.get("thstrm_add_amount"))
            if v is not None:
                return v
        return to_num(r.get("thstrm_amount"))

    for aid in cand["ids"]:
        for r in pool:
            if (r.get("account_id") or "").strip() == aid:
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


def eok(v):
    """원 단위 -> 억원. 소수 1자리."""
    return None if v is None else round(v / 1e8, 1)


# ------------------------------------------------- 배당

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
        if rev is None or op is None:
            log("  - %d년 매출/영업이익 매칭 실패, 건너뜀" % y)
            continue
        div = fetch_dividend(corp_code, y)
        rows.append({
            "p": y, "rev": eok(rev), "op": eok(op), "ni": eok(ni),
            "dps": div["dps"], "payout": div["payout"], "yield": div["yield"],
        })
        log("  %d년  매출 %s억  영업이익 %s억  DPS %s" %
            (y, f"{eok(rev):,.0f}", f"{eok(op):,.0f}",
             f"{div['dps']:,.0f}원" if div["dps"] else "-"))
    return rows[-YEARS:]


def collect_quarterly(corp_code, latest_year):
    """
    DART엔 '2분기 단독' 보고서가 없다. 누적에서 빼서 각 분기를 만든다.
        1Q = 1분기보고서
        2Q = 반기 - 1Q
        3Q = 3분기보고서(누적) - 반기
        4Q = 사업보고서(연간) - 3Q누적

    올해 분기보고서는 이미 나와 있으므로 현재 연도까지 훑는다.
    (분기보고서 마감은 분기 종료 후 45일, 반기는 60일)
    아직 안 나온 보고서는 자연스럽게 None이 되어 건너뛴다.
    """
    out = []
    for y in range(latest_year - 3, latest_year + 1):
        cum = {}
        for tag, code in (("Q1", REPRT["Q1"]), ("HALF", REPRT["HALF"]),
                          ("Q3", REPRT["Q3"]), ("YEAR", REPRT["YEAR"])):
            fs = fetch_fs(corp_code, y, code)
            if not fs:
                continue
            use_cum = tag != "YEAR"
            cum[tag] = {
                "rev": pick_account(fs, "rev", cumulative=use_cum),
                "op": pick_account(fs, "op", cumulative=use_cum),
                "ni": pick_account(fs, "ni", cumulative=use_cum),
            }

        def diff(a, b):
            if a is None:
                return None
            if b is None:
                return a
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
            if rev is None or op is None:
                continue
            out.append({"y": y, "q": q, "rev": eok(rev), "op": eok(op), "ni": eok(ni)})
            log("  %d.%dQ  매출 %s억  영업이익 %s억" % (y, q, f"{eok(rev):,.0f}", f"{eok(op):,.0f}"))

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

    return {
        "name": display,
        "legal_name": info["name"],
        "code": code,
        "market": "",
        "sector": "",
        "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
        "annual": annual,
        "quarterly": quarterly,
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


def save_company(code, data):
    """
    값이 그대로면 파일을 건드리지 않는다.
    (updated 날짜만 바뀌는 커밋이 매번 쌓이는 걸 막는다)
    반환: True면 실제로 썼음
    """
    path = os.path.join(OUT_DIR, code + ".json")
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
    path = os.path.join(OUT_DIR, "index.json")
    payload = {"updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
               "count": len(items), "companies": items}
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
    takes_value = {"--budget", "--refresh-days", "--dividend"}
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

    log("\n목록 %d종목 | 최신 %d | 미수집 %d | 갱신대상 %d | 이전 실패(건너뜀) %d"
        % (len(tickers), len(done), len(fresh), len(refresh), len(failed)))
    if refresh_days is not None:
        log("갱신 주기 %d일 — %d일 넘은 데이터는 다시 받습니다." % (refresh_days, refresh_days))
        if refresh:
            log("가장 오래된 데이터: %d일 전" % refresh[0][0])

    if not todo:
        n = rebuild_index()
        log("받을 종목이 없습니다. index.json 갱신 완료 (%d종목)" % n)
        if refresh_days is None:
            log("주기적으로 갱신하려면 --refresh-days 9 를 붙이세요.")
        else:
            log("모든 데이터가 %d일 이내입니다." % refresh_days)
        return

    can_do = min(budget // 43, len(todo))
    log("예산 %s회 -> 이번에 약 %d종목 처리 예상 (%.0f분)"
        % (f"{budget:,}", can_do, can_do * 10.6 / 60))

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

    log("index.json 총 %d종목  |  누적 실패 %d종목 (data/_failed.json)"
        % (total_in_index, len(failed)))
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
