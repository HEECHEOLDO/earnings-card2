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
NAME_VER = 3               # 종목명 규칙 판. 올리면 공시가 그대로여도 다시 만든다
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
    "APPLE": "애플", "MICROSOFT": "MS", "AMAZON": "아마존", "ALPHABET": "알파벳",
    "NVIDIA": "엔비디아", "META PLATFORMS": "메타", "TESLA": "테슬라", "NETFLIX": "넷플릭스",
    "ORACLE": "오라클", "SALESFORCE": "세일즈포스", "ADOBE": "어도비", "BROADCOM": "브로드컴",
    "ADVANCED MICRO DEVICES": "AMD", "INTEL": "인텔", "QUALCOMM": "퀄컴", "MICRON": "마이크론",
    "TAIWAN SEMICONDUCTOR": "TSMC", "ARM HOLDINGS": "ARM", "APPLIED MATERIALS": "AMAT",
    "LAM RESEARCH": "램리서치", "KLA": "KLA", "TEXAS INSTRUMENTS": "TI", "ANALOG DEVICES": "ADI",
    "SERVICENOW": "서비스나우", "SNOWFLAKE": "스노우", "DATADOG": "데이터독",
    "CROWDSTRIKE": "크라우드", "PALO ALTO": "팔로알토", "FORTINET": "포티넷", "WORKDAY": "워크데이",
    "INTUIT": "인튜이트", "AUTODESK": "오토데스크", "SYNOPSYS": "시놉시스", "CADENCE": "케이던스",
    "UBER": "우버", "DOORDASH": "도어대시",
     "PAYPAL": "페이팔", 
    "ROBLOX": "로블록스", "ROKU": "로쿠", "ZOOM": "줌비디오",  "PINTEREST": "핀터레스트",
    "SNAP": "스냅", "REDDIT": "레딧", "DUOLINGO": "듀오링고", "UNITY": "유니티", "TWILIO": "트윌리오",
    "MONGODB": "몽고DB", "CLOUDFLARE": "클플레어", "OKTA": "옥타", "ZSCALER": "지스케일러",
    "DELL": "DELL", "HEWLETT PACKARD": "HPE", "HP INC": "HP", "IBM": "IBM", "INTERNATIONAL BUSINESS": "IBM",
    "CISCO": "시스코", "ARISTA": "아리스타", "SUPER MICRO": "슈퍼마이크로", "VERTIV": "버티브",
    # 금융
    "BERKSHIRE HATHAWAY": "버크셔", "JPMORGAN": "JP모건", "BANK AMER": "BoA", "BANK AMERICAN": "BoA", "BANK OF AMER": "BoA",
    "BANK OF AMERICA": "BoA", "WELLS FARGO": "웰스파고", "CITIGROUP": "씨티",
    "GOLDMAN SACHS": "골드만삭스", "MORGAN STANLEY": "모건스탠리", "AMERICAN EXPRESS": "아멕스",
    "VISA": "비자", "MASTERCARD": "마스터카드", "CAPITAL ONE": "캐피털원", "BLACKROCK": "블랙록",
    "BLACKSTONE": "블랙스톤", "KKR": "KKR", "APOLLO": "아폴로", "SCHWAB": "슈왑", "CHARLES SCHWAB": "슈왑",
    "S&P GLOBAL": "S&P글로벌", "MOODYS": "무디스", "MSCI": "MSCI", "CME": "CME", "ICE": "ICE",
    "INTERCONTINENTAL EXCH": "ICE", "CHUBB": "처브", "PROGRESSIVE": "프로그레시브", "AON": "에이온",
    "MARSH": "마시맥레넌", "ALLY FINL": "앨리파이낸셜", "ALLY FINANCIAL": "앨리파이낸셜", "NU HLDGS": "누뱅크", "NU HOLDINGS": "누뱅크",
    "AMERICAN INTL": "AIG", "METLIFE": "메트라이프", "PRUDENTIAL": "푸르덴셜", "US BANCORP": "US뱅코프",
    "PNC": "PNC", "TRUIST": "트루이스트", "FISERV": "파이서브", "SOFI": "소파이",
    # 소비
    "COCA COLA": "코카콜라", "PEPSICO": "펩시코", "PROCTER & GAMBLE": "P&G", "PROCTER GAMBLE": "P&G",
    "WALMART": "월마트", "COSTCO": "코스트코", "TARGET": "타겟", "HOME DEPOT": "홈디포", "LOWES": "로우스",
    "MCDONALDS": "맥도날드", "STARBUCKS": "스타벅스", "CHIPOTLE": "치폴레", "DOMINOS": "도미노",
    "NIKE": "나이키",  "KRAFT HEINZ": "크래프트", "MONDELEZ": "몬델리즈",
    "CONSTELLATION BRANDS": "컨스텔레이션", "ALTRIA": "알트리아",
    "COLGATE": "콜게이트", "KIMBERLY": "킴벌리", "ESTEE LAUDER": "에스티로더", "KROGER": "크로거",
    "DOLLAR GENERAL": "달러제너럴", "DOLLAR TREE": "달러트리", "TJX": "TJX", "ROSS STORES": "로스스토어",
    "MARRIOTT": "메리어트", "HILTON": "힐튼", "LAS VEGAS SANDS": "샌즈",
    "WALT DISNEY": "디즈니", "DISNEY": "디즈니", "WARNER BROS": "워너브라더스", "COMCAST": "컴캐스트",
    "CHARTER": "차터", "LIVE NATION": "라이브네이션", "SIRIUS XM": "시리우스XM", "LIBERTY MEDIA": "리버티미디어",
    "LIBERTY BROADBAND": "리버티BB", "FORMULA ONE": "포뮬러원", "ATLANTA BRAVES": "브레이브스",
    "TAKE TWO": "테이크투", "ELECTRONIC ARTS": "EA", "FORD": "포드", "GENERAL MOTORS": "GM",
    "RIVIAN": "리비안", "LUCID": "루시드", "CARVANA": "카바나", "AUTOZONE": "오토존", "OREILLY": "오라일리",
    # 헬스케어
    "UNITEDHEALTH": "UNH", "JOHNSON & JOHNSON": "J&J", "JOHNSON JOHNSON": "J&J",
    "PFIZER": "화이자", "ELI LILLY": "일라이릴리", "LILLY ELI": "일라이릴리", "MERCK": "머크",
    "ABBVIE": "애브비", "AMGEN": "암젠", "GILEAD": "길리어드", "BRISTOL MYERS": "BMS", "MODERNA": "모더나",
    "REGENERON": "리제네론", "VERTEX": "버텍스", "THERMO FISHER": "써모피셔", "DANAHER": "다나허",
    "ABBOTT": "애보트", "MEDTRONIC": "메드트로닉", "INTUITIVE SURGICAL": "인튜이티브", "STRYKER": "스트라이커",
    "BOSTON SCIENTIFIC": "보스턴SC", "CVS": "CVS", "CIGNA": "시그나", "HUMANA": "휴매나",
    "ELEVANCE": "엘리번스", "HCA": "HCA", "DAVITA": "다비타", "ZOETIS": "조에티스",
    "CRISPR": "크리스퍼", "ASTRAZENECA": "아스트라",
    # 산업·에너지·소재
    "EXXON MOBIL": "엑슨모빌", "CHEVRON": "셰브론", "OCCIDENTAL": "옥시덴탈", "CONOCOPHILLIPS": "코노코",
    "SCHLUMBERGER": "슐룸베르거",  "EOG": "EOG", "DEVON": "데번에너지",
    "BOEING": "보잉", "LOCKHEED": "록히드마틴", "RTX": "RTX", "RAYTHEON": "RTX", "NORTHROP": "노스롭",
    "GENERAL DYNAMICS": "GD", "GENERAL ELECTRIC": "GE", "GE AEROSPACE": "GE",
    "HONEYWELL": "허니웰", "CATERPILLAR": "캐터필러", "DEERE": "존디어", "3M": "3M", "UNION PACIFIC": "유니언퍼시픽",
    "CSX": "CSX", "NORFOLK": "노퍽서던", "CANADIAN NATL": "CN철도", "CANADIAN NATIONAL": "CN철도",
    "CANADIAN PACIFIC": "CP철도", "FEDEX": "페덱스", "UNITED PARCEL": "UPS", "UPS": "UPS",
    "DELTA AIR": "델타항공", "UNITED AIRLINES": "유나이티드", "SOUTHWEST": "사우스웨스트",
    "AMERICAN AIRLINES": "아메리칸항공", "SPIRIT AIRLINES": "스피릿항공", "JETBLUE": "제트블루", "ALASKA AIR": "알래스카항공",
    "WASTE MANAGEMENT": "WM", "REPUBLIC SERVICES": "리퍼블릭", "ECOLAB": "에코랩", "SHERWIN": "셔윈",
    "LINDE": "린데", "AIR PRODUCTS": "에어프로덕츠", "FREEPORT": "프리포트", "NEWMONT": "뉴몬트",
    "NUCOR": "뉴코어", "DOW": "다우케미칼", "DUPONT": "듀폰", "CRH": "CRH", "VULCAN": "벌컨", "MARTIN MARIETTA": "마틴마리에타",
    "LENNAR": "레나", "DR HORTON": "DR호튼", "NVR": "NVR", "PULTE": "풀티", "HEICO": "헤이코",
    "LOUISIANA PAC": "LP", "TRANSDIGM": "트랜스다임", "PARKER HANNIFIN": "파커",
    "EMERSON": "에머슨", "ILLINOIS TOOL": "ITW", "CINTAS": "신타스", "FASTENAL": "패스널",
    # 통신·유틸리티·부동산
    "AT&T": "AT&T", "VERIZON": "버라이즌", "T MOBILE": "T모바일", "TELEPHONE & DATA": "TDS", "TELEPHONE DATA": "TDS",
    "NEXTERA": "넥스트에라", "DUKE ENERGY": "듀크에너지", "SOUTHERN CO": "서던컴퍼니", "DOMINION": "도미니언",
    "CONSTELLATION ENERGY": "컨스텔E", "VISTRA": "비스트라", "AMERICAN TOWER": "아메리칸타워",
    "PROLOGIS": "프로로지스", "EQUINIX": "에퀴닉스", "CROWN CASTLE": "크라운캐슬", "REALTY INCOME": "리얼티인컴",
    "SIMON PROPERTY": "사이먼", "PUBLIC STORAGE": "퍼블릭ST", "WELLTOWER": "웰타워",
    # 중국·기타 해외
    "ALIBABA": "알리바바", "PINDUODUO": "핀둬둬", "PDD": "핀둬둬", "JD COM": "징둥", "BAIDU": "바이두",
    "TENCENT": "텐센트", "NIO": "니오", "XPENG": "샤오펑", "LI AUTO": "리오토", "BILIBILI": "빌리빌리",
    "MERCADOLIBRE": "메르카도", "SPOTIFY": "스포티파이",
    "SHELL": "로열더치셸", "BP": "BP", "MITSUBISHI": "미쓰비시", "MITSUI": "미쓰이",
    "ITOCHU": "이토추", "SUMITOMO": "스미토모", "MARUBENI": "마루베니", "UNILEVER": "유니레버",
    "NOVARTIS": "노바티스", "ROCHE": "로슈", "LVMH": "LVMH",
    # ── 추가: S&P500·나스닥100 나머지 + 13F 단골 ──
    # 기술
    "AMPHENOL": "암페놀", "ANSYS": "앤시스", "AKAMAI": "아카마이",
    "APPLOVIN": "앱러빈",  "AUTOMATIC DATA": "ADP", "BROADRIDGE": "브로드리지",
    "CDW": "CDW", "CHECK POINT": "체크포인트", "COGNIZANT": "코그니전트", 
    "CORNING": "코닝", "COSTAR": "코스타", "CTS": "CTS", "DEXCOM": "덱스콤", "DOCUSIGN": "도큐사인",
    "DROPBOX": "드롭박스", "DYNATRACE": "다이나", "ELASTIC": "일래스틱", "ENPHASE": "엔페이즈",
    "EPAM": "EPAM", "F5": "F5", "FAIR ISAAC": "FICO", "FIRST SOLAR": "퍼스트솔라", "GARMIN": "가민",
    "GARTNER": "가트너", "GEN DIGITAL": "젠디지털", "GITLAB": "깃랩", "GLOBALFOUNDRIES": "GF",
    "GLOBANT": "글로반트", "GODADDY": "고대디", "HUBSPOT": "허브스팟", "JABIL": "제이빌", "JACK HENRY": "잭헨리",
    "JUNIPER": "주니퍼", "KEYSIGHT": "키사이트", "LEIDOS": "레이도스", "MARVELL": "마벨", "MICROCHIP": "마이크로칩",
    "MONOLITHIC POWER": "MPS", "MOTOROLA": "모토로라", "NETAPP": "넷앱", "ON SEMICONDUCTOR": "온세미",
    "PAYCHEX": "페이첵스", "PAYCOM": "페이컴", "PTC": "PTC", "QORVO": "코보", "RINGCENTRAL": "링센트럴",
    "SAMSARA": "삼사라", "SEAGATE": "시게이트", "SKYWORKS": "스카이웍스", "SMARTSHEET": "스마트시트",
    "SQUARESPACE": "스퀘어SP", "TERADYNE": "테라다인", "TRIMBLE": "트림블", "TYLER": "타일러",
    "UIPATH": "유아이패스", "VEEVA": "비바", "VERISIGN": "베리사인", "WESTERN DIGITAL": "웨스턴디지털",
    "ZEBRA": "지브라", "ZILLOW": "질로우", "ASTERA": "아스테라랩스", "CREDO": "크레도테크", "IONQ": "아이온큐",
    "RIGETTI": "리게티", "D WAVE": "디웨이브", "SOUNDHOUND": "사운드하운드", "C3 AI": "C3AI", "BIGBEAR": "빅베어",
    "ROCKET LAB": "로켓랩", "ASTS": "AST", "AST SPACEMOBILE": "AST", "JOBY": "조비", "ARCHER": "아처",
    "TEMPUS": "템퍼스AI", "HIMS": "힘스앤허스", "OKLO": "오클로", "NUSCALE": "뉴스케일", "CAMECO": "카메코",
    "QUANTUM COMPUTING": "퀀텀컴퓨팅", "CIRCLE INTERNET": "서클인터넷", "MICROSTRATEGY": "MSTR",
    "STRATEGY INC": "MSTR", "MARATHON DIGITAL": "마라홀딩스", "MARA": "마라홀딩스", "RIOT": "라이엇플랫폼",
    "CLEANSPARK": "클린스파크", "CORE SCIENTIFIC": "코어SCI", "IREN": "아이렌", "CIPHER MINING": "사이퍼마이닝",
    "NEBIUS": "네비우스", "COREWEAVE": "코어위브", "SANDISK": "샌디스크", "SEALSQ": "실스큐",
    # 금융 추가
    "AFLAC": "아플락", "ALLSTATE": "올스테이트", "AMERIPRISE": "아메리프", "ARCH CAPITAL": "아치캐피털",
    "ARES": "아레스", "ARTHUR J GALLAGHER": "갤러거", "BANK NEW YORK": "BNY멜론", "BANK OF NEW YORK": "BNY멜론",
    "BROWN & BROWN": "브라운", "CBOE": "CBOE", "CINCINNATI FINL": "신시내티", "CITIZENS FINL": "시티즌스",
    "COINBASE": "코인베이스", "DISCOVER": "디스커버", "EQUIFAX": "에퀴팩스", "EVEREST": "에베레스트",
    "FIFTH THIRD": "피프스서드", "FRANKLIN RES": "프랭클린", "GLOBAL PAYMENTS": "글로벌PM",
    "HARTFORD": "하트포드", "HUNTINGTON": "헌팅턴", "INTERACTIVE BROKERS": "IBKR", "INVESCO": "인베스코",
    "KEYCORP": "키코프", "LPL": "LPL", "M&T BANK": "M&T", "MARKETAXESS": "마켓액세스",
    "NASDAQ": "나스닥", "NORTHERN TRUST": "노던트러스트", "PRINCIPAL": "프린시펄", "RAYMOND JAMES": "레이먼드",
    "REGIONS": "리전스", "STATE STREET": "스테이트ST", "SYNCHRONY": "싱크로니", "T ROWE": "T로우",
    "TRAVELERS": "트래블러스", "W R BERKLEY": "WR버클리", "WILLIS": "윌리스타워스", "ROBINHOOD": "로빈후드",
    "CARLYLE": "칼라일", "TPG": "TPG", "STONEX": "스톤엑스", "UPSTART": "업스타트",
    "AFFIRM": "어펌", "TOAST": "토스트", "MARQETA": "마케타", "LEMONADE": "레모네이드", "ROOT": "루트보험",
    # 소비 추가
    "ABERCROMBIE": "아베크롬비", "AMER SPORTS": "아머스포츠", "APTIV": "앱티브", "BATH & BODY": "배스앤바디",
    "BEST BUY": "베스트바이", "BORGWARNER": "보그워너", "BROWN FORMAN": "브라운포먼", "BUNGE": "벙기",
    "BURLINGTON": "벌링턴", "CAESARS": "시저스", "CAMPBELL": "캠벨", "CARMAX": "카맥스", "CARNIVAL": "카니발",
    "CHURCH & DWIGHT": "처치DW", "CLOROX": "클로락스", "CONAGRA": "코나그라", "COPART": "코파트",
    "DARDEN": "다든레스토랑", "DECKERS": "데커스", "DRAFTKINGS": "드래프트킹스", "EBAY": "이베이",
    "ETSY": "엣시", "EXPEDIA": "익스피디아", "GENERAL MILLS": "제너럴밀스", "GENUINE PARTS": "제뉴인파츠",
    "HASBRO": "해즈브로", "HERSHEY": "허쉬", "HORMEL": "호멜", "J M SMUCKER": "스머커", "KELLANOVA": "켈라노바",
    "KEURIG": "큐리그", "LAMB WESTON": "램웨스턴", "LKQ": "LKQ", "MATTEL": "마텔", "MCCORMICK": "맥코믹",
    "MGM": "MGM", "MOHAWK": "모호크", "MOLSON": "몰슨", "MONSTER": "몬스터", "NORWEGIAN": "노르웨지안",
    "PELOTON": "펠로톤", "PHILIP MORRIS": "필립모리스", "POOL": "풀코퍼레이션", "RALPH LAUREN": "랄프로렌",
    "ROYAL CARIBBEAN": "로얄캐리비안", "SKECHERS": "스케쳐스", "SYSCO": "시스코푸드", "TAPESTRY": "태피스트리",
    "TRACTOR SUPPLY": "트랙터SP", "TYSON": "타이슨", "ULTA": "울타", "V F CORP": "VF", "WAYFAIR": "웨이페어",
    "WENDYS": "웬디스", "WHIRLPOOL": "월풀", "WILLIAMS SONOMA": "윌리엄스SN", "WYNN": "윈리조트", "YUM": "얌브랜즈",
    "CAVA": "카바", "SWEETGREEN": "스위트그린", "CELSIUS": "셀시어스", "ON HOLDING": "온러닝", "BIRKENSTOCK": "버켄스탁",
    "CROCS": "크록스", "DUTCH BROS": "더치브로스", "SHAKE SHACK": "쉐이크쉑", "WINGSTOP": "윙스탑",
    "GAP": "갭(GAP)", "FOOT LOCKER": "풋락커", "DICKS": "딕스스포팅", "FIVE BELOW": "파이브빌로우", "OLLIES": "올리스",
    "CHEWY": "츄이", "PETCO": "펫코", "WARBY": "와비파커", "FIGS": "피그스", "REVOLVE": "리볼브",
    "NEWS CORP": "뉴스코프", "NEW YORK TIMES": "NYT", "FOX CORP": "폭스", "PARAMOUNT": "파라마운트",
    "AMC ENTERTAINMENT": "AMC", "CINEMARK": "시네마크", "MADISON SQUARE": "MSG", "ENDEAVOR": "엔데버", "TKO": "TKO",
    "SPHERE": "스피어엔터", "TRADE DESK": "TTD", "MATCH": "매치그룹", "BUMBLE": "범블",
    # 헬스케어 추가
    "AGILENT": "애질런트", "ALIGN": "얼라인", "BAXTER": "박스터", "BECTON": "BD", "BIOGEN": "바이오젠",
    "BIO RAD": "바이오라드", "BIO TECHNE": "바이오테크네", "CARDINAL": "카디널", "CENCORA": "센코라",
    "CHARLES RIVER": "찰스리버", "COOPER": "쿠퍼컴퍼니스", "CORPAY": "코페이", "DENTSPLY": "덴츠플라이", "EDWARDS": "에드워즈",
    "GE HEALTHCARE": "GE헬스케어", "HOLOGIC": "홀로직", "IDEXX": "아이덱스", "ILLUMINA": "일루미나",
    "INCYTE": "인사이트", "INSULET": "인슐렛", "IQVIA": "아이큐비아", "LABCORP": "랩코프", "MCKESSON": "맥케슨",
    "METTLER": "메틀러", "MOLINA": "몰리나", "QUEST": "퀘스트진단",  "REVVITY": "레비티",
    "SOLVENTUM": "솔벤텀", "STERIS": "스테리스", "TELEFLEX": "텔레플렉스", "UNIVERSAL HEALTH": "UHS",
    "VIATRIS": "비아트리스", "WATERS": "워터스", "WEST PHARM": "웨스트파마", "ZIMMER": "짐머",
    "ALNYLAM": "앨나일람", "ARGENX": "아젠엑스", "BIONTECH": "바이오엔텍", "EXACT SCIENCES": "이그잭트",
    "NATERA": "나테라", "NEUROCRINE": "뉴로크린", "SAREPTA": "사렙타", "UNITED THERAPEUTICS": "UTHR",
    "VIKING": "바이킹", "SUMMIT THERAPEUTICS": "서밋", "ROIVANT": "로이반트", "INSMED": "인스메드",
    "GUARDANT": "가던트", "TWIST": "트위스트", "10X GENOMICS": "10X", "PACIFIC BIOSCIENCES": "팩바이오",
    "BEAM": "빔테라퓨틱스", "INTELLIA": "인텔리아", "EDITAS": "에디타스", "RECURSION": "리커전", "SCHRODINGER": "슈뢰딩거",
    "TELADOC": "텔라닥", "OSCAR": "오스카헬스", "CLOVER": "클로버헬스", "HIMS & HERS": "힘스앤허스",
    # 산업·에너지·소재 추가
    "A O SMITH": "AO스미스", "ALBEMARLE": "앨버말", "ALLEGION": "알레지온", "AMCOR": "암코",
    "AMETEK": "아메텍", "APA": "APA", "ARCHER DANIELS": "ADM", "AVERY": "에이버리", "AXON": "액손",
    "BAKER HUGHES": "베이커휴즈", "BALL": "볼코퍼레이션", "CARRIER": "캐리어", "CF INDUSTRIES": "CF", "CHENIERE": "셰니에르",
    "CHART": "차트", "COTERRA": "코테라", "CUMMINS": "커민스", "CELANESE": "셀라니즈", "CORTEVA": "코르테바",
    "DIAMONDBACK": "다이아몬드백", "DOVER": "도버", "EASTMAN": "이스트먼", "EXPEDITORS": "익스페디터스",
    "FORTIVE": "포티브", "GENERAC": "제너락", "GRAINGER": "그레인저", "HALLIBURTON": "할리버튼",
    "HESS": "헤스", "HOWMET": "하우멧", "HUBBELL": "허벨", "HUNTINGTON INGALLS": "헌팅턴잉걸스",
    "IDEX": "IDEX", "INGERSOLL": "잉거솔", "INTL PAPER": "IP", "INTERNATIONAL PAPER": "IP",
    "J B HUNT": "JB헌트", "JOHNSON CONTROLS": "존슨컨트롤스", "KINDER MORGAN": "킨더모건", "L3HARRIS": "L3해리스",
    "LYONDELLBASELL": "라이온델", "MARATHON PETE": "마라톤", "MARATHON PETROLEUM": "마라톤", "MASCO": "마스코",
    "MOSAIC": "모자이크", "NORDSON": "노드슨", "OLD DOMINION": "올드도미니언", "ONEOK": "원오크", "OTIS": "오티스",
    "OWENS CORNING": "오웬스코닝", "PACCAR": "팩카", "PACKAGING CORP": "PCA", "PENTAIR": "펜테어",
    "PHILLIPS 66": "필립스66", "PPG": "PPG", "QUANTA": "콴타", "ROCKWELL": "록웰", "ROLLINS": "롤린스",
    "ROPER": "로퍼", "SMURFIT": "스머핏", "SNAP ON": "스냅온", "STANLEY BLACK": "스탠리", "STEEL DYNAMICS": "스틸DX",
    "TARGA": "타르가", "TEXTRON": "텍스트론", "TRANE": "트레인", "UNITED RENTALS": "URI",
    "VALERO": "발레로", "VERALTO": "베랄토", "W W GRAINGER": "그레인저", "WESTINGHOUSE AIR": "왑텍", "WABTEC": "왑텍",
    "WILLIAMS COS": "윌리엄스", "XYLEM": "자일럼", "GE VERNOVA": "GE버노바", "GEV": "GE버노바",
    "EATON": "이튼", "KRATOS": "크라토스", "AEROVIRONMENT": "AV",
    "PALANTIR": "팔란티어", "BWX": "BWX", "CURTISS": "커티스", "HEXCEL": "헥셀", "SPIRIT AERO": "스피릿",
    "ALCOA": "알코아", "CLEVELAND CLIFFS": "클리프스", "US STEEL": "US스틸", "UNITED STATES STEEL": "US스틸",
    "SOUTHERN COPPER": "서던코퍼", "AGNICO": "아그니코", "WHEATON": "휘튼",
    "FRANCO NEVADA": "프랑코네바다", "ROYAL GOLD": "로열골드", "KINROSS": "킨로스", "SSR MINING": "SSR",
    "MP MATERIALS": "MP", "LITHIUM AMERICAS": "리튬AM", "PIEDMONT": "피드몬트",
    "SUNRUN": "선런", "PLUG POWER": "플러그파워", "BLOOM ENERGY": "블룸에너지", "FLUENCE": "플루언스",
    "TALEN": "탤런에너지", "NRG": "NRG", "AES": "AES", "CENTERPOINT": "센터포인트", "PG&E": "PG&E", "PACIFIC GAS": "PG&E",
    "EDISON INTL": "에디슨", "XCEL": "엑셀", "ENTERGY": "엔터지", "EVERSOURCE": "에버소스", "EXELON": "엑셀론",
    "PUBLIC SERVICE": "PSEG", "SEMPRA": "셈프라", "AMERICAN ELECTRIC": "AEP", "AMERICAN WATER": "아메리칸워터",
    "ATMOS": "아트모스", "CONSOLIDATED EDISON": "콘에디슨", "DTE": "DTE", "FIRSTENERGY": "퍼스트에너지",
    "PPL": "PPL", "WEC": "WEC", "ALLIANT": "얼라이언트", "AMEREN": "아메렌", "CMS": "CMS", "EVERGY": "에버지",
    "NISOURCE": "나이소스", "PINNACLE WEST": "피너클", "PORTLAND GENERAL": "포틀랜드",
    # 부동산 추가
    "ALEXANDRIA": "알렉산드리아", "AVALONBAY": "아발론베이", "BOSTON PROPERTIES": "BXP", "BXP": "BXP",
    "CAMDEN": "캠든", "DIGITAL REALTY": "디지털리얼티", "EQUITY RESIDENTIAL": "에쿼티RE",
    "ESSEX": "에식스", "EXTRA SPACE": "엑스트라", "FEDERAL REALTY": "페더럴리얼티", "HEALTHPEAK": "헬스피크",
    "HOST HOTELS": "호스트호텔", "INVITATION HOMES": "인비테이션", "IRON MOUNTAIN": "아이언마운틴",
    "KIMCO": "킴코", "MID AMERICA APT": "MAA", "REGENCY": "리젠시", "SBA COMMUNICATIONS": "SBA",
    "UDR": "UDR", "VENTAS": "벤타스", "VICI": "VICI", "WEYERHAEUSER": "웨이어하우저", "CBRE": "CBRE",
    "SUN COMMUNITIES": "선커뮤니티", "EQUITY LIFESTYLE": "ELS", "AMERICOLD": "아메리콜드", "OPENDOOR": "오픈도어",
    "REXFORD": "렉스포드", "STAG": "STAG", "W P CAREY": "WP케리", "GAMING & LEISURE": "GLPI",
    # 해외 추가
    "BANCO SANTANDER": "산탄데르", "BBVA": "BBVA", "HSBC": "HSBC", "BARCLAYS": "바클레이즈", "UBS": "UBS",
    "DEUTSCHE BANK": "도이체방크", "ING": "ING", "MITSUBISHI UFJ": "MUFG", "SUMITOMO MITSUI": "SMFG",
    "MIZUHO": "미즈호", "NOMURA": "노무라", "HONDA": "혼다", "NISSAN": "닛산", "TOYOTA": "도요타", "CANON": "캐논",
    "NINTENDO": "닌텐도", "TAKEDA": "다케다", "ORIX": "오릭스", "SONY": "소니", "HITACHI": "히타치",
    "SAMSUNG": "삼성", "SK HYNIX": "SK하이닉스", "KB FINL": "KB금융", "SHINHAN": "신한", "WOORI": "우리",
    "POSCO": "포스코", "LG DISPLAY": "LGD", "COUPANG": "쿠팡", "GRAVITY": "그래비티", "WEBZEN": "웹젠",
    "INFOSYS": "인포시스", "WIPRO": "위프로", "HDFC": "HDFC", "ICICI": "ICICI", "RELIANCE": "릴라이언스",
    "VALE": "발레", "PETROBRAS": "페트로브라스", "ITAU": "이타우", "AMBEV": "암베브", "NUBANK": "누뱅크",
    "STONECO": "스톤코", "PAGSEGURO": "파그세구로", "XP INC": "XP", "COPA": "코파항공", "GRUPO TELEVISA": "텔레비사",
    "AMERICA MOVIL": "아메리카모빌", "FOMENTO": "펨사", "FEMSA": "펨사", "CEMEX": "시멕스", "WALMEX": "월멕스",
    "TSMC": "TSMC", "UNITED MICRO": "UMC", "ASE": "ASE", "CHUNGHWA": "중화텔레콤", "HIMAX": "하이맥스",
    "NETEASE": "넷이즈", "TRIP COM": "트립닷컴", "YUM CHINA": "얌차이나", "ZTO": "ZTO", "FUTU": "푸투",
    "IQIYI": "아이치이", "WEIBO": "웨이보", "KANZHUN": "칸준", "BOSS ZHIPIN": "칸준", "TAL EDUCATION": "TAL",
    "NEW ORIENTAL": "신동방", "VIPSHOP": "VIP샵", "ZAI LAB": "자이랩", "BEIGENE": "베이진", "LEGEND BIOTECH": "레전드",
    "MINISO": "미니소", "ATOUR": "아투어", "H WORLD": "화주그룹", "YUM BRANDS": "얌브랜즈", "SEA": "씨리미티드",
    "SHOPIFY": "쇼피파이", "CANADIAN NATURAL": "CNQ", "SUNCOR": "선코어", "ENBRIDGE": "엔브리지",
    "TC ENERGY": "TC에너지", "BROOKFIELD": "브룩필드", "THOMSON REUTERS": "톰슨로이터", "WASTE CONNECTIONS": "웨이스트CN",
    "CGI": "CGI", "OPEN TEXT": "오픈텍스트", "BCE": "BCE", "TELUS": "텔러스", "ROGERS": "로저스",
    "ROYAL BANK": "RBC", "TORONTO DOMINION": "TD", "BANK NOVA SCOTIA": "스코샤", "BANK MONTREAL": "BMO",
    "CANADIAN IMPERIAL": "CIBC", "MANULIFE": "매뉴라이프", "SUN LIFE": "선라이프", "FAIRFAX": "페어팩스",
    "RESTAURANT BRANDS": "RBI", "DOLLARAMA": "달라라마", "COUCHE TARD": "쿠쉬타르", "LULULEMON": "룰루레몬",
    "NUTRIEN": "뉴트리엔", "BARRICK": "배릭", "TECK": "텍리소스", "FIRST QUANTUM": "퍼스트퀀텀", "IVANHOE": "아이반호",
    "MAGNA": "마그나", "BOMBARDIER": "봄바디어", "CAE": "CAE", "AIR CANADA": "에어캐나다",
    "NOVO NORDISK": "노보노디스크", "SANOFI": "사노피", "GSK": "GSK", "GLAXO": "GSK", "BAYER": "바이엘",
    "SIEMENS": "지멘스", "SCHNEIDER": "슈나이더", "ABB": "ABB", "AIRBUS": "에어버스", "SAFRAN": "사프란",
    "RHEINMETALL": "라인메탈", "BAE": "BAE", "ROLLS ROYCE": "롤스로이스", "VOLKSWAGEN": "폭스바겐",
    "MERCEDES": "메르세데스", "BMW": "BMW", "STELLANTIS": "스텔란티스", "FERRARI": "페라리", "PORSCHE": "포르쉐",
    "ADIDAS": "아디다스", "PUMA": "푸마", "HERMES": "에르메스", "KERING": "케링", "RICHEMONT": "리치몬트",
    "SWATCH": "스와치", "DIAGEO": "디아지오", "HEINEKEN": "하이네켄", "AB INBEV": "AB인베브", "ANHEUSER": "AB인베브",
    "BRITISH AMERICAN": "BAT", "IMPERIAL BRANDS": "임페리얼", "RIO TINTO": "리오틴토", "BHP": "BHP",
    "GLENCORE": "글렌코어", "ANGLO AMERICAN": "앵글로", "TOTALENERGIES": "토탈에너지스", "ENI": "ENI",
    "EQUINOR": "에퀴노르", "REPSOL": "렙솔", "ORSTED": "오스테드", "VESTAS": "베스타스", "ENEL": "에넬",
    "IBERDROLA": "이베르드롤라", "NATIONAL GRID": "내셔널그리드", "VODAFONE": "보다폰", "DEUTSCHE TELEKOM": "도이체텔레콤",
    "TELEFONICA": "텔레포니카", "ORANGE": "오랑주", "ERICSSON": "에릭슨", "NOKIA": "노키아",
    "ASML": "ASML", "INFINEON": "인피니언", "STMICRO": "ST마이크로", "NXP": "NXP", "ARM": "ARM",
    "SAP": "SAP", "ACCENTURE": "액센츄어", "CAPGEMINI": "캡제미니", "DASSAULT": "다쏘", "AMADEUS": "아마데우스",
    "ADYEN": "아디옌", "WISE": "와이즈", "ALLIANZ": "알리안츠", "AXA": "AXA", "ZURICH": "취리히", "MUNICH RE": "뮌헨리",
    "SWISS RE": "스위스리", "PRUDENTIAL PLC": "푸르덴셜", "LEGAL & GENERAL": "L&G", "AVIVA": "아비바",
    "LLOYDS": "로이즈", "NATWEST": "냇웨스트", "STANDARD CHARTERED": "SC제일", "BNP": "BNP파리바",
    "SOCIETE GENERALE": "소시에테", "CREDIT AGRICOLE": "크레디A", "INTESA": "인테사", "UNICREDIT": "유니크레딧",
    "NESTLE": "네슬레", "DANONE": "다논", "LOREAL": "로레알", "RECKITT": "레킷",
    "AIRBNB": "에어비앤비", "BOOKING": "부킹", "RYANAIR": "라이언에어", "LUFTHANSA": "루프트한자",
    "INTERNATIONAL CONSOLIDATED": "IAG", "IAG": "IAG", "ACCOR": "아코르", "IHG": "IHG",
    "COMPASS": "컴패스그룹", "SODEXO": "소덱소", "RELX": "RELX", "WOLTERS": "볼터스", "EXPERIAN": "익스피리언",
    "LONDON STOCK": "LSE", "DEUTSCHE BOERSE": "도이체뵈르제", "EURONEXT": "유로넥스트",
    "TENCENT MUSIC": "텐센트뮤직", "KUAISHOU": "콰이쇼우", "MEITUAN": "메이투안", "XIAOMI": "샤오미",
    "BYD": "BYD", "GEELY": "지리", "CATL": "CATL", "PING AN": "핑안", "ICBC": "공상은행", "CHINA CONSTRUCTION": "건설은행",
    "MOUTAI": "마오타이", "KWEICHOW": "마오타이", "CHINA MOBILE": "차이나모바일", "PETROCHINA": "페트로차이나",
    "SINOPEC": "시노펙", "CNOOC": "CNOOC", "LENOVO": "레노버", "SMIC": "SMIC", "HUA HONG": "화홍",
    "SAUDI ARAMCO": "아람코", "ARAMCO": "아람코", "TEMASEK": "테마섹", "DBS": "DBS", "OCBC": "OCBC", "UOB": "UOB",
    "SINGAPORE TELECOM": "싱텔", "SINGTEL": "싱텔", "GRAB": "그랩", "SEA LTD": "씨리미티드", "GARENA": "가레나",
    "COMMONWEALTH BANK": "CBA", "WESTPAC": "웨스트팩", "ANZ": "ANZ", "MACQUARIE": "맥쿼리",
    "CSL": "CSL", "WOOLWORTHS": "울워스", "FORTESCUE": "포테스큐", "WOODSIDE": "우드사이드", "ATLASSIAN": "아틀라시안",
    "WISETECH": "와이즈테크", "XERO": "제로", "REA GROUP": "REA그룹", "COCHLEAR": "코클리어", "RESMED": "레즈메드",
    "TELSTRA": "텔스트라", "QANTAS": "콴타스", "AFTERPAY": "애프터페이", "BLOCK": "블록",
    # ETF
    "SPDR S&P 500": "S&P500", "ISHARES CORE S&P 500": "S&P500", "VANGUARD S&P 500": "S&P500",
    "INVESCO QQQ": "QQQ", "ISHARES TRUST CORE S&P 500": "S&P500", "ISHARES CORE S&P": "S&P500",
    "ISHARES TRUST": "아이셰어즈", "SPDR S&P 500 ETF": "S&P500", "VANGUARD INDEX": "뱅가드",
    "AMERICAN AIRLINES": "아메리칸항공", "SPIRIT AIRLINES": "스피릿항공", "JETBLUE": "제트블루", "ALASKA AIR": "알래스카항공", "SPDR GOLD": "금(GLD)", "ISHARES RUSSELL 2000": "IWM",
    "ISHARES MSCI": "MSCI", "VANGUARD TOTAL": "VTI", "ARK INNOVATION": "ARKK",
    "ISHARES 20": "TLT", "ISHARES BITCOIN": "비트코인", "GRAYSCALE BITCOIN": "비트코인",

    # ETF 운용사 — 공시에는 "…TR", "…FDS" 같은 신탁 이름으로 올라온다
    "SELECT SECTOR SPDR": "SPDR섹터", "SPDR SERIES": "SPDR", "SPDR SER": "SPDR",
    "SPDR INDEX SHS": "SPDR", "SPDR PORTFOLIO": "SPDR",
    "VANGUARD WORLD": "뱅가드", "VANGUARD SCOTTSDALE": "뱅가드",
    "VANGUARD BD INDEX": "뱅가드채권", "VANGUARD BOND INDEX": "뱅가드채권",
    "VANGUARD ADMIRAL": "뱅가드", "VANGUARD STAR": "뱅가드", "VANGUARD TAX": "뱅가드",
    "VANGUARD SPECIALIZED": "뱅가드", "VANGUARD INTL": "뱅가드",
    "ISHARES INC": "아이셰어즈", "ISHARES SILVER": "은(SLV)", "ISHARES GOLD": "금(IAU)",
    "INVESCO EXCH TRADED": "인베스코", "INVESCO EXCHANGE TRADED": "인베스코",
    "FIRST TR EXCHANGE TRADED": "퍼스트TR", "FIRST TRUST EXCHANGE": "퍼스트TR",
    "DIREXION SHARES": "디렉시온", "DIREXION": "디렉시온",
    "PROSHARES": "프로셰어즈", "GLOBAL X": "글로벌X", "WISDOMTREE": "위즈덤트리",
    "VANECK": "반에크", "SCHWAB STRATEGIC": "슈왑ETF", "SCHWAB US": "슈왑ETF",
    "JPMORGAN EXCHANGE TRADED": "JP모건", "GOLDMAN SACHS ETF": "골드만ETF",
    "FIDELITY COVINGTON": "피델리티", "FIDELITY MERRIMACK": "피델리티",
    "DIMENSIONAL ETF": "DFA", "DIMENSIONAL FD": "DFA",
    "AMERICAN CENTURY ETF": "센추리",
    "JANUS DETROIT STREET": "야누스", "JANUS HENDERSON": "야누스",
    "PACER FDS": "페이서", "AMPLIFY ETF": "앰플리파이", "ROUNDHILL": "라운드힐",
    "YIELDMAX": "일드맥스", "DEFIANCE ETFS": "디파이언스", "TIDAL": "타이달",
    "GRAYSCALE": "그레이스케일", "BITWISE": "비트와이즈", "VALKYRIE": "발키리",
    "FRANKLIN TEMPLETON ETF": "프랭클린", "NEUBERGER BERMAN ETF": "뉴버거",
    "KRANESHARES": "크레인셰어즈", "MATTHEWS INTL FDS": "매튜스",
    "XTRACKERS": "X트래커스", "DBX ETF": "X트래커스",

    # 영문으로 남던 중견 기업 — 한글로 읽기 쉽게
    "ENERGIZER": "에너자이저", "CHEESECAKE FACTORY": "치즈케이크",
    "TEXAS ROADHOUSE": "텍사스로드", "BOSTON BEER": "보스턴비어",
    "ELF BEAUTY": "엘프뷰티", "TEMPUR SEALY": "템퍼실리", "SLEEP NUMBER": "슬립넘버",
    "NEWELL BRANDS": "뉴웰브랜즈", "FLOWERS FOODS": "플라워푸드",
    "HENRY SCHEIN": "헨리샤인", "CENTENE": "센틴", "ENCOMPASS HEALTH": "엔컴패스",
    "GLOBUS MEDICAL": "글로버스", "LEGGETT": "레깃플랫", "MASIMO": "마시모",
    "GRACO": "그라코", "POST HOLDINGS": "포스트", "COTY": "코티", "KENVUE": "켄뷰",
    "PENUMBRA": "페넘브라", "TOPBUILD": "탑빌드", "NORDSON": "노드슨",
    "BUILDERS FIRSTSOURCE": "빌더스", "FLOOR & DECOR": "플로어앤데코",
    "INSTALLED BLDG": "IBP", "ADVANCED DRAINAGE": "ADS",
    "WATTS WATER": "와츠워터", "LINCOLN ELECTRIC": "링컨일렉트릭",
    "INSPIRE MEDICAL": "인스파이어", "WEST PHARMACEUTICAL": "웨스트팜",
    "LABORATORY AMERICAN": "랩콥", "LABCORP": "랩콥", "LABORATORY CORP": "랩콥", "LABORATORY": "랩콥",
    "BIOMARIN": "바이오마린", "JAZZ PHARMACEUTICALS": "재즈파마",
    "SPECTRUM BRANDS": "스펙트럼", "REYNOLDS CONSUMER": "레이놀즈",
    "PURPLE INNOVATION": "퍼플", "SPIRIT AEROSYSTEMS": "스피릿에어로",

    # 미국 지방은행 — 큰 기관 13F 에 잔뜩 들어 있어 영문으로 남기 쉽다
    "EAST WEST BANCORP": "이스트웨스트", "EAST WEST BANCORP DEL": "이스트웨스트",
    "ZIONS": "자이온스", "COMERICA": "코메리카", "WEBSTER FINANCIAL": "웹스터",
    "CULLEN FROST": "컬렌프로스트", "PINNACLE FINANCIAL": "피너클",
    "WESTERN ALLIANCE": "웨스턴은행", "FIRST HORIZON": "FHN", "SYNOVUS": "시노버스",
    "VALLEY NATIONAL": "밸리은행", "OLD NATIONAL": "올드내셔널",
    "GLACIER BANCORP": "글레이셔", "UMB FINANCIAL": "UMB",
    "COMMERCE BANCSHARES": "커머스은행", "BOK FINANCIAL": "BOK",
    "WINTRUST": "윈트러스트", "CATHAY GENERAL": "캐세이은행",
    "PROSPERITY BANCSHARES": "프로스페리티", "BANKUNITED": "BKU",
    "SOUTH STATE": "SSB", "UNITED BANKSHARES": "UBSI", "FULTON FINANCIAL": "풀턴",
    "HANCOCK WHITNEY": "핸콕휘트니", "ASSOCIATED BANC": "ASB",
    "FIRST INTERSTATE": "퍼스트인터", "INDEPENDENT BK": "인디펜던트",
    "COLUMBIA BKG": "컬럼비아", "EAGLE BANCORP": "이글", "AXOS FINANCIAL": "액소스",
    "CUSTOMERS BANCORP": "커스터머스", "SEACOAST BKG": "시코스트",

    # 아시아·유럽 기업
    "ZEEKR": "지커", "LUFAX": "루팍스", "SOFTBANK": "소프트뱅크", "NIDEC": "니덱",
    "KEYENCE": "키엔스", "FAST RETAILING": "유니클로", "SHISEIDO": "시세이도",
    "TOTALENERGIES": "토탈에너지", "TOTAL SA": "토탈에너지",
    "FLOWSERVE": "플로우서브", "BEYOND MEAT": "비욘드미트", "OATLY": "오트리",
}
KO_KEYS = sorted(KO, key=len, reverse=True)

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
    # 줄임말을 먼저 푼다 (AIRLS -> AIRLINES) 그래야 한글 목록과 맞는다
    s = " ".join(ABBR.get(w, w) for w in s.split())
    # 긴 키부터, 단어 경계로만 맞춘다 (ARM 이 ARMSTRONG 에 붙지 않게)
    for k in KO_KEYS:
        if s == k or s.startswith(k + " "):
            return KO[k]
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


