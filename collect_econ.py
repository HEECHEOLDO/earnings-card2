#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""경제 지표 수집 — 인포그래픽 탭의 '경제·생활' 카드용. data/econ/ 에 쓴다.

출처 (모두 GitHub 자동 작업에서 받는다)
  1) 시장 가격 (CNBC 차트): 금·은·구리·유가·천연가스·비트코인·달러지수·국채 금리·환율 — 일별 1년 + 주별 5년
  2) 거시 지표 (미국 연준 FRED, 키 없음): 미국 기준금리·물가·실업률·고용·모기지 금리·휘발유 값,
     한국 물가·실업률·금리·수출(OECD 자료) — 월별
  3) 품목별 수출 (관세청 수출입실적, 공공데이터포털 키 DATA_GO_KEY): 화장품·반도체·자동차·라면·김 등 — 월별
  4) (선택) 한국은행 ECOS (키 ECOS_KEY 가 있을 때만): 기준금리·소비자물가·가계대출

파일: data/econ/{id}.json  {"id","name","unit","freq","src","d":[[날짜, 값, …]], "updated"}
      data/econ/index.json  어떤 지표가 있고 마지막 값이 언제인지, 실패한 건 왜인지
사용: python3 collect_econ.py            전체
      python3 collect_econ.py fred trade 일부만 (market · fred · trade · ecos)
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "econ")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TODAY = date.today()
STATUS = {}


def get(url, tries=3, timeout=40):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:                    # noqa: BLE001
            err = str(e)
            time.sleep(2 + i * 3)
    print("  !! %s — %s" % (safe(url), safe(err)[:120]))
    return None


def safe(t):
    """로그에 키가 찍히지 않게 — serviceKey·api_key·ECOS 경로의 키를 가린다"""
    t = re.sub(r"(serviceKey|api_key|key)=[^&\s]+", r"\1=***", str(t))
    return re.sub(r"(StatisticSearch/)[^/]+", r"\1***", t)[:160]


