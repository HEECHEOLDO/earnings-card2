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
    # 빅테크
    "APPLE": "애플", "MICROSOFT": "마이크로소프트", "AMAZON": "아마존", "ALPHABET": "알파벳",
    "NVIDIA": "엔비디아", "META PLATFORMS": "메타", "TESLA": "테슬라", "NETFLIX": "넷플릭스",
    "ORACLE": "오라클", "SALESFORCE": "세일즈포스", "ADOBE": "어도비", "BROADCOM": "브로드컴",
    "ADVANCED MICRO DEVICES": "AMD", "INTEL": "인텔", "QUALCOMM": "퀄컴", "MICRON": "마이크론",
    "TAIWAN SEMICONDUCTOR": "TSMC", "ARM HOLDINGS": "ARM", "ASML": "ASML", "APPLIED MATERIALS": "AMAT",
    "LAM RESEARCH": "램리서치", "KLA": "KLA", "TEXAS INSTRUMENTS": "TI", "ANALOG DEVICES": "ADI",
    "PALANTIR": "팔란티어", "SERVICENOW": "서비스나우", "SNOWFLAKE": "스노우플레이크", "DATADOG": "데이터독",
    "CROWDSTRIKE": "크라우드스트라이크", "PALO ALTO": "팔로알토", "FORTINET": "포티넷", "WORKDAY": "워크데이",
    "INTUIT": "인튜이트", "AUTODESK": "오토데스크", "SYNOPSYS": "시놉시스", "CADENCE": "케이던스",
    "SHOPIFY": "쇼피파이", "UBER": "우버", "AIRBNB": "에어비앤비", "DOORDASH": "도어대시",
    "BLOCK": "블록", "PAYPAL": "페이팔", "COINBASE": "코인베이스", "ROBINHOOD": "로빈후드",
    "ROBLOX": "로블록스", "ROKU": "로쿠", "ZOOM": "줌", "SPOTIFY": "스포티파이", "PINTEREST": "핀터레스트",
    "SNAP": "스냅", "REDDIT": "레딧", "DUOLINGO": "듀오링고", "UNITY": "유니티", "TWILIO": "트윌리오",
    "MONGODB": "몽고DB", "CLOUDFLARE": "클라우드플레어", "OKTA": "옥타", "ZSCALER": "지스케일러",
    "DELL": "델", "HEWLETT PACKARD": "HPE", "HP INC": "HP", "IBM": "IBM", "INTERNATIONAL BUSINESS": "IBM",
    "CISCO": "시스코", "ARISTA": "아리스타", "SUPER MICRO": "슈퍼마이크로", "VERTIV": "버티브",
    # 금융
    "BERKSHIRE HATHAWAY": "버크셔", "JPMORGAN": "JP모건", "BANK AMER": "뱅크오브아메리카",
    "BANK OF AMERICA": "뱅크오브아메리카", "WELLS FARGO": "웰스파고", "CITIGROUP": "씨티",
    "GOLDMAN SACHS": "골드만삭스", "MORGAN STANLEY": "모건스탠리", "AMERICAN EXPRESS": "아멕스",
    "VISA": "비자", "MASTERCARD": "마스터카드", "CAPITAL ONE": "캐피털원", "BLACKROCK": "블랙록",
    "BLACKSTONE": "블랙스톤", "KKR": "KKR", "APOLLO": "아폴로", "SCHWAB": "슈왑", "CHARLES SCHWAB": "슈왑",
    "S&P GLOBAL": "S&P글로벌", "MOODYS": "무디스", "MSCI": "MSCI", "CME": "CME", "ICE": "ICE",
    "INTERCONTINENTAL EXCH": "ICE", "CHUBB": "처브", "PROGRESSIVE": "프로그레시브", "AON": "에이온",
    "MARSH": "마시", "ALLY FINL": "앨리", "ALLY FINANCIAL": "앨리", "NU HLDGS": "누뱅크", "NU HOLDINGS": "누뱅크",
    "AMERICAN INTL": "AIG", "METLIFE": "메트라이프", "PRUDENTIAL": "푸르덴셜", "US BANCORP": "US뱅코프",
    "PNC": "PNC", "TRUIST": "트루이스트", "FISERV": "파이서브", "SOFI": "소파이",
    # 소비
    "COCA COLA": "코카콜라", "PEPSICO": "펩시코", "PROCTER & GAMBLE": "P&G", "PROCTER GAMBLE": "P&G",
    "WALMART": "월마트", "COSTCO": "코스트코", "TARGET": "타겟", "HOME DEPOT": "홈디포", "LOWES": "로우스",
    "MCDONALDS": "맥도날드", "STARBUCKS": "스타벅스", "CHIPOTLE": "치폴레", "DOMINOS": "도미노",
    "NIKE": "나이키", "LULULEMON": "룰루레몬", "KRAFT HEINZ": "크래프트하인즈", "MONDELEZ": "몬델리즈",
    "CONSTELLATION BRANDS": "컨스텔레이션", "PHILIP MORRIS": "필립모리스", "ALTRIA": "알트리아",
    "COLGATE": "콜게이트", "KIMBERLY": "킴벌리", "ESTEE LAUDER": "에스티로더", "KROGER": "크로거",
    "DOLLAR GENERAL": "달러제너럴", "DOLLAR TREE": "달러트리", "TJX": "TJX", "ROSS STORES": "로스",
    "BOOKING": "부킹", "MARRIOTT": "메리어트", "HILTON": "힐튼", "LAS VEGAS SANDS": "샌즈",
    "WALT DISNEY": "디즈니", "DISNEY": "디즈니", "WARNER BROS": "워너브라더스", "COMCAST": "컴캐스트",
    "CHARTER": "차터", "LIVE NATION": "라이브네이션", "SIRIUS XM": "시리우스XM", "LIBERTY MEDIA": "리버티",
    "LIBERTY BROADBAND": "리버티", "FORMULA ONE": "포뮬러원", "ATLANTA BRAVES": "브레이브스",
    "TAKE TWO": "테이크투", "ELECTRONIC ARTS": "EA", "FORD": "포드", "GENERAL MOTORS": "GM",
    "RIVIAN": "리비안", "LUCID": "루시드", "CARVANA": "카바나", "AUTOZONE": "오토존", "OREILLY": "오라일리",
    # 헬스케어
    "UNITEDHEALTH": "유나이티드헬스", "JOHNSON & JOHNSON": "J&J", "JOHNSON JOHNSON": "J&J",
    "PFIZER": "화이자", "ELI LILLY": "일라이릴리", "LILLY ELI": "일라이릴리", "MERCK": "머크",
    "ABBVIE": "애브비", "AMGEN": "암젠", "GILEAD": "길리어드", "BRISTOL MYERS": "BMS", "MODERNA": "모더나",
    "REGENERON": "리제네론", "VERTEX": "버텍스", "THERMO FISHER": "써모피셔", "DANAHER": "다나허",
    "ABBOTT": "애보트", "MEDTRONIC": "메드트로닉", "INTUITIVE SURGICAL": "인튜이티브", "STRYKER": "스트라이커",
    "BOSTON SCIENTIFIC": "보스턴사이언티픽", "CVS": "CVS", "CIGNA": "시그나", "HUMANA": "휴매나",
    "ELEVANCE": "엘리번스", "HCA": "HCA", "DAVITA": "다비타", "ZOETIS": "조에티스",
    "CRISPR": "크리스퍼", "NOVO NORDISK": "노보노디스크", "ASTRAZENECA": "아스트라제네카",
    # 산업·에너지·소재
    "EXXON MOBIL": "엑슨모빌", "CHEVRON": "셰브론", "OCCIDENTAL": "옥시덴탈", "CONOCOPHILLIPS": "코노코",
    "SCHLUMBERGER": "슐룸베르거", "HALLIBURTON": "할리버튼", "EOG": "EOG", "DEVON": "데번",
    "BOEING": "보잉", "LOCKHEED": "록히드마틴", "RTX": "RTX", "RAYTHEON": "RTX", "NORTHROP": "노스롭",
    "GENERAL DYNAMICS": "제너럴다이내믹스", "GENERAL ELECTRIC": "GE", "GE AEROSPACE": "GE",
    "HONEYWELL": "허니웰", "CATERPILLAR": "캐터필러", "DEERE": "디어", "3M": "3M", "UNION PACIFIC": "유니언퍼시픽",
    "CSX": "CSX", "NORFOLK": "노퍽서던", "CANADIAN NATL": "CN철도", "CANADIAN NATIONAL": "CN철도",
    "CANADIAN PACIFIC": "CP철도", "FEDEX": "페덱스", "UNITED PARCEL": "UPS", "UPS": "UPS",
    "DELTA AIR": "델타항공", "UNITED AIRLINES": "유나이티드항공", "SOUTHWEST": "사우스웨스트",
    "WASTE MANAGEMENT": "WM", "REPUBLIC SERVICES": "리퍼블릭", "ECOLAB": "에코랩", "SHERWIN": "셔윈",
    "LINDE": "린데", "AIR PRODUCTS": "에어프로덕츠", "FREEPORT": "프리포트", "NEWMONT": "뉴몬트",
    "NUCOR": "뉴코어", "DOW": "다우", "DUPONT": "듀폰", "CRH": "CRH", "VULCAN": "벌컨", "MARTIN MARIETTA": "마틴마리에타",
    "LENNAR": "레나", "DR HORTON": "DR호튼", "NVR": "NVR", "PULTE": "풀티", "HEICO": "헤이코",
    "LOUISIANA PAC": "LP", "POOL": "풀", "TRANSDIGM": "트랜스다임", "PARKER HANNIFIN": "파커",
    "EATON": "이튼", "EMERSON": "에머슨", "ILLINOIS TOOL": "ITW", "CINTAS": "신타스", "FASTENAL": "패스널",
    # 통신·유틸리티·부동산
    "AT&T": "AT&T", "VERIZON": "버라이즌", "T MOBILE": "T모바일", "TELEPHONE & DATA": "TDS", "TELEPHONE DATA": "TDS",
    "NEXTERA": "넥스트에라", "DUKE ENERGY": "듀크", "SOUTHERN CO": "서던", "DOMINION": "도미니언",
    "CONSTELLATION ENERGY": "컨스텔레이션E", "VISTRA": "비스트라", "AMERICAN TOWER": "아메리칸타워",
    "PROLOGIS": "프로로지스", "EQUINIX": "에퀴닉스", "CROWN CASTLE": "크라운캐슬", "REALTY INCOME": "리얼티인컴",
    "SIMON PROPERTY": "사이먼", "PUBLIC STORAGE": "퍼블릭스토리지", "WELLTOWER": "웰타워",
    # 중국·기타 해외
    "ALIBABA": "알리바바", "PINDUODUO": "핀둬둬", "PDD": "핀둬둬", "JD COM": "징둥", "BAIDU": "바이두",
    "TENCENT": "텐센트", "NIO": "니오", "XPENG": "샤오펑", "LI AUTO": "리오토", "BILIBILI": "빌리빌리",
    "SEA LTD": "씨", "MERCADOLIBRE": "메르카도리브레", "GRAB": "그랩", "SPOTIFY": "스포티파이",
    "SHELL": "셸", "BP": "BP", "TOYOTA": "도요타", "SONY": "소니", "MITSUBISHI": "미쓰비시", "MITSUI": "미쓰이",
    "ITOCHU": "이토추", "SUMITOMO": "스미토모", "MARUBENI": "마루베니", "UNILEVER": "유니레버",
    "NESTLE": "네슬레", "NOVARTIS": "노바티스", "ROCHE": "로슈", "SAP": "SAP", "LVMH": "LVMH",
    # ETF
    "SPDR S&P 500": "S&P500 ETF", "ISHARES CORE S&P 500": "S&P500 ETF", "VANGUARD S&P 500": "S&P500 ETF",
    "INVESCO QQQ": "나스닥100 ETF", "SPDR GOLD": "금 ETF", "ISHARES RUSSELL 2000": "러셀2000 ETF",
    "ISHARES MSCI": "MSCI ETF", "VANGUARD TOTAL": "VTI", "ARK INNOVATION": "ARKK",
    "ISHARES 20": "TLT", "ISHARES BITCOIN": "비트코인 ETF", "GRAYSCALE BITCOIN": "비트코인 ETF",
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
    s = " ".join(ABBR.get(w, w) for w in s.split())
    # 회사 형태·주식 종류 꼬리표 제거
    s = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|HOLDINGS?|GROUP|"
               r"TRUST|LP|LLC|SA|NV|AG|ADR|ADS|COM|NEW|DEL|CL [ABC]|CLASS [ABC]|"
               r"SHS|SHARES|ORD|ORDINARY|DEP RECPT|SPONSORED|COMMON|STOCK|"
               r"THE|OF|&)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 첫 글자만 대문자
    return " ".join(w if len(w) <= 3 else w.capitalize() for w in s.split())[:22] or raw[:22]