def names(only_bad=False):
    """저장된 data/13f.json 의 모든 종목을 '공시 원문 → 지금 → 바뀜' 으로 찍는다."""
    try:
        with open(OUT, encoding="utf-8") as f:
            funds = json.load(f).get("funds", {})
    except Exception as e:                                  # noqa: BLE001
        return log("%s 를 못 읽었습니다 (%s). 먼저 수집을 돌려주세요." % (OUT, e))

    seen = {}
    for key, fd in funds.items():
        for h in fd.get("holdings", []):
            raw = h.get("raw") or h.get("name")
            rec = seen.setdefault(raw, {"old": h.get("name", ""), "funds": set()})
            rec["funds"].add(key)

    rows = []
    for raw, rec in seen.items():
        new = clean_name(raw)
        han = bool(re.search(r"[가-힣]", new))
        rows.append((raw, rec["old"], new, han, len(rec["funds"])))

    han_n = sum(1 for r in rows if r[3])
    log("=" * 78)
    log("13F 종목명 점검  |  %d개 기관 · 종목 %d개" % (len(funds), len(rows)))
    log("  한글 이름 %d개 (%.0f%%) · 영문 남음 %d개"
        % (han_n, han_n * 100.0 / (len(rows) or 1), len(rows) - han_n))
    log("=" * 78)

    def pad(s, w):                       # 한글은 두 칸을 차지한다
        s = str(s)
        cut = ""
        used = 0
        for ch in s:
            cw = 2 if ord(ch) > 0x1100 and not ch.isascii() else 1
            if used + cw > w:
                break
            cut += ch
            used += cw
        return cut + " " * (w - used)

    show = [r for r in rows if not r[3]] if only_bad else rows
    show.sort(key=lambda r: (r[3], -r[4], r[2].lower()))
    log("  %s %s %s %s" % (pad("공시 원문", 34), pad("지금", 22), pad("바뀜", 16), "기관"))
    log("-" * 82)
    for raw, old, new, han, nf in show:
        mark = "→ " if old != new else "  "
        log("%s%s %s %s %d" % (mark, pad(raw, 34), pad(old, 22), pad(new, 16), nf))
    log("-" * 78)
    log("바뀌는 이름 %d개 · 영문 그대로 %d개"
        % (sum(1 for r in rows if r[1] != r[2]), len(rows) - han_n))
    log("\n영문만 보려면:  python3 collect_13f.py --names-bad")
    log("반영하려면:    python3 collect_13f.py        (NAME_VER=%d 이므로 다시 만듭니다)" % NAME_VER)


def main():
    argv = sys.argv[1:]
    if "--verify" in argv:
        return verify()
    if "--names" in argv:
        return names(False)
    if "--names-bad" in argv:
        return names(True)
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
        old = prev.get(key, {})
        if (old.get("acc") == meta["acc"]
                and old.get("namever") == NAME_VER
                and "--force" not in sys.argv):
            log("  %-12s 변화 없음 (%s 보유분)" % (key, meta["period"]))
            continue
        rows, why = fetch_holdings(cik, meta["acc"])
        if not rows:
            fails.append((key, why)); continue
        holdings, n_all, total = build(rows)
        result[key] = {
            "title": title, "entity": sec_name or expect, "cik": cik,
            "period": meta["period"], "filed": meta["filed"], "acc": meta["acc"],
            "count": n_all, "total_value": round(total), "namever": NAME_VER,
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
