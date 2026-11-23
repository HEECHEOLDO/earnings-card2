# 시험용 — B 카드 시안용 실제 값 모으기 (출력만, 저장 안 함). 각 결과는 '@@이름 {json}' 한 줄
import os, sys, re, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util
spec = importlib.util.spec_from_file_location("sp", "tools/src_probe.py")
def get(url, data=None, hd=None, enc=None):
    import urllib.request, urllib.parse
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}; h.update(hd or {})
    rq = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=25) as r:
            b = r.read(); return r.status, b.decode(r.headers.get_content_charset() or enc or "utf-8", "replace")
    except Exception as e:
        return "ERR", repr(e)[:300]
def out(name, obj): print("@@" + name, json.dumps(obj, ensure_ascii=False), flush=True)
W = os.environ.get("CODES", "all")
# ---- 출처 더 찾기 (사이드카 · 투자자 · 예탁금)
if W in ("all", "src"):
    for u in ["https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261120&sosok=&page=1",
              "https://m.stock.naver.com/api/index/KOSPI/trend?pageSize=20&page=1&bizdate=20261120",
              "https://m.stock.naver.com/api/index/KOSPI/investor?pageSize=20&page=1",
              "https://m.stock.naver.com/front-api/marketIndex/investorTrend?category=KOSPI",
              "https://m.stock.naver.com/api/home/deposit",
              "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy",
              "https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain",
              "https://kind.krx.co.kr/marketmeasure/marketmeasure.do?method=searchMarketMeasureMain"]:
        st, t = get(u, hd={"Referer": "https://finance.naver.com/"}, enc="euc-kr")
        tx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
        m = re.search(r"\d{2}\.\d{2}\.\d{2}|20\d{6}|사이드카|순매수|예탁금", tx)
        print("== src", st, len(t), u[:90], "|", tx[max(0, (m.start() if m else 0) - 80):(m.start() if m else 0) + 400], flush=True)
    st, t = get("https://kind.krx.co.kr/disclosure/details.do", {"method": "searchDetailsSub", "currentPageSize": "50", "pageIndex": "1", "orderMode": "1", "orderStat": "D", "forward": "details_sub",
                "disclosureType01": "", "reportNm": "사이드카", "fromDate": "2026-01-01", "toDate": "2026-11-23"}, {"Referer": "https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain"})
    print("== kind details 사이드카", st, len(t), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:900], flush=True)
import collect as C
C.API_KEY = C.get_key()
# ---- 공모주 성적표 (올해 코스피·코스닥 신규상장: 증권신고서(지분) 공모가 + 상장 뒤 첫날·지금 종가)
if W in ("all", "ipo"):
    INV = {v["corp_code"]: k for k, v in C.load_corp_map().items()}
    seen, rows = set(), []
    for a, b in (("20250901", "20251231"), ("20260101", "20260430"), ("20260501", "20260831"), ("20260901", "20261120")):
        for pg in range(1, 6):
            r = C.api_get("list.json", {"bgn_de": a, "end_de": b, "pblntf_detail_ty": "C001", "page_count": 100, "page_no": pg})
            L = r.get("list") or []
            for x in L:
                if "지분증권" in x["report_nm"] and "기업인수목적" not in x["corp_name"] and "스팩" not in x["corp_name"] and x["corp_code"] not in seen and not x.get("stock_code"):   # 신고 때 아직 상장 전(종목코드 없음) = 공모주
                    seen.add(x["corp_code"]); rows.append(x)
            if len(L) < 100: break
    print("== ipo 후보", len(rows), flush=True)
    res = []
    for x in rows:
        try:
            r = C.api_get("estkRs.json", {"corp_code": x["corp_code"], "bgn_de": "20250901", "end_de": "20261120"})
            g = {gg["title"]: gg["list"] for gg in (r.get("group") or [])}
            kinds = g.get("증권의종류") or []
            prc = next((k.get("slprc") for k in kinds[::-1] if k.get("stksen") == "보통주" and k.get("slprc") not in (None, "-")), None)
            res.append({"code": INV.get(x["corp_code"]), "name": x["corp_name"], "cls": x["corp_cls"], "rcept": x["rcept_no"], "prc": prc})
        except Exception as e:
            pass
    out("ipo", res)
