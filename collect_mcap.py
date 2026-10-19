#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 시가총액을 받아 data/mcap.json 에 적는다 — '시가총액' 탭(mcap.html)이 읽는다.

  python3 collect_mcap.py            받기 (네이버 금융, 키 필요 없음 · 호출 약 400회 · 3~5분)
  python3 collect_mcap.py --show     받아둔 파일만 보기
  python3 collect_mcap.py --probe    네이버 페이지 모양만 확인 (호출 6회) → mcap_probe.txt
  python3 collect_mcap.py --rename   받아둔 파일의 업종 이름만 띄어 쓴 이름으로 (호출 0회)

받는 것
  1. 코스피·코스닥 전 종목 시가총액 (네이버 시가총액 순위표, 시장마다 약 40쪽)
  2. 업종 목록과 업종별 종목 (네이버 업종별 시세, 약 80개 업종)
  3. 테마 목록과 테마별 종목 (네이버 테마별 시세, 약 260개 테마)
업종·테마 안의 종목은 1번의 시가총액으로 줄 세운다.

국내 실적 목록(data/index.json)과 실적 수집에서 빠진 금융사(data/_failed.json)의 보통주만 남긴다
— ETF·우선주·스팩은 빠진다.
올해 등락률(원 테두리 색)은 연간 수익률 자료(data/returns.json)의 올해 값을 쓴다.
시가총액 순위표를 못 받으면 아무것도 바꾸지 않고 끝낸다 (전날 파일이 그대로 남는다).
업종·테마만 실패하면 전날 받은 업종·테마를 그대로 둔다.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "mcap.json")
TOP_MARKET = 60          # 시장별 상위 몇 종목을 바로 쓸 수 있게 적어 둘지
TOP_GROUP = 60           # 업종·테마마다 상위 몇 종목까지 적을지
BASE = "https://finance.naver.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MARKETS = (("kospi", 0), ("kosdaq", 1))
CALLS = [0]


def log(*a):
    print(*a, flush=True)


def decode(raw, ctype=""):
    """네이버 금융은 예전엔 EUC-KR, 지금은 화면마다 UTF-8 이기도 하다. 머리글·meta 를 보고,
    없으면 UTF-8 로 읽어 보고 안 되면 EUC-KR."""
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I) or \
        re.search(rb'charset=["\']?([\w-]+)', raw[:2000], re.I)
    if m:
        enc = m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)
        try:
            return raw.decode(enc)
        except Exception:                     # noqa: BLE001
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("euc-kr", "replace")


def get(url, enc=None, tries=3):
    for i in range(tries):
        try:
            CALLS[0] += 1
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                return raw.decode(enc, "replace") if enc else decode(raw, r.headers.get("Content-Type", ""))
        except Exception:                     # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    return ""


def num(s):
    s = re.sub(r"[^\d.\-]", "", str(s or ""))
    try:
        return float(s)
    except ValueError:
        return None


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>|\s+", " ", s)).strip()


def last_close():
    """값이 어느 날 종가인지. 주말에 받으면 금요일, 평일 장 마감(15:30) 전에 받으면 전 영업일.
    공휴일은 모른다 — 공휴일에 받으면 그 전날 값인데 날짜만 공휴일로 찍힌다."""
    now = datetime.now(KST)
    d = now.date()
    if d.weekday() < 5 and (now.hour, now.minute) < (15, 30):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


# ------------------------------------------------------------ 1. 시가총액 (전 종목)

