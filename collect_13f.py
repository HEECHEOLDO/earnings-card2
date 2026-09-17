#!/usr/bin/env python3
"""
유명 투자자·기관의 미국 주식 보유 현황(13F) -> data/13f.json

SEC EDGAR 에서 최신 13F-HR 을 받아 종목별 비중을 계산한다.
13F 는 분기마다 내는 공시라 보통 한 분기 늦다 (9월 말 보유분이 11월 중순 공개).

사용법:
    python3 collect_13f.py              # 전체
    python3 collect_13f.py berkshire    # 하나만
    python3 collect_13f.py --verify     # CIK 가 맞는지 SEC 등록명 확인
    python3 collect_13f.py --find 하버드 # 이름으로 CIK 찾기 (영문으로)

표준 라이브러리만 사용한다.
"""

import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

UA = "fincard personal project heecheoldo@gmail.com"
OUT = "data/13f.json"
TOP_N = 40                 # 종목이 수천 개인 기관도 있어 상위만 저장
SLEEP = 0.15

# (키, 카드 제목, 공시 주체, CIK)
# CIK 는 --verify 로 SEC 등록명이 맞는지 꼭 확인할 것
FUNDS = [
    ("berkshire",  "워런 버핏",        "Berkshire Hathaway",                  1067983),
    ("ark",        "캐시 우드",        "ARK Investment Management",           1697748),
    ("gates",      "빌 게이츠",        "Gates Foundation Trust",              1166559),
    ("harvard",    "하버드 대학",      "Harvard Management Co",               1082621),
    ("scion",      "마이클 버리",      "Scion Asset Management",              1649339),
    ("duquesne",   "드러켄밀러",       "Duquesne Family Office",              1536411),
    ("pershing",   "빌 애크먼",        "Pershing Square Capital",             1336528),
    ("bridgewater","레이 달리오",      "Bridgewater Associates",              1350694),
    ("rentech",    "르네상스 테크",    "Renaissance Technologies",            1037389),
    ("soros",      "조지 소로스",      "Soros Fund Management",               1029160),
    ("appaloosa",  "데이비드 테퍼",    "Appaloosa LP",                        1656456),
    ("baupost",    "세스 클라만",      "Baupost Group",                       1061768),
    ("thirdpoint", "댄 로브",          "Third Point",                         1040273),
    ("greenlight", "데이비드 아인혼",  "Greenlight Capital",                  1079114),
    ("tiger",      "타이거 글로벌",    "Tiger Global Management",             1167483),
    ("citadel",    "켄 그리핀",        "Citadel Advisors",                    1423053),
    ("himalaya",   "리루",             "Himalaya Capital Management",         1709323),
    ("icahn",      "칼 아이칸",        "Icahn Carl C",                        921669),
    ("lonepine",   "론파인",           "Lone Pine Capital",                   1061165),
    ("coatue",     "코튜",             "Coatue Management",                   1135730),
    ("norges",     "노르웨이 국부펀드", "Norges Bank",                        1374170),
    ("nps",        "국민연금",         "National Pension Service",            1608046),
]