# ---- 자사주 취득 결정 (올해, 금액 큰 순)
if W in ("all", "buyback"):
    acc = []
    for a, b in (("20260101", "20260331"), ("20260401", "20260630"), ("20260701", "20260930"), ("20261001", "20261120")):
        for pg in range(1, 15):
            r = C.api_get("list.json", {"bgn_de": a, "end_de": b, "pblntf_detail_ty": "B001", "page_count": 100, "page_no": pg})
            L = r.get("list") or []
            acc += [x for x in L if "자기주식취득결정" in x["report_nm"].replace(" ", "") and "정정" not in x["report_nm"]]
            if len(L) < 100: break
    print("== 자사주 결정 공시", len(acc), flush=True)
    by = {}
    for x in acc:
        by.setdefault(x["corp_code"], x)
    res = []
    for cc, x in list(by.items()):
        r = C.api_get("tsstkAqDecsn.json", {"corp_code": cc, "bgn_de": "20260101", "end_de": "20261120"})
        for y in r.get("list") or []:
            try:
                v = int(str(y.get("aqpln_prc_ostk") or "0").replace(",", "").replace("-", "0") or 0) + int(str(y.get("aqpln_prc_estk") or "0").replace(",", "").replace("-", "0") or 0)
            except ValueError:
                v = 0
            res.append({"name": y["corp_name"], "code": x.get("stock_code"), "rcept": y["rcept_no"], "won": v, "purpose": y.get("aq_pp"), "how": y.get("aq_mth")})
    res.sort(key=lambda z: -z["won"])
    out("buyback", res[:40]); print("== 자사주 건수", len(res), "합계", sum(z["won"] for z in res))
# ---- 미국 내부자 매수 (최근 30일, Form 4 의 P 거래) — 우리 미국 종목만
if W in ("all", "form4"):
    import urllib.request
    UA2 = {"User-Agent": "earnings-card research hcdo@example.com"}
    def sj(u):
        rq = urllib.request.Request(u, headers=UA2)
        with urllib.request.urlopen(rq, timeout=30) as r: return r.read().decode("utf-8", "replace")
    idx = json.load(open("data/us/index.json"))["companies"]
    since = "2026-10-21"; res = []
    for c in idx[:460]:
        try:
            cik = int(c.get("cik") or json.load(open("data/us/%s.json" % c["code"])).get("cik"))
            sub = json.loads(sj("https://data.sec.gov/submissions/CIK%010d.json" % cik)); time.sleep(0.12)
            rc = sub["filings"]["recent"]
            for i, f in enumerate(rc["form"]):
                if f != "4" or rc["filingDate"][i] < since: continue
                acc = rc["accessionNumber"][i].replace("-", ""); doc = rc["primaryDocument"][i].split("/")[-1]
                x = sj("https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (cik, acc, doc)); time.sleep(0.12)
                who = re.search(r"<rptOwnerName>([^<]+)", x); ttl = re.search(r"<officerTitle>([^<]+)", x)
                ic = re.search(r"<issuerCik>0*(\d+)", x)
                if not ic or int(ic.group(1)) != cik: continue           # 이 회사가 '보고자'로 다른 회사 주식을 산 건 빼고, 이 회사 주식 거래만
                for t in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", x, re.S):
                    code = re.search(r"<transactionCode>(\w)", t); sh = re.search(r"<transactionShares>\s*<value>([\d.]+)", t); pr = re.search(r"<transactionPricePerShare>\s*<value>([\d.]+)", t)
                    dt = re.search(r"<transactionDate>\s*<value>([\d-]+)", t)
                    if code and code.group(1) in ("P", "S") and sh and pr:
                        res.append({"t": c["code"], "who": who.group(1) if who else "", "title": ttl.group(1) if ttl else "", "code": code.group(1), "usd": round(float(sh.group(1)) * float(pr.group(1))), "date": dt.group(1) if dt else rc["filingDate"][i]})
        except Exception as e:
            print("   form4 오류", c.get("code"), repr(e)[:80])
    P = sorted([z for z in res if z["code"] == "P"], key=lambda z: -z["usd"]); S = sorted([z for z in res if z["code"] == "S"], key=lambda z: -z["usd"])
    out("form4", {"buy": P[:20], "sell": S[:20], "n_buy": len(P), "n_sell": len(S), "since": since})