def save(id_, name, unit, freq, src, rows, **extra):
    if not rows:
        STATUS[id_] = {"ok": False, "name": name, "why": "자료 없음"}
        return
    os.makedirs(OUT, exist_ok=True)
    rows = sorted({r[0]: r for r in rows}.values())
    obj = {"id": id_, "name": name, "unit": unit, "freq": freq, "src": src, "updated": TODAY.isoformat(), "d": rows}
    obj.update(extra)
    with open(os.path.join(OUT, id_ + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    STATUS[id_] = {"ok": True, "name": name, "unit": unit, "freq": freq, "src": src, "last": rows[-1][0], "n": len(rows)}
    print("  ok %-14s %5d개 · 마지막 %s = %s" % (id_, len(rows), rows[-1][0], rows[-1][1]))


# ------------------------------------------------------------------ 1) 시장 가격 (CNBC)
MARKET = [  # id, CNBC 기호, 이름, 단위
    ("gold", "@GC.1", "금 (온스당)", "달러"), ("silver", "@SI.1", "은 (온스당)", "달러"), ("copper", "@HG.1", "구리 (파운드당)", "달러"),
    ("wti", "@CL.1", "국제유가 WTI (배럴당)", "달러"), ("brent", "@LCO.1", "브렌트유 (배럴당)", "달러"), ("natgas", "@NG.1", "천연가스", "달러"),
    ("btc", "BTC.CM=", "비트코인", "달러"), ("eth", "ETH.CM=", "이더리움", "달러"),
    ("dxy", ".DXY", "달러지수", "pt"), ("vix", ".VIX", "공포지수 VIX", "pt"),
    ("us10y", "US10Y", "미국 국채 10년", "%"), ("us2y", "US2Y", "미국 국채 2년", "%"), ("kr10y", "KR10Y", "한국 국채 10년", "%"),
    ("kr3y", "KR3Y", "한국 국채 3년", "%"), ("jp10y", "JP10Y", "일본 국채 10년", "%"),
    ("usdkrw", "KRW=", "원·달러", "원"), ("jpykrw", "JPYKRW=", "원·엔 (1엔)", "원"), ("eurkrw", "EURKRW=", "원·유로", "원"), ("cnykrw", "CNYKRW=", "원·위안", "원"),
]


def market():
    from collect_chart_us import cnbc_bars
    for id_, sym, name, unit in MARKET:
        try:
            d1 = [tuple(x) for x in (cnbc_bars(sym, "1Y") or [])]
            w5 = [tuple(x) for x in (cnbc_bars(sym, "5Y") or [])]
        except Exception as e:                    # noqa: BLE001
            STATUS[id_] = {"ok": False, "name": name, "why": str(e)[:100]}
            continue
        m = {}
        for a, b in w5:                           # 주별(5년) 위에 일별(1년)을 덮는다
            if not d1 or a < d1[0][0]:
                m[a] = b
        for a, b in d1:
            m[a] = b
        rows = [[a, round(b, 4)] for a, b in sorted(m.items())]
        save(id_, name, unit, "D", "CNBC", rows)


# ------------------------------------------------------------------ 2) FRED (키 없는 CSV)
FRED = [  # id, 시리즈, 이름, 단위
    ("us_rate", "DFEDTARU", "미국 기준금리 (상단)", "%"), ("us_cpi", "CPIAUCSL", "미국 소비자물가", "지수"), ("us_core", "CPILFESL", "미국 근원물가", "지수"),
    ("us_unemp", "UNRATE", "미국 실업률", "%"), ("us_jobs", "PAYEMS", "미국 비농업 고용", "천 명"), ("us_mort", "MORTGAGE30US", "미국 30년 주택담보대출 금리", "%"),
    ("us_gas", "GASREGW", "미국 휘발유 (갤런당)", "달러"), ("us_sent", "UMCSENT", "미국 소비자심리", "pt"), ("us_m2", "M2SL", "미국 통화량 M2", "십억 달러"),
    ("us_home", "CSUSHPINSA", "미국 집값 (케이스-실러)", "지수"), ("us_retail", "RSAFS", "미국 소매판매", "백만 달러"),
    ("us_cars", "TOTALSA", "미국 자동차 판매 (연율)", "백만 대"),
    ("kr_cpi", "KORCPIALLMINMEI", "한국 소비자물가 (OECD)", "지수"), ("kr_unemp", "LRHUTTTTKRM156S", "한국 실업률 (OECD)", "%"),
    ("kr_10y_m", "IRLTLT01KRM156N", "한국 국채 10년 (월평균)", "%"), ("kr_3m", "IR3TIB01KRM156N", "한국 3개월 금리", "%"),
    ("kr_exp", "XTEXVA01KRM664S", "한국 수출액 (OECD, 계절조정)", "달러"), ("kr_imp", "XTIMVA01KRM664S", "한국 수입액 (OECD, 계절조정)", "달러"),
    ("kr_house", "QKRR628BIS", "한국 집값 (BIS 실질)", "지수"), ("kr_prod", "KORPROINDMISMEI", "한국 산업생산", "지수"),
]


def fred():
    t0 = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE&cosd=2024-01-01", tries=1, timeout=90)
    print("  FRED 점검 응답:", (t0 or "없음")[:120].replace("\n", " | "))
    if not t0:
        for id_, sid, name, unit in FRED:
            STATUS[id_] = {"ok": False, "name": name, "why": "FRED 응답 없음 (GitHub 서버에서 막힘)"}
        bls()
        nyfed()
        return
    for id_, sid, name, unit in FRED:
        t = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid + "&cosd=2005-01-01", tries=2, timeout=30)
        if not t or "DATE" not in t.upper()[:40] and "observation_date" not in t[:40]:
            STATUS[id_] = {"ok": False, "name": name, "why": "FRED 응답 없음"}
            continue
        rows = []
        for r in csv.reader(io.StringIO(t)):
            if len(r) < 2 or not re.match(r"\d{4}-\d\d-\d\d", r[0]):
                continue
            try:
                v = float(r[1])
            except ValueError:
                continue
            rows.append([int(r[0].replace("-", "")), v])
        save(id_, name, unit, "M" if sid not in ("DFEDTARU", "MORTGAGE30US", "GASREGW") else "W", "FRED · " + sid, rows)


# ------------------------------------------------------------------ 2-1) FRED 가 막힐 때: 미국 노동통계국(BLS) · 뉴욕 연준 (키 없음)
BLS = [("us_cpi", "CUUR0000SA0", "미국 소비자물가", "지수"), ("us_core", "CUUR0000SA0L1E", "미국 근원물가", "지수"),
       ("us_unemp", "LNS14000000", "미국 실업률", "%"), ("us_jobs", "CES0000000001", "미국 비농업 고용", "천 명"),
       ("us_gas", "APU000074714", "미국 휘발유 (갤런당)", "달러")]


def bls():
    y1 = TODAY.year
    for y0 in (y1 - 9, y1 - 19):                 # v1 은 한 번에 10년까지
        pass
    acc = {k[0]: [] for k in BLS}
    for a, b in ((y1 - 9, y1), (y1 - 19, y1 - 10)):
        body = json.dumps({"seriesid": [k[1] for k in BLS], "startyear": str(a), "endyear": str(b)}).encode()
        try:
            req = urllib.request.Request("https://api.bls.gov/publicAPI/v1/timeseries/data/", data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": UA})
            j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
        except Exception as e:                    # noqa: BLE001
            print("  !! BLS", safe(e))
            continue
        for ser in (j.get("Results") or {}).get("series", []):
            k = [x for x in BLS if x[1] == ser.get("seriesID")]
            if not k:
                continue
            for r in ser.get("data", []):
                if not r.get("period", "").startswith("M") or r["period"] == "M13":
                    continue
                try:
                    acc[k[0][0]].append([int(r["year"]) * 10000 + int(r["period"][1:]) * 100 + 1, float(r["value"])])
                except ValueError:
                    pass
        time.sleep(1)
    for id_, sid, name, unit in BLS:
        save(id_, name, unit, "M", "미국 노동통계국 BLS · " + sid, acc[id_])


def nyfed():
    t = get("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate=2015-01-01&endDate=" + TODAY.isoformat(), tries=2, timeout=60)
    rows = []
    try:
        for r in json.loads(t)["refRates"]:
            rows.append([int(r["effectiveDate"].replace("-", "")), float(r.get("targetRateTo") or r["percentRate"])])
    except Exception:                             # noqa: BLE001
        pass
    save("us_rate", "미국 기준금리 (상단)", "%", "D", "뉴욕 연준 · EFFR 목표 범위", rows)


# ------------------------------------------------------------------ 3) 관세청 품목별 수출입 (공공데이터포털)
TRADE = [  # id, HS, 이름
    ("t_semi", "8542", "반도체"), ("t_car", "8703", "승용차"), ("t_parts", "8708", "자동차 부품"), ("t_batt", "8507", "2차전지"),
    ("t_ship", "8901", "선박"), ("t_cosm", "3304", "화장품"), ("t_ramen", "190230", "라면"), ("t_laver", "200899", "조미김 등"),
    ("t_gim", "121221", "김 (마른김)"), ("t_soju", "220890", "소주 등 증류주"), ("t_pharm", "3004", "의약품"), ("t_phone", "851713", "스마트폰"),
    ("t_oil", "2710", "석유제품"), ("t_steel", "7208", "철강판"), ("t_display", "8524", "디스플레이"), ("t_comp", "8471", "컴퓨터"),
    ("t_bio", "3002", "백신·바이오 의약품"), ("t_tire", "4011", "타이어"), ("t_food_snack", "1905", "과자·빵"), ("t_beauty_dev", "8543", "미용기기 등"),
]


def key_datago():
    k = os.environ.get("DATA_GO_KEY", "").strip()
    if not k and os.path.exists("datago_key.txt"):
        k = open("datago_key.txt").read().strip()
    return k


def trade_call(key, hs, a, b):
    q = urllib.parse.urlencode({"serviceKey": urllib.parse.unquote(key), "strtYymm": a, "endYymm": b, "hsSgn": hs})
    for base in ("https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList", "http://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"):
        t = get(base + "?" + q, tries=1, timeout=25)
        if t and "<" in t:
            return t
    return None


def trade():
    key = key_datago()
    if not key:
        for id_, hs, name in TRADE:
            STATUS[id_] = {"ok": False, "name": name + " 수출", "why": "DATA_GO_KEY 없음"}
        return
    y1 = TODAY.year
    t = trade_call(key, "3304", "%d01" % (y1 - 1), "%d12" % (y1 - 1))   # 먼저 한 번 열어 본다 — 막혀 있으면 다 건너뛴다
    print("  관세청 점검 응답:", safe(re.sub(r"\s+", " ", (t or "없음"))[:300]))
    if not t or "<item>" not in t:
        why = "403 — 공공데이터포털에서 '관세청_품목별 수출입실적' 활용신청 필요" if not t else safe(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))[:150]
        for id_, hs, name in TRADE:
            STATUS[id_] = {"ok": False, "name": name + " 수출", "why": "관세청 API: " + why}
        return
    for id_, hs, name in TRADE:
        mon = {}
        why = ""
        for y in range(2015, y1 + 1):
            t = trade_call(key, hs, "%d01" % y, "%d12" % y if y < y1 else TODAY.strftime("%Y%m"))
            if not t:
                why = "응답 없음"
                continue
            if "SERVICE_KEY" in t or "<returnAuthMsg>" in t or "LIMITED" in t:
                why = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:120]
                break
            try:
                root = ET.fromstring(t)
            except ET.ParseError:
                why = "XML 오류"
                continue
            for it in root.iter("item"):
                g = lambda k: (it.findtext(k) or "").strip()  # noqa: E731
                ym = g("year").replace(".", "")
                if not re.match(r"^\d{6}$", ym):          # '총계' 줄은 건너뛴다
                    continue
                try:
                    ex, im = float(g("expDlr") or 0), float(g("impDlr") or 0)
                    ew = float(g("expWgt") or 0)
                except ValueError:
                    continue
                k = int(ym)
                p = mon.get(k, [k, 0.0, 0.0, 0.0])
                p[1] += ex; p[2] += im; p[3] += ew      # 세부 HS 여러 줄이면 더한다
                mon[k] = p
            time.sleep(0.3)
        rows = [[k, round(v[1]), round(v[2]), round(v[3])] for k, v in sorted(mon.items())]
        if rows:
            save(id_, name + " 수출", "달러", "M", "관세청 수출입실적 · HS " + hs, rows, hs=hs, cols=["월", "수출액", "수입액", "수출중량kg"])
        else:
            STATUS[id_] = {"ok": False, "name": name + " 수출", "why": why or "자료 없음"}
        if why and "SERVICE_KEY" in why:
            print("  !! 관세청 API 키 승인이 안 된 것 같습니다:", safe(why))
            for jd, h2, n2 in TRADE:
                STATUS.setdefault(jd, {"ok": False, "name": n2 + " 수출", "why": why})
            return