# 카드에 한글로 보이게 — 없는 회사는 영문 이름을 정리해서 쓴다
KO = {
    "APPLE": "애플", "MICROSOFT": "마이크로소프트", "AMAZON": "아마존", "ALPHABET": "알파벳",
    "NVIDIA": "엔비디아", "META PLATFORMS": "메타", "TESLA": "테슬라", "BERKSHIRE HATHAWAY": "버크셔",
    "COCA COLA": "코카콜라", "AMERICAN EXPRESS": "아메리칸 익스프레스", "BANK OF AMERICA": "뱅크오브아메리카",
    "CHEVRON": "셰브론", "BANK AMER": "뱅크오브아메리카", "AMERICAN EXPRESS": "아메리칸 익스프레스",
    "NU HLDGS": "누뱅크", "NU HOLDINGS": "누뱅크", "ALLY FINL": "앨리 파이낸셜", "AON": "에이온",
    "LENNAR": "레나", "DR HORTON": "DR호튼", "HEICO": "헤이코", "LOUISIANA PAC": "루이지애나퍼시픽", "OCCIDENTAL PETROLEUM": "옥시덴탈", "KRAFT HEINZ": "크래프트하인즈",
    "MOODYS": "무디스", "CHUBB": "처브", "VISA": "비자", "MASTERCARD": "마스터카드",
    "DAVITA": "다비타", "KROGER": "크로거", "CITIGROUP": "씨티그룹", "CAPITAL ONE": "캐피털원",
    "VERISIGN": "베리사인", "ALLY FINANCIAL": "앨리 파이낸셜", "SIRIUS XM": "시리우스XM",
    "DOMINOS PIZZA": "도미노피자", "POOL": "풀", "CONSTELLATION BRANDS": "컨스텔레이션",
    "UNITEDHEALTH": "유나이티드헬스", "JOHNSON & JOHNSON": "존슨앤드존슨", "PFIZER": "화이자",
    "ELI LILLY": "일라이릴리", "MERCK": "머크", "ABBVIE": "애브비", "BROADCOM": "브로드컴",
    "ADVANCED MICRO DEVICES": "AMD", "INTEL": "인텔", "QUALCOMM": "퀄컴", "TAIWAN SEMICONDUCTOR": "TSMC",
    "NETFLIX": "넷플릭스", "WALT DISNEY": "디즈니", "ORACLE": "오라클", "SALESFORCE": "세일즈포스",
    "ADOBE": "어도비", "PALANTIR": "팔란티어", "COINBASE": "코인베이스", "ROBINHOOD": "로빈후드",
    "ROBLOX": "로블록스", "ROKU": "로쿠", "SHOPIFY": "쇼피파이", "UBER": "우버", "AIRBNB": "에어비앤비",
    "BLOCK": "블록", "PAYPAL": "페이팔", "ZOOM": "줌", "CRISPR THERAPEUTICS": "크리스퍼",
    "WASTE MANAGEMENT": "웨이스트 매니지먼트", "CATERPILLAR": "캐터필러", "DEERE": "디어",
    "CANADIAN NATIONAL RAILWAY": "캐나다 내셔널 철도", "ECOLAB": "에코랩", "FEDEX": "페덱스",
    "WALMART": "월마트", "COSTCO": "코스트코", "HOME DEPOT": "홈디포", "MCDONALDS": "맥도날드",
    "STARBUCKS": "스타벅스", "NIKE": "나이키", "PROCTER & GAMBLE": "P&G", "PEPSICO": "펩시코",
    "EXXON MOBIL": "엑슨모빌", "JPMORGAN CHASE": "JP모건", "GOLDMAN SACHS": "골드만삭스",
    "MORGAN STANLEY": "모건스탠리", "WELLS FARGO": "웰스파고", "BLACKROCK": "블랙록",
    "ALIBABA": "알리바바", "PINDUODUO": "핀둬둬", "PDD": "핀둬둬", "JD COM": "징둥",
    "BAIDU": "바이두", "SPDR S&P 500": "S&P500 ETF", "SPDR GOLD": "금 ETF",
    "ISHARES CORE S&P 500": "S&P500 ETF", "VANGUARD S&P 500": "S&P500 ETF",
    "INVESCO QQQ": "나스닥100 ETF", "BOEING": "보잉", "GENERAL ELECTRIC": "GE",
    "LOCKHEED MARTIN": "록히드마틴", "RAYTHEON": "레이시온", "HONEYWELL": "허니웰",
    "3M": "3M", "AT&T": "AT&T", "VERIZON": "버라이즌", "T MOBILE": "T모바일",
    "COMCAST": "컴캐스트", "CHARTER COMMUNICATIONS": "차터", "LIBERTY MEDIA": "리버티 미디어",
    "FORMULA ONE": "포뮬러원", "ATLANTA BRAVES": "애틀랜타 브레이브스",
}