_tickers = None      # [(정규화된 이름, 티커)]

# 13F 에 흔한 줄임말 — 티커 목록의 정식 이름과 맞추려고 푼다
ABBR = {
    "MGMT": "MANAGEMENT", "FINL": "FINANCIAL", "MFG": "MANUFACTURING", "SVCS": "SERVICES",
    "SVC": "SERVICE", "SYS": "SYSTEMS", "INTL": "INTERNATIONAL", "TECH": "TECHNOLOGY",
    "TECHS": "TECHNOLOGIES", "PHARMA": "PHARMACEUTICALS", "HLTH": "HEALTH", "HLTHCARE": "HEALTHCARE",
    "ENTMT": "ENTERTAINMENT", "PWR": "POWER", "RES": "RESOURCES", "PPTYS": "PROPERTIES",
    "PPTY": "PROPERTY", "INDS": "INDUSTRIES", "IND": "INDUSTRIES", "AMER": "AMERICAN",
    "NATL": "NATIONAL", "GENL": "GENERAL", "ELEC": "ELECTRIC", "MTRS": "MOTORS", "MTR": "MOTOR",
    "PETE": "PETROLEUM", "PETROL": "PETROLEUM", "RLTY": "REALTY", "INVT": "INVESTMENT",
    "INVS": "INVESTORS", "CAP": "CAPITAL", "COMMUNICATIONS": "COMMUNICATIONS", "COMM": "COMMUNICATIONS",
    "ENERGY": "ENERGY", "ENRGY": "ENERGY", "PRODS": "PRODUCTS", "PROD": "PRODUCTS",
    "LABS": "LABORATORIES", "BANCORP": "BANCORP", "BK": "BANK", "TR": "TRUST", "SEMICONDUCTOR": "SEMICONDUCTOR",
    "MEDIA": "MEDIA", "ASSOC": "ASSOCIATES", "GRP": "GROUP", "HLDG": "HOLDING",
    "AIRLS": "AIRLINES", "AIRL": "AIRLINES", "RR": "RAILROAD", "RY": "RAILWAY", "STL": "STEEL",
    "CHEM": "CHEMICAL", "CHEMS": "CHEMICALS", "MED": "MEDICAL", "DEV": "DEVELOPMENT", "EQUIP": "EQUIPMENT",
    "SOLTNS": "SOLUTIONS", "SOLUTNS": "SOLUTIONS", "BRDCSTG": "BROADCASTING", "PLATFRMS": "PLATFORMS",
}