# ------------------------------------------------------------------ 4) 한국은행 ECOS (키가 있을 때만)
ECOS = [  # id, 통계표, 주기, 항목, 이름, 단위
    ("kr_base", "722Y001", "M", "0101000", "한국은행 기준금리", "%"),
    ("kr_cpi_e", "901Y009", "M", "0", "한국 소비자물가지수", "지수"),
    ("kr_hhdebt", "151Y002", "M", "1110000", "예금은행 가계대출", "십억 원"),
]


def ecos():
    key = os.environ.get("ECOS_KEY", "").strip()
    if not key:
        print("  ECOS_KEY 없음 — 건너뜀")
        return
    for id_, tb, fq, item, name, unit in ECOS:
        url = "https://ecos.bok.or.kr/api/StatisticSearch/%s/json/kr/1/1000/%s/%s/200501/%s/%s" % (key, tb, fq, TODAY.strftime("%Y%m"), item)
        t = get(url)
        rows = []
        try:
            for r in json.loads(t)["StatisticSearch"]["row"]:
                rows.append([int(r["TIME"]), float(r["DATA_VALUE"])])
        except Exception:                         # noqa: BLE001
            STATUS[id_] = {"ok": False, "name": name, "why": safe((t or "응답 없음")[:120])}
            continue
        save(id_, name, unit, fq, "한국은행 ECOS · " + tb, rows)


def main():
    sys.stdout.reconfigure(line_buffering=True)
    parts = sys.argv[1:] or ["market", "fred", "trade", "ecos"]
    os.makedirs(OUT, exist_ok=True)
    old = {}
    p = os.path.join(OUT, "index.json")
    if os.path.exists(p):
        old = json.load(open(p, encoding="utf-8")).get("items", {})
    for part in parts:
        print("==", part)
        try:
            {"market": market, "fred": fred, "trade": trade, "ecos": ecos}[part]()
        except Exception as e:                    # noqa: BLE001 — 한 부분이 죽어도 나머지는 남긴다
            print("  !! %s 실패: %s" % (part, e))
    items = dict(old)
    for k, v in STATUS.items():                  # 이번에 실패했어도 예전 파일이 있으면 그건 살린다
        if v.get("ok") or k not in old or not old[k].get("ok"):
            items[k] = v
        else:
            items[k] = dict(old[k], stale=True, why=v.get("why"))
    json.dump({"updated": TODAY.isoformat(), "items": items}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in items.values() if v.get("ok"))
    print("== 끝: %d개 성공 / %d개" % (ok, len(items)))


if __name__ == "__main__":
    main()