_calls = 0


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url, is_json=True, tries=3):
    global _calls
    last = ""
    for i in range(tries):
        try:
            _calls += 1
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Encoding": "gzip",
                "Accept": "application/json" if is_json else "*/*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            time.sleep(SLEEP)
            txt = raw.decode("utf-8", "ignore")
            return (json.loads(txt) if is_json else txt), ""
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code == 404:
                return None, last
            time.sleep(1.5 + i)
        except Exception as e:                # noqa: BLE001
            last = type(e).__name__
            time.sleep(1.5 + i)
    return None, last


def clean_name(raw):
    """SEC 발행사 이름을 카드에 쓸 만하게 다듬는다."""
    s = raw.upper().replace(".", "").replace(",", "")
    s = re.sub(r"\s+", " ", s).strip()
    for k in KO:
        if s.startswith(k):
            return KO[k]
    # 회사 형태·주식 종류 꼬리표 제거
    s = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|HOLDINGS?|GROUP|"
               r"TRUST|LP|LLC|SA|NV|AG|ADR|ADS|COM|NEW|DEL|CL [ABC]|CLASS [ABC]|"
               r"SHS|SHARES|ORD|ORDINARY|DEP RECPT|SPONSORED|COMMON|STOCK|"
               r"THE|OF|&)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 첫 글자만 대문자
    return " ".join(w if len(w) <= 3 else w.capitalize() for w in s.split())[:22] or raw[:22]


def local(tag):
    return tag.split("}")[-1].lower()