def norm_name(raw):
    t = re.sub(r"[^A-Z0-9& ]", " ", str(raw).upper())
    t = " ".join(ABBR.get(w, w) for w in t.split())
    t = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|HOLDINGS?|HLDGS?|GROUP|"
               r"TRUST|LP|LLC|SA|NV|AG|ADR|ADS|COM|NEW|DEL|CL [ABC]|CLASS [ABC]|SER [ABC]|"
               r"SHS|SHARES|ORD|ORDINARY|SPONSORED|COMMON|STOCK|THE|OF|&|AND)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def load_tickers():
    """SEC 회사·티커 목록 (약 1만 개). 하루 한 번 받아 캐시한다."""
    global _tickers
    if _tickers is not None:
        return _tickers
    cache = "data/sec_tickers.json"
    j = None
    try:
        st = os.stat(cache)
        if time.time() - st.st_mtime < 7 * 86400:
            with open(cache, encoding="utf-8") as f:
                j = json.load(f)
    except Exception:                         # noqa: BLE001
        j = None
    if j is None:
        j, _ = get("https://www.sec.gov/files/company_tickers.json")
        if j:
            os.makedirs("data", exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(j, f)
    _tickers = []
    for v in (j or {}).values():
        try:
            _tickers.append((norm_name(v["title"]), v["ticker"].replace("-", ".")))
        except Exception:                     # noqa: BLE001
            continue
    return _tickers

def find_ticker(raw):
    """13F 발행사 이름으로 티커를 찾는다. 앞부분이 같은 것 중 가장 긴 일치."""
    n = norm_name(raw)
    if len(n) < 4:
        return None
    best, best_len = None, 0
    nw = n.split()
    for name, tk in load_tickers():
        if not name:
            continue
        if name == n:
            return tk
        # 한쪽이 다른 쪽의 앞부분이고, 겹치는 길이가 충분할 때
        if n.startswith(name + " ") or name.startswith(n + " ") or name.startswith(n):
            k = min(len(name), len(n))
            if k >= 6 and k > best_len:
                best, best_len = tk, k
    if best:
        return best
    # 그래도 없으면 앞 두 단어가 정확히 같은 것 (두 단어면 대개 회사가 특정된다)
    if len(nw) >= 2 and len(nw[0]) + len(nw[1]) >= 8:
        head = nw[0] + " " + nw[1]
        cands = [tk for name, tk in load_tickers() if name == head or name.startswith(head + " ")]
        if len(cands) == 1:
            return cands[0]
    return None


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
        name = clean_name(b["raw"])
        ticker = None
        # 한글 이름이 아니고 길면 티커로 바꾼다 (카드에서 글자가 작아진다)
        if not re.search(r"[가-힣]", name) and len(name) > 9:
            ticker = find_ticker(b["raw"])
            if ticker and len(ticker) <= 6:
                name = ticker
        out.append({
            "name": name,
            "raw": b["raw"],
            "ticker": ticker,
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
