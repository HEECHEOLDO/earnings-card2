# 시험용 — 새 인포그래픽 자료 출처가 GitHub 에서 받아지는지 (상태·앞부분만 출력, 저장 안 함)
import os, sys, json, re, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(url, data=None, hd=None, enc=None):
    h = dict(UA); h.update(hd or {})
    rq = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=25) as r:
            b = r.read(); c = r.headers.get_content_charset() or enc or "utf-8"
            return r.status, b.decode(c, "replace")
    except Exception as e:
        return "ERR", repr(e)[:200]
def show(name, st, txt, pat=None):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))
    if pat:
        m = re.search(pat, t); t = t[max(0, m.start() - 100): m.start() + 600] if m else "(패턴 없음) " + t[:300]
    print("==", name, st, len(txt), "|", t[:700], flush=True)
# 1 네이버 증시자금 동향 (예탁금·신용잔고)
st, t = get("https://finance.naver.com/sise/sise_deposit.naver", enc="euc-kr"); show("naver 예탁금", st, t, r"고객예탁금")
# 2 네이버 투자자별 매매동향 (시장 일별)
st, t = get("https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261120&sosok=", enc="euc-kr"); show("naver 투자자 시장", st, t, r"개인")
# 3 네이버 종목 외국인·기관
st, t = get("https://finance.naver.com/item/frgn.naver?code=005930", enc="euc-kr"); show("naver 종목 외국인", st, t, r"외국인")
# 4 KRX 정보데이터시스템 (투자자별 거래실적)
st, t = get("http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", {"bld": "dbms/MDC/STAT/standard/MDCSTAT02201", "locale": "ko_KR", "inqTpCd": "1", "trdVolVal": "2", "askBid": "3", "mktId": "STK", "strtDd": "20261101", "endDd": "20261120", "money": "1"}, {"Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"}); show("krx 투자자", st, t)
# 5 KRX 공매도 잔고 상위
st, t = get("http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", {"bld": "dbms/MDC/STAT/srt/MDCSTAT30801", "locale": "ko_KR", "searchType": "1", "mktId": "STK", "trdDd": "20261118", "inqCond": "STMFRTSCIFDRFS"}, {"Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"}); show("krx 공매도", st, t)
# 6 KIND 시장조치 — 사이드카/서킷브레이커
for u in ["https://kind.krx.co.kr/marketmeasure/sidecar.do?method=searchSidecarMain",
          "https://kind.krx.co.kr/marketmeasure/circuitbreaker.do?method=searchCircuitBreakerMain",
          "https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain"]:
    st, t = get(u); show("kind " + u.split("/")[-1][:40], st, t)
st, t = get("https://kind.krx.co.kr/disclosure/searchtotalinfo.do", {"method": "searchTotalInfoSub", "searchText": "프로그램매매호가 효력정지", "fromDate": "2015-01-01", "toDate": "2026-11-23", "pageIndex": "1", "currentPageSize": "50"}, {"Referer": "https://kind.krx.co.kr/disclosure/searchtotalinfo.do"}); show("kind 통합검색 사이드카", st, t, r"효력정지|사이드카")
# 7 KIND 신규상장
st, t = get("https://kind.krx.co.kr/listinvstg/listingcompany.do", {"method": "searchListingTypeSub", "currentPageSize": "20", "pageIndex": "1", "orderMode": "1", "orderStat": "D", "fromDate": "2026-01-01", "toDate": "2026-11-23"}, {"Referer": "https://kind.krx.co.kr/listinvstg/listingcompany.do"}); show("kind 신규상장", st, t, r"상장일|공모")
# 8 금융투자협회 freesis
st, t = get("https://freesis.kofia.or.kr/stat/FreeSIS.do?parentDivId=MSIS10000000000000&serviceId=STATSCU0100000060"); show("freesis", st, t)
# 9 DART 자기주식 취득 결정 · 임원 소유보고 (회사 1곳)
try:
    import collect as C
    C.API_KEY = C.get_key()
    r = C.api_get("tsstkAqDecsn.json", {"corp_code": "00126380", "bgnde": "20250101", "endde": "20261120"}); print("== dart 자사주 삼성", str(r)[:500])
    r = C.api_get("elestock.json", {"corp_code": "00126380"}); print("== dart 임원 삼성", r.get("status"), len(r.get("list") or []), str((r.get("list") or [None])[-1])[:300])
    r = C.api_get("list.json", {"bgn_de": "20261101", "end_de": "20261120", "pblntf_detail_ty": "B001", "page_count": 100}); print("== dart 주요사항 목록", r.get("status"), r.get("total_count"), [x["report_nm"] for x in (r.get("list") or [])[:8]])
    r = C.api_get("list.json", {"bgn_de": "20261101", "end_de": "20261120", "pblntf_detail_ty": "C001", "page_count": 100}); print("== dart 증권신고서", r.get("status"), r.get("total_count"), [x["corp_name"] + ":" + x["report_nm"] for x in (r.get("list") or [])[:8]])
except Exception as e:
    print("== dart 오류", e)
# 10 SEC Form 4 (EDGAR 최신 목록)
st, t = get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=10&output=atom", hd={"User-Agent": "earnings-card research contact@example.com"}); show("sec form4", st, t, r"<entry>|4 -")