def parse_infotable(xml_text):
    """13F 정보표 XML -> [(이름, cusip, 금액, 주식수)] (옵션 제외)"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if local(root.tag) != "informationtable":
        # 안에 informationTable 이 들어있는 경우
        found = None
        for el in root.iter():
            if local(el.tag) == "informationtable":
                found = el
                break
        if found is None:
            return None
        root = found
    rows = []
    for it in root:
        if local(it.tag) != "infotable":
            continue
        d = {}
        for el in it.iter():
            d[local(el.tag)] = (el.text or "").strip()
        if d.get("putcall"):
            continue                          # 옵션은 뺀다
        try:
            value = float(d.get("value") or 0)
            shares = float(d.get("sshprnamt") or 0)
        except ValueError:
            continue
        if value <= 0:
            continue
        rows.append((d.get("nameofissuer", ""), d.get("cusip", "")[:6], value, shares))
    return rows


def latest_13f(cik):
    """가장 최근 13F-HR 의 (접수번호, 보고기간, 접수일) 을 찾는다."""
    j, why = get("https://data.sec.gov/submissions/CIK%010d.json" % cik)
    if not j:
        return None, None, why
    name = j.get("name", "")
    rec = j.get("filings", {}).get("recent", {})
    forms = rec.get("form", [])
    for i, f in enumerate(forms):
        if f == "13F-HR":
            return {
                "acc": rec["accessionNumber"][i].replace("-", ""),
                "period": rec["reportDate"][i],
                "filed": rec["filingDate"][i],
            }, name, None
    return None, name, "13F-HR 없음"


def fetch_holdings(cik, acc):
    """접수번호로 정보표를 찾아 파싱한다."""
    base = "https://www.sec.gov/Archives/edgar/data/%d/%s/" % (cik, acc)
    idx, why = get(base + "index.json")
    if not idx:
        return None, "목록 " + why
    files = [f["name"] for f in idx.get("directory", {}).get("item", [])
             if f["name"].lower().endswith(".xml")]
    # 정보표는 보통 'infotable' 이름이지만 회사마다 달라 전부 열어본다
    files.sort(key=lambda n: (0 if "info" in n.lower() else 1, n))
    for fn in files:
        txt, _ = get(base + fn, is_json=False)
        if not txt:
            continue
        rows = parse_infotable(txt)
        if rows:
            return rows, None
    return None, "정보표를 못 찾음"


def build(rows):
    """종목별로 합쳐 비중을 낸다."""
    by = {}
    for name, cusip6, value, shares in rows:
        key = cusip6 or name
        b = by.setdefault(key, {"raw": name, "value": 0.0, "shares": 0.0})
        b["value"] += value
        b["shares"] += shares
        if len(name) > len(b["raw"]):
            b["raw"] = name
    total = sum(b["value"] for b in by.values()) or 1.0
    items = sorted(by.values(), key=lambda b: -b["value"])
    out = []
    for b in items[:TOP_N]:
        out.append({
            "name": clean_name(b["raw"]),
            "raw": b["raw"],
            "weight": round(b["value"] / total * 100, 2),
            "value": round(b["value"]),
        })
    return out, len(by), total


def verify():
    log("CIK 확인 — SEC 등록명이 기대와 다르면 번호가 틀린 것")
    log("-" * 66)
    for key, title, expect, cik in FUNDS:
        j, why = get("https://data.sec.gov/submissions/CIK%010d.json" % cik)
        name = (j or {}).get("name", "") if j else ("실패: " + why)
        ok = expect.split()[0].lower() in name.lower()
        log("%-12s %-8d %s  %s" % (key, cik, "OK " if ok else "?? ", name))


def find(q):
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=%s"
           "&type=13F-HR&output=atom" % urllib.parse.quote(q))
    txt, why = get(url, is_json=False)
    if not txt:
        return log("검색 실패: " + why)
    # 회사명은 <conformed-name>, 번호는 <cik> 에 들어 있다
    names = re.findall(r"<conformed-name>(.*?)</conformed-name>", txt, re.S)
    ciks = re.findall(r"<cik>(\d+)</cik>", txt, re.S)
    if not ciks:
        # 회사가 하나뿐이면 다른 형식이라 CIK 만 뽑는다
        ciks = list(dict.fromkeys(re.findall(r"CIK=(\d+)", txt)))
        names = [""] * len(ciks)
    if not ciks:
        return log("결과 없음. 영문 이름으로 찾아보세요 (예: harvard)")
    for cik, name in list(zip(ciks, names))[:15]:
        log("  %-10s %s" % (int(cik), name.strip()))


def main():
    argv = sys.argv[1:]
    if "--verify" in argv:
        return verify()
    if "--find" in argv:
        i = argv.index("--find")
        return find(argv[i + 1] if i + 1 < len(argv) else "")

    only = [a for a in argv if not a.startswith("--")]
    funds = [f for f in FUNDS if not only or f[0] in only]

    prev = {}
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f).get("funds", {})
    except Exception:                         # noqa: BLE001
        pass

    result, fails = dict(prev), []
    for key, title, expect, cik in funds:
        meta, sec_name, why = latest_13f(cik)
        if not meta:
            fails.append((key, why)); continue
        if prev.get(key, {}).get("acc") == meta["acc"]:
            log("  %-12s 변화 없음 (%s 보유분)" % (key, meta["period"]))
            continue
        rows, why = fetch_holdings(cik, meta["acc"])
        if not rows:
            fails.append((key, why)); continue
        holdings, n_all, total = build(rows)
        result[key] = {
            "title": title, "entity": sec_name or expect, "cik": cik,
            "period": meta["period"], "filed": meta["filed"], "acc": meta["acc"],
            "count": n_all, "total_value": round(total),
            "holdings": holdings,
        }
        log("  %-12s %s 보유분 · %d종목 · 1위 %s %.1f%%"
            % (key, meta["period"], n_all, holdings[0]["name"], holdings[0]["weight"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
            "source": "SEC 13F-HR",
            "funds": result,
        }, f, ensure_ascii=False, separators=(",", ":"))
    log("\n저장 %d개 · 호출 %d회" % (len(result), _calls))
    for key, why in fails:
        log("  실패 %-12s %s" % (key, why))


if __name__ == "__main__":
    main()