def market_page(sosok, page):
    """시가총액 순위표 한 쪽. [(코드, 이름, 시총억)], 마지막 쪽 번호"""
    t = get("%s/sise/sise_market_sum.naver?sosok=%d&page=%d" % (BASE, sosok, page))
    heads = [re.sub(r"<[^>]+>|\s", "", h) for h in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
    if "시가총액" not in heads:
        raise RuntimeError("시가총액 표 머리글을 못 찾음")
    i_cap = heads.index("시가총액")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        m = re.search(r'code=(\d{6})"[^>]*>([^<]+)</a>', tr)
        if not m:
            continue
        tds = [re.sub(r"<[^>]+>|\s", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) > i_cap and num(tds[i_cap]):
            rows.append((m.group(1), html.unescape(m.group(2)).strip(), num(tds[i_cap])))
    last = max([int(x) for x in re.findall(r"sise_market_sum\.naver\?&?sosok=%d&(?:amp;)?page=(\d+)" % sosok, t)] or [page])
    return rows, last


def caps_mobile(key):
    """네이버 증권 모바일 JSON — 시가총액 순, marketValue 는 억원. 빈 쪽이 나올 때까지."""
    mk = key.upper()
    out, page = {}, 1
    while page <= 60:
        j = json.loads(get("https://m.stock.naver.com/api/stocks/marketValue/%s?page=%d&pageSize=100" % (mk, page), "utf-8"))
        rows = j.get("stocks", [])
        if not rows:
            break
        for s in rows:
            cap = num(s.get("marketValue"))
            if s.get("itemCode") and cap:
                out[s["itemCode"]] = {"n": s.get("stockName", ""), "c": cap, "m": key}
        page += 1
        time.sleep(0.15)
    return out


def all_caps():
    caps = {}
    for key, sosok in MARKETS:
        try:
            got = caps_mobile(key)
            if len(got) > 200:
                caps.update(got)
                log("  %s %d종목 (모바일)" % (key, len(got)))
                continue
        except Exception as e:                # noqa: BLE001
            log("  %s 모바일 실패: %s — 표로 받습니다" % (key, e))
        page, last = 1, 1
        while page <= last:
            rows, lp = market_page(sosok, page)
            last = max(last, lp)
            for code, name, cap in rows:
                caps[code] = {"n": name, "c": cap, "m": key}
            page += 1
            time.sleep(0.15)
        log("  %s %d종목 (표 %d쪽)" % (key, sum(1 for v in caps.values() if v["m"] == key), last))
    return caps


# ------------------------------------------------------------ 2·3. 업종 · 테마

def group_list(kind):
    """[(번호, 이름)] — kind 는 upjong(업종) 또는 theme(테마)"""
    seen, out = set(), []
    pages = [1] if kind == "upjong" else range(1, 30)
    for p in pages:
        url = (BASE + "/sise/sise_group.naver?type=upjong") if kind == "upjong" \
            else (BASE + "/sise/theme.naver?&page=%d" % p)
        t = get(url)
        got = 0
        for no, name in re.findall(r'sise_group_detail\.naver\?type=%s&(?:amp;)?no=(\d+)"[^>]*>(.*?)</a>' % kind, t, re.S):
            if no in seen:
                continue
            seen.add(no)
            out.append((no, clean(name)))
            got += 1
        if not got:                            # 테마 쪽 끝
            break
        time.sleep(0.15)
    return out


def group_members(kind, no):
    t = get(BASE + "/sise/sise_group_detail.naver?type=%s&no=%s" % (kind, no))
    return list(dict.fromkeys(re.findall(r"/item/main\.naver\?code=(\d{6})", t)))


# 네이버 업종 이름은 띄어쓰기가 없다 (반도체와반도체장비). 화면·카드에는 띄어 쓴 이름을 쓴다.
# 붙여 쓴 이름이 열쇠라서, 네이버가 새 업종을 만들면 그 업종만 네이버 이름 그대로 나온다.
UPJONG_NAME = {re.sub(r"[\s]", "", n): n for n in [
    "전기제품", "화학", "에너지 장비 및 서비스", "비철금속", "IT 서비스",
    "백화점과 일반 상점", "자동차", "철강", "기계", "통신 장비",
    "전자 장비와 기기", "건강관리 기술", "방송과 엔터테인먼트", "제약", "생물공학",
    "전기 장비", "판매 업체", "반도체와 반도체 장비", "자동차 부품", "항공사",
    "석유와 가스", "우주항공과 국방", "출판", "전기 유틸리티", "건설",
    "핸드셋", "창업투자", "생명보험", "건강관리 장비와 용품", "복합 유틸리티",
    "복합기업", "손해보험", "도로와 철도 운송", "건강관리 업체 및 서비스", "무역회사와 판매 업체",
    "게임 엔터테인먼트", "생명과학 도구 및 서비스", "가스 유틸리티", "증권", "디스플레이 장비 및 부품",
    "포장재", "해운사", "전자제품", "양방향 미디어와 서비스", "건축자재",
    "광고", "건축제품", "항공화물 운송과 물류", "교육 서비스", "호텔, 레스토랑, 레저",
    "전문 소매", "다각화된 소비자 서비스", "상업 서비스와 공급품", "음료", "무선 통신 서비스",
    "인터넷과 카탈로그 소매", "식품", "디스플레이 패널", "기타", "소프트웨어",
    "다각화된 통신 서비스", "부동산", "종이와 목재", "가구", "문구류",
    "섬유, 의류, 신발, 호화품", "운송 인프라", "레저용 장비와 제품", "담배", "조선",
    "은행", "화장품", "가정용 기기와 용품", "카드", "컴퓨터와 주변기기",
    "식품과 기본 식료품 소매", "사무용 전자제품", "가정용품", "기타 금융",
]}


# 카드 제목용 짧은 이름 — 고르는 목록에는 위의 전체 이름, 카드 제목에는 이 이름을 쓴다.
# 여기 없는 업종은 전체 이름 그대로. 바꾸고 싶으면 오른쪽만 고치면 된다.
UPJONG_SHORT = {
    "반도체와 반도체 장비": "반도체",
    "전자 장비와 기기": "전자 장비",
    "우주항공과 국방": "방산·우주항공",
    "석유와 가스": "석유·가스",
    "에너지 장비 및 서비스": "에너지 장비",
    "디스플레이 장비 및 부품": "디스플레이 장비",
    "건강관리 장비와 용품": "의료기기",
    "건강관리 업체 및 서비스": "헬스케어 서비스",
    "생명과학 도구 및 서비스": "바이오 도구",
    "방송과 엔터테인먼트": "방송·엔터",
    "게임 엔터테인먼트": "게임",
    "양방향 미디어와 서비스": "인터넷 플랫폼",
    "섬유, 의류, 신발, 호화품": "패션·의류",
    "호텔, 레스토랑, 레저": "호텔·레저",
    "백화점과 일반 상점": "백화점·유통",
    "식품과 기본 식료품 소매": "식료품 소매",
    "인터넷과 카탈로그 소매": "온라인 쇼핑",
    "다각화된 통신 서비스": "통신 서비스",
    "다각화된 소비자 서비스": "소비자 서비스",
    "무선 통신 서비스": "무선 통신",
    "항공화물 운송과 물류": "물류",
    "도로와 철도 운송": "육상 운송",
    "무역회사와 판매 업체": "종합상사",
    "상업 서비스와 공급품": "상업 서비스",
    "컴퓨터와 주변기기": "컴퓨터",
    "가정용 기기와 용품": "생활가전",
    "레저용 장비와 제품": "레저용품",
    "건강관리 기술": "헬스케어 IT",
}


def short_name(name):
    return UPJONG_SHORT.get(name, "")


def nice_name(kind, name):
    if kind in ("upjong", "industry"):
        return UPJONG_NAME.get(re.sub(r"\s", "", name), name)
    return name


# ---- 네이버 증권 모바일 JSON (새 네이버 증권 화면이 쓰는 데이터) ----
MKIND = {"upjong": "industry", "theme": "theme"}


def _lists(j):
    """JSON 안의 '사전 목록'들을 모두 꺼낸다 (키 이름이 바뀌어도 찾게)"""
    out = []
    if isinstance(j, list):
        if j and all(isinstance(x, dict) for x in j):
            out.append(j)
        for x in j:
            out += _lists(x)
    elif isinstance(j, dict):
        for v in j.values():
            out += _lists(v)
    return out


def _pick(d, *keys):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def m_group_list(kind):
    out, seen = [], set()
    for page in range(1, 20):
        try:
            j = json.loads(get("https://m.stock.naver.com/api/stocks/%s?page=%d&pageSize=100" % (MKIND[kind], page), "utf-8"))
        except urllib.error.HTTPError as e:
            if page > 1 and e.code == 404:     # 마지막 쪽 다음은 404 로 끝난다
                break
            raise
        got = 0
        for lst in _lists(j):
            for g in lst:
                no, name = _pick(g, "no", "groupNo", "id", "code"), _pick(g, "name", "groupName", "title")
                if no is None or not name or str(no) in seen:
                    continue
                seen.add(str(no)); out.append((str(no), str(name).strip())); got += 1
        if not got:
            break
        time.sleep(0.15)
    return out


# 업종·테마 안 종목 주소 후보 — 처음 맞는 것을 기억해 계속 쓴다
DETAIL = [
    "https://m.stock.naver.com/api/stocks/%(k)s/%(no)s?page=%(p)d&pageSize=100",
    "https://m.stock.naver.com/api/stocks/%(k)s/%(no)s/total?page=%(p)d&pageSize=100",
    "https://m.stock.naver.com/api/stocks/%(k)s/%(no)s/stocks?page=%(p)d&pageSize=100",
    "https://m.stock.naver.com/api/stocks/%(k)s/detail/%(no)s?page=%(p)d&pageSize=100",
    "https://m.stock.naver.com/api/stocks/%(k)s/stocks/%(no)s?page=%(p)d&pageSize=100",
    "https://m.stock.naver.com/front-api/stocks/%(k)s/%(no)s?page=%(p)d&pageSize=100",
]
_detail_ok = [None]


def m_detail(kind, no, page):
    tries = [_detail_ok[0]] if _detail_ok[0] else DETAIL
    last = None
    for pat in tries:
        try:
            j = json.loads(get(pat % {"k": MKIND[kind], "no": no, "p": page}, "utf-8", tries=1))
            if any(_pick(x, "itemCode", "code", "stockCode") for lst in _lists(j) for x in lst):
                _detail_ok[0] = pat
                return j
        except Exception as e:                # noqa: BLE001
            last = e
    if page > 1:
        return {}
    raise RuntimeError("종목 주소를 못 찾음 (%s)" % last)


def m_group_members(kind, no):
    codes = []
    for page in range(1, 10):
        j = m_detail(kind, no, page)
        got = 0
        for lst in _lists(j):
            for s in lst:
                c = _pick(s, "itemCode", "code", "stockCode")
                # 종목코드는 6자리 — 2024년부터 새로 상장한 곳은 영문이 섞인다 (예: 0088M0)
                if c and re.fullmatch(r"[0-9A-Z]{6}", str(c)) and c not in codes:
                    codes.append(c); got += 1
        if not got:                            # 새 종목이 더 안 나오면 끝 (100개 넘는 업종은 2쪽 이상)
            break
        time.sleep(0.12)
    return codes


def groups(kind, keep, caps):
    out = []
    lst, members = None, group_members
    try:
        lst = m_group_list(kind)
        if lst:
            members = m_group_members
            log("  목록 %d개 (모바일)" % len(lst))
    except Exception as e:                    # noqa: BLE001
        log("  모바일 목록 실패: %s — 예전 표로 받습니다" % e)
    if not lst:
        lst = group_list(kind)
    for no, name in lst:
        try:
            codes = [c for c in members(kind, no) if c in keep]
        except Exception as e:                # noqa: BLE001
            log("    ! %s %s: %s" % (name, no, e))
            continue
        codes.sort(key=lambda c: -caps[c]["c"])
        if codes:
            out.append({"no": no, "name": nice_name(kind, name), "short": short_name(nice_name(kind, name)),
                        "n": len(codes),
                        "sum": round(sum(caps[c]["c"] for c in codes)), "codes": codes[:TOP_GROUP]})
        time.sleep(0.12)
    out.sort(key=lambda g: -g["sum"])
    return out


# ------------------------------------------------------------ 실행

def probe():
    lines = []
    for label, url in (("시가총액 코스피 1쪽", BASE + "/sise/sise_market_sum.naver?sosok=0&page=1"),
                       ("업종 목록", BASE + "/sise/sise_group.naver?type=upjong"),
                       ("테마 목록 1쪽", BASE + "/sise/theme.naver?&page=1")):
        try:
            t = get(url)
            k = max(0, t.find("<th") - 200)
            lines.append("== %s (%d자)\n%s\n...\n%s" % (label, len(t), t[:1500], t[k:k + 6000]))
        except Exception as e:                # noqa: BLE001
            lines.append("== %s 실패: %s" % (label, e))
    try:
        j = json.loads(get("https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=100", "utf-8"))
        st = j.get("stocks", [])
        log("시가총액(모바일): 1쪽 %d종목, 1위 %s %s억" % (len(st), st[0].get("stockName") if st else "-",
                                                      st[0].get("marketValue") if st else "-"))
    except Exception as e:                    # noqa: BLE001
        log("!! 시가총액(모바일) 실패: %s" % e)
    try:
        rows, last = market_page(0, 1)
        log("시가총액 표: 1쪽 %d종목, 마지막 쪽 %d, 1위 %s" % (len(rows), last, rows[0] if rows else "-"))
    except Exception as e:                    # noqa: BLE001
        log("!! 시가총액 표 실패: %s" % e)
    for kind in ("upjong", "theme"):
        try:
            raw = get("https://m.stock.naver.com/api/stocks/%s?page=1&pageSize=100" % MKIND[kind], "utf-8")
            lines.append("== 모바일 %s 목록\n%s" % (kind, raw[:3000]))
            gl = m_group_list(kind)
            log("%s(모바일) %d개, 예: %s" % ("업종" if kind == "upjong" else "테마", len(gl), gl[:3]))
            if gl:
                for pat in DETAIL:
                    u = pat % {"k": MKIND[kind], "no": gl[0][0], "p": 1}
                    try:
                        raw2 = get(u, "utf-8", tries=1)
                        lines.append("== 상세 OK %s\n%s" % (u, raw2[:2500]))
                        log("  상세 OK  %s" % u)
                    except Exception as e:    # noqa: BLE001
                        log("  상세 %s  %s" % (getattr(e, "code", e), u))
                mem = m_group_members(kind, gl[0][0])
                log("  '%s' 종목 %d개, 예: %s" % (gl[0][1], len(mem), mem[:5]))
        except Exception as e:                # noqa: BLE001
            log("!! %s(모바일) 실패: %s" % (kind, e))
            lines.append("== 모바일 %s 실패: %s" % (kind, e))
    try:
        up = group_list("upjong")
        log("업종 %d개, 예: %s" % (len(up), up[:3]))
        if up:
            mem = group_members("upjong", up[0][0])
            log("  '%s' 종목 %d개, 예: %s" % (up[0][1], len(mem), mem[:5]))
            lines.append("== 업종 상세\n" + get(BASE + "/sise/sise_group_detail.naver?type=upjong&no=%s" % up[0][0])[:3000])
        t1 = get(BASE + "/sise/theme.naver?&page=1")
        th = re.findall(r'sise_group_detail\.naver\?type=theme&(?:amp;)?no=(\d+)"[^>]*>(.*?)</a>', t1, re.S)
        log("테마 1쪽 %d개, 예: %s" % (len(th), [(a, clean(b)) for a, b in th[:3]]))
    except Exception as e:                    # noqa: BLE001
        log("!! 확인 실패: %s" % e)
    open("mcap_probe.txt", "w", encoding="utf-8").write("\n\n".join(lines))
    log("mcap_probe.txt 저장 · 호출 %d회" % CALLS[0])


def main():
    if "--probe" in sys.argv:
        return probe()
    if "--rename" in sys.argv:                 # 받아둔 파일의 업종 이름만 띄어 쓴 이름으로 (호출 0회)
        j = json.load(open(OUT, encoding="utf-8"))
        n = 0
        for g in (j.get("groups") or {}).get("industry", []):
            new = nice_name("industry", g["name"])
            n += new != g["name"] or g.get("short") != short_name(new)
            g["name"] = new
            g["short"] = short_name(new)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
        return log("업종 이름 %d개를 고쳤습니다 (짧은 이름 %d개 · 호출 0회)"
                   % (n, sum(1 for g in (j.get("groups") or {}).get("industry", []) if g.get("short"))))
    if "--show" in sys.argv:
        j = json.load(open(OUT, encoding="utf-8"))
        log("%s 종가 기준 (받은 날 %s)" % (j.get("asof"), j.get("updated")))
        for k, _ in MARKETS:
            log("\n[%s] 상위 10" % k)
            for i, r in enumerate(j.get(k, [])[:10], 1):
                log("  %2d %-14s %8s억" % (i, r["name"], format(round(r["cap"]), ",")))
        for kind, label in (("industry", "업종"), ("theme", "테마")):
            gs = (j.get("groups") or {}).get(kind, [])
            log("\n%s %d개 · 시총 큰 순 앞 8개" % (label, len(gs)))
            for g in gs[:8]:
                log("  %-18s %3d종목  %8s억  1위 %s" % (g["name"][:18], g["n"], format(g["sum"], ","),
                                                     j["stocks"][g["codes"][0]]["n"]))
        return

    try:
        listed = {c["code"] for c in json.load(open("data/index.json", encoding="utf-8")).get("companies", [])}
    except Exception:                         # noqa: BLE001
        listed = set()
        log("! data/index.json 이 없어 ETF·우선주를 이름으로만 거릅니다")
    try:
        ret = json.load(open("data/returns.json", encoding="utf-8")).get("items", {})
    except Exception:                         # noqa: BLE001
        ret = {}
    year = str(datetime.now(KST).year)
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:                         # noqa: BLE001
        old = {}

    log("1) 시가총액")
    try:
        caps = all_caps()
    except Exception as e:                    # noqa: BLE001
        log("!! 시가총액을 받지 못했습니다 (%s). 파일을 바꾸지 않습니다." % e)
        sys.exit(1)
    bad = re.compile(r"(우|우B|\d우[BC]?|스팩\d*호?)$|^(KODEX|TIGER|ACE|SOL|RISE|HANARO|PLUS|KIWOOM|KBSTAR|ARIRANG)")
    # 국내 실적 목록(data/index.json)만 쓰면 은행·보험·증권처럼 DART 재무 API 에 숫자가 없어
    # 실적 수집에 실패한 회사(data/_failed.json)까지 빠진다 — KB금융·신한지주 등. 그래서 둘 다 넣는다.
    # ETF·ETN 은 두 목록 어디에도 없어 자연히 빠지고, 우선주·스팩은 이름으로 한 번 더 거른다.
    try:
        tried = set(json.load(open("data/_failed.json", encoding="utf-8")))
    except Exception:                         # noqa: BLE001
        tried = set()
    base = listed | tried
    keep = {c for c, v in caps.items() if (c in base if base else True) and not bad.search(v["n"])}
    for c in keep:
        yv = (ret.get(c, {}).get("years") or {}).get(year)
        caps[c]["y"] = round(float(yv), 1) if yv is not None else None

    out = {"updated": datetime.now(KST).strftime("%Y-%m-%d"), "asof": last_close(),
           "unit": "억원", "source": "네이버 금융"}
    for key, _ in MARKETS:
        top = sorted((c for c in keep if caps[c]["m"] == key), key=lambda c: -caps[c]["c"])[:TOP_MARKET]
        out[key] = [{"code": c, "name": caps[c]["n"], "cap": caps[c]["c"], "ytd": caps[c].get("y")} for c in top]

    out["groups"] = {}
    for kind, key, label in (("upjong", "industry", "업종"), ("theme", "theme", "테마")):
        log("%s) %s" % ("2" if kind == "upjong" else "3", label))
        try:
            gs = groups(kind, keep, caps)
            if not gs:
                raise RuntimeError("하나도 못 읽음")
            out["groups"][key] = gs
            log("  %s %d개" % (label, len(gs)))
        except Exception as e:                # noqa: BLE001
            out["groups"][key] = (old.get("groups") or {}).get(key, [])
            log("  ! %s 실패 (%s) — 전날 것을 그대로 둡니다 (%d개)" % (label, e, len(out["groups"][key])))

    used = set(r["code"] for k, _ in MARKETS for r in out[k])
    for gs in out["groups"].values():
        for g in gs:
            used.update(g["codes"])
    out["stocks"] = {c: {"n": caps[c]["n"], "c": caps[c]["c"], "y": caps[c].get("y"), "m": caps[c]["m"]}
                     for c in sorted(used) if c in caps}

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log("저장: %s (%.0fKB) · 호출 %d회" % (OUT, os.path.getsize(OUT) / 1024, CALLS[0]))


if __name__ == "__main__":
    main()
