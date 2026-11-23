# 시험용 2 — 출처 세부 확인
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src_probe import get, show  # noqa: E402  (src_probe 를 불러오면 1차 시험도 다시 돈다 — 출력은 무시)
print("\n\n######## 2차 ########", flush=True)
st, t = get("https://kind.krx.co.kr/main.do?method=loadInitPage&scrnmode=1")
for m in sorted(set(re.findall(r'href="(/[a-z]+/[a-zA-Z0-9_]+\.do[^"]*)"[^>]*>\s*([^<]{1,30})<', t)))[:400]:
    if re.search(r"사이드카|서킷|시장조치|매매거래|상장|신규", m[1]): print("   KIND 메뉴", m)
for u in ["https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261120&sosok=01&page=1",
          "https://finance.naver.com/sise/investorDealTrendDay.nhn?bizdate=20261120&sosok=&page=1",
          "https://m.stock.naver.com/api/stock/005930/trend?pageSize=5",
          "https://m.stock.naver.com/api/index/KOSPI/trend?pageSize=5",
          "https://finance.naver.com/sise/sise_deposit.naver?page=1"]:
    st, t = get(u, enc="euc-kr"); show(u.split("/")[-1][:60], st, t, r"20\d\d[.\-]\d\d[.\-]\d\d|\d\d\.\d\d\.\d\d")
import collect as C
C.API_KEY = C.get_key()
r = C.api_get("tsstkAqDecsn.json", {"corp_code": "00126380", "bgn_de": "20240101", "end_de": "20261120"}); print("== dart 자사주 삼성", r.get("status"), len(r.get("list") or []), str((r.get("list") or [None])[0])[:500])
r = C.api_get("list.json", {"bgn_de": "20261001", "end_de": "20261120", "pblntf_detail_ty": "C001", "page_count": 100})
ipo = [x for x in (r.get("list") or []) if "지분증권" in x["report_nm"]][:3]; print("== dart 증권신고서(지분)", [(x["corp_name"], x["corp_code"], x["rcept_no"]) for x in ipo])
if ipo:
    x = ipo[0]
    r = C.api_get("estkRs.json", {"corp_code": x["corp_code"], "bgn_de": "20260101", "end_de": "20261120"}); print("== dart estkRs", r.get("status"), str(r)[:900])
