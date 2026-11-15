#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'돈의 흐름'(생키) 카드용 손익 세부 — data/flow/{종목코드|티커}.json

매출 → 매출원가 / 매출총이익 → 판관비(미국은 연구개발비·판매관리비·기타 따로) / 영업이익
     → 법인세 / 영업외 손익 / 순이익   — 가장 최근 분기(3개월) 하나.

국내: DART 전체 재무제표 API (fnlttSinglAcntAll, 키 DART_API_KEY) — 분기·반기 보고서의 '3개월' 값,
      가장 최근 것이 사업보고서면 연간 값.
미국: SEC companyfacts (키 없음, SEC_UA) — 같은 분기(frame CY2026Q3 처럼 3개월)로 맞춘 값.
대상: 국내 시총 상위 30 · 미국 시총 상위 30 (보통주)
"""
import json
import os
import sys
import time
from datetime import date

import collect as C
import collect_us as U

OUT = os.path.join("data", "flow")
TODAY = date.today()


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ 국내
KR_IDS = {
    "rev": ["ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"],
    "cogs": ["ifrs-full_CostOfSales"],
    "gross": ["ifrs-full_GrossProfit"],
    "sga": ["dart_TotalSellingGeneralAdministrativeExpenses", "ifrs-full_SellingGeneralAndAdministrativeExpense"],
    "op": ["dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"],
    "pretax": ["ifrs-full_ProfitLossBeforeTax"],
    "tax": ["ifrs-full_IncomeTaxExpenseContinuingOperations"],
    "ni": ["ifrs-full_ProfitLoss"],
}
KR_NM = {"rev": ["매출액", "수익(매출액)", "영업수익", "매출"], "cogs": ["매출원가", "영업비용"], "gross": ["매출총이익"],
         "sga": ["판매비와관리비", "판매비와 관리비"], "op": ["영업이익", "영업이익(손실)"], "pretax": ["법인세비용차감전순이익", "법인세비용차감전순이익(손실)"],
         "tax": ["법인세비용", "법인세비용(수익)"], "ni": ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익", "분기순이익(손실)", "반기순이익(손실)"]}


def kr_pick(rows, k, quarter):
    rows = [r for r in rows if r.get("sj_div") in ("IS", "CIS")]
    for aid in KR_IDS[k]:
        for r in rows:
            if r.get("account_id") == aid:
                v = num(r.get("thstrm_amount"))
                if v is not None:
                    return v
    for nm in KR_NM[k]:
        for r in rows:
            if (r.get("account_nm") or "").replace(" ", "") == nm.replace(" ", ""):
                v = num(r.get("thstrm_amount"))
                if v is not None:
                    return v
    return None


def kr_one(code, corp):
    y = TODAY.year
    for yy, rc, q in ((y, "11014", 3), (y, "11012", 2), (y, "11013", 1), (y - 1, "11011", 0), (y - 1, "11014", 3)):
        rows = C.fetch_fs(corp, yy, rc)
        if not rows:
            continue
        d = {k: kr_pick(rows, k, q) for k in KR_IDS}
        if not d["rev"] or d["op"] is None:
            continue
        if d["gross"] is None and d["cogs"] is not None:
            d["gross"] = d["rev"] - d["cogs"]
        if d["cogs"] is None and d["gross"] is not None:
            d["cogs"] = d["rev"] - d["gross"]
        e = 1e8                                    # 원 → 억원
        out = {k: (round(v / e, 1) if v is not None else None) for k, v in d.items()}
        out.update({"y": yy, "q": q, "unit": "억원", "period": "'%s년 %s" % (str(yy)[2:], "연간" if q == 0 else "%d분기" % q)})
        return out
    return None


# ------------------------------------------------------------------ 미국
US_TAGS = {
    "rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"],
    "gross": ["GrossProfit"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "sm": ["SellingAndMarketingExpense"],
    "ga": ["GeneralAndAdministrativeExpense"],
    "opex": ["OperatingExpenses", "CostsAndExpenses"],
    "op": ["OperatingIncomeLoss"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "ni": ["NetIncomeLoss", "ProfitLoss"],
}


def us_frames(facts, tags):
    """태그들 중 3개월 값(frame CYyyyyQn)을 {frame: 값} 으로"""
    g = (facts.get("facts") or {}).get("us-gaap") or {}
    out = {}
    for t in tags:
        for u in ((g.get(t) or {}).get("units") or {}).get("USD", []):
            fr = u.get("frame") or ""
            if len(fr) == 8 and fr.startswith("CY") and fr[6] == "Q" and fr not in out:
                out[fr] = u.get("val")
    return out


def us_one(t, cik):
    facts = U.get_json(U.SEC_FACTS % str(cik).zfill(10))
    if not facts:
        return None
    rv = us_frames(facts, US_TAGS["rev"])
    if not rv:
        return None
    fr = max(rv)
    d = {"rev": rv[fr]}
    for k, tags in US_TAGS.items():
        if k != "rev":
            d[k] = us_frames(facts, tags).get(fr)
    if d.get("gross") is None and d.get("cogs") is not None:
        d["gross"] = d["rev"] - d["cogs"]
    if d.get("cogs") is None and d.get("gross") is not None:
        d["cogs"] = d["rev"] - d["gross"]
    if d.get("op") is None or d.get("ni") is None:
        return None
    m = 1e6                                         # 달러 → 백만 달러
    out = {k: (round(v / m, 1) if isinstance(v, (int, float)) else None) for k, v in d.items()}
    out.update({"y": int(fr[2:6]), "q": int(fr[7]), "unit": "백만달러", "period": "'%s년 %s분기 (달력 기준)" % (fr[4:6], fr[7]), "frame": fr})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    mc = json.load(open("data/mcap.json", encoding="utf-8"))["stocks"]
    mu = json.load(open("data/mcap_us.json", encoding="utf-8"))["stocks"]
    kr = [c for c in sorted(mc, key=lambda c: -(mc[c].get("c") or 0)) if c.endswith("0")][:30]
    us = sorted([t for t in mu if mu[t].get("c")], key=lambda t: -mu[t]["c"])[:30]
    idx = {}
    if "--us-only" not in sys.argv:
        C.API_KEY = C.get_key()
        cmap = C.load_corp_map()
        for code in kr:
            info = cmap.get(code)
            if not info:
                continue
            try:
                d = kr_one(code, info["corp_code"])
            except Exception as e:                  # noqa: BLE001
                print("  !! %s %s" % (code, e))
                d = None
            if d:
                d.update({"code": code, "name": mc[code].get("n"), "market": "KR", "updated": TODAY.isoformat()})
                json.dump(d, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
                idx[code] = {"n": d["name"], "m": "KR", "p": d["period"]}
                print("  ok %s %s %s 매출 %s 원가 %s 판관비 %s 영업 %s 순 %s" % (code, d["name"], d["period"], d["rev"], d["cogs"], d["sga"], d["op"], d["ni"]))
    for t in us:
        cik = None
        p = os.path.join("data", "us", t + ".json")
        if os.path.exists(p):
            cik = json.load(open(p, encoding="utf-8")).get("cik")
        if not cik:
            continue
        try:
            d = us_one(t, cik)
        except Exception as e:                      # noqa: BLE001
            print("  !! %s %s" % (t, e))
            d = None
        time.sleep(0.15)
        if d:
            d.update({"code": t, "name": mu[t].get("n"), "market": "US", "updated": TODAY.isoformat()})
            json.dump(d, open(os.path.join(OUT, t + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            idx[t] = {"n": d["name"], "m": "US", "p": d["period"]}
            print("  ok %s %s 매출 %s 원가 %s R&D %s SG&A %s 영업 %s 순 %s" % (t, d["period"], d["rev"], d["cogs"], d.get("rnd"), d.get("sga"), d["op"], d["ni"]))
    old = {}
    ip = os.path.join(OUT, "index.json")
    if os.path.exists(ip):
        old = json.load(open(ip, encoding="utf-8")).get("items", {})
    old.update(idx)
    json.dump({"updated": TODAY.isoformat(), "items": old}, open(ip, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("== 끝: %d곳" % len(idx))


if __name__ == "__main__":
    main()
