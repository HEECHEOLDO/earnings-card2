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
import flow_xbrl as FX
import xbrl_dims as XD
import re

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


# ------------------------------------------------------------------ 공시 원본(XBRL): 3개월 손익 + 매출 종류
VER = 6                                            # 계산 방식이 바뀌면 올려서 다시 계산


def kr_xbrl(corp, old=None):
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "%d0101" % (TODAY.year - 1), "pblntf_ty": "A", "page_count": 30})
    rows = [r for r in (res or {}).get("list", []) if re.search(r"(분기|반기|사업)보고서", r.get("report_nm", ""))]
    rows.sort(key=lambda r: r["rcept_dt"], reverse=True)
    if rows and old and old.get("src") == rows[0]["rcept_no"] and old.get("ver") == VER:
        return "SAME"                               # 새 보고서가 없으면 그대로
    for r0 in rows[:3]:
        nm = r0["report_nm"]
        rc = "11011" if "사업" in nm else "11012" if "반기" in nm else "11014" if ".09" in nm else "11013"
        blob = C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": rc}, raw=True)
        if not blob or blob[:2] != b"PK":
            continue
        files = XD.unzip(blob)
        inst = [n for n in files if n.endswith(".xbrl")]
        lab = [n for n in files if "lab-ko" in n]
        cal = [n for n in files if n.endswith("_cal.xml") or "cal" in n.rsplit("/", 1)[-1]]
        if not inst:
            continue
        v = FX.from_instance(files[inst[0]], files[lab[0]] if lab else "", us=False, caltext=files[cal[0]] if cal else "")
        if v:
            v["report"] = nm
            v["src"] = r0["rcept_no"]
            if not v.get("items") and v.get("sga"):
                try:
                    mix = None
                    for a in [r for r in rows if "사업보고서" in r["report_nm"]][:1]:
                        fa = files if a is r0 else XD.unzip(C.api_get("fnlttXbrl.xml", {"rcept_no": a["rcept_no"], "reprt_code": "11011"}, raw=True) or b"")
                        ia = [n for n in fa if n.endswith(".xbrl")]
                        mix = FX.kr_sga_mix(fa[ia[0]]) if ia else None
                    if mix and "mix" in mix:
                        v["items"] = FX.split_sga(v["sga"], mix)
                        v["items_from"] = mix["year"]
                    else:
                        v["mix_err"] = (mix or {}).get("err", "사업보고서 못 찾음")
                except Exception as e:              # noqa: BLE001
                    v["mix_err"] = str(e)[:120]
            return v
    return None


def us_xbrl(cik, old=None):
    sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))
    if not sub:
        return None
    rc = sub["filings"]["recent"]
    for i, f in enumerate(rc["form"]):
        if f not in ("10-Q", "10-K"):
            continue
        acc = rc["accessionNumber"][i]
        if old and old.get("src") == acc and old.get("ver") == VER:
            return "SAME"
        base = U.SEC_ARCH % (int(cik), acc.replace("-", ""))
        idx = U.get_json(base + "index.json")
        names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
        inst = [n for n in names if n.endswith("_htm.xml")]
        lab = [n for n in names if n.endswith("_lab.xml")]
        cal = [n for n in names if n.endswith("_cal.xml")]
        if not inst:
            FX.WHY = "공시에 XBRL 파일 없음 %s" % acc
            return None
        raw = U.get(base + inst[0])
        lr = U.get(base + lab[0]) if lab else None
        cr = U.get(base + cal[0]) if cal else None
        if not raw:
            FX.WHY = "XBRL 내려받기 실패"
            return None
        v = FX.from_instance(raw.decode("utf-8", "replace"), lr.decode("utf-8", "replace") if lr else "", us=True,
                             caltext=cr.decode("utf-8", "replace") if cr else "")
        if v:
            v["report"] = f + " " + rc["reportDate"][i]
            v["src"] = acc
        return v
    return None


def usable(code):
    p = os.path.join(OUT, code + ".json")
    if not os.path.exists(p):
        return False
    d = json.load(open(p, encoding="utf-8"))
    rev, op = d.get("rev"), d.get("op")
    if not rev or rev <= 0 or op is None or op >= rev:
        return False
    if not d.get("start") and d.get("y") and d.get("q"):          # 예전 방식(분기 번호만 있는 자료)
        d["start"], d["end"] = "%d-%02d-01" % (d["y"], d["q"] * 3 - 2), "%d-%02d-28" % (d["y"], d["q"] * 3)
    if not d.get("start") or not d.get("end"):
        return False
    gross = d.get("gross") if d.get("gross") is not None else rev - (d.get("cogs") or 0)
    if gross - op < 0:
        return False
    days = (date.fromisoformat(d["end"]) - date.fromisoformat(d["start"])).days
    if not (80 <= days <= 100 or 350 <= days <= 380):
        return False
    return (TODAY - date.fromisoformat(d["end"])).days < 200            # 분기 끝 + 제출 기한(45~90일)보다 오래되면 뺌


def scaled(v, k):
    out = {}
    for a, b in v.items():
        if isinstance(b, (int, float)):
            out[a] = round(b / k, 1)
        elif a in ("segs", "items"):
            out[a] = [[n, round(x / k, 1)] for n, x in b]
        else:
            out[a] = b
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
                fp = os.path.join(OUT, code + ".json")
                old = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else None
                x = kr_xbrl(info["corp_code"], old)
                if x == "SAME":
                    idx[code] = {"n": old["name"], "m": "KR", "p": old["period"]}
                    print("  = %s 그대로" % code)
                    continue
                d = scaled(x, 1e8) if x else None
                if d:
                    d["ver"] = VER
                    d["unit"] = "억원"
                else:
                    d = kr_one(code, info["corp_code"])
            except Exception as e:                  # noqa: BLE001
                print("  !! %s %s" % (code, e))
                d = None
            if d:
                d.update({"code": code, "name": mc[code].get("n"), "market": "KR", "updated": TODAY.isoformat()})
                json.dump(d, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
                idx[code] = {"n": d["name"], "m": "KR", "p": d["period"]}
                print("  ok %s %s %s 매출 %s 원가 %s 판관비 %s 영업 %s 순 %s 부문 %s" % (code, d.get("name"), d.get("period"), d.get("rev"), d.get("cogs"), d.get("sga"), d.get("op"), d.get("ni"), d.get("segs")))
    for t in us:
        cik = None
        p = os.path.join("data", "us", t + ".json")
        if os.path.exists(p):
            cik = json.load(open(p, encoding="utf-8")).get("cik")
        if not cik:
            continue
        try:
            fp = os.path.join(OUT, t + ".json")
            old = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else None
            FX.WHY = ""
            try:
                x = us_xbrl(cik, old)
            except Exception as e:                  # noqa: BLE001
                x, FX.WHY = None, "오류 %s" % e
            if x == "SAME":
                idx[t] = {"n": old["name"], "m": "US", "p": old["period"]}
                print("  = %s 그대로" % t)
                continue
            d = scaled(x, 1e6) if x else None
            if d:
                d["ver"] = VER
                d["unit"] = "백만달러"
            else:
                d = us_one(t, cik)
                if d:
                    d["xbrl_err"] = FX.WHY or "까닭 모름"
        except Exception as e:                      # noqa: BLE001
            print("  !! %s %s" % (t, e))
            d = None
        time.sleep(0.15)
        if d:
            d.update({"code": t, "name": mu[t].get("n"), "market": "US", "updated": TODAY.isoformat()})
            json.dump(d, open(os.path.join(OUT, t + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            idx[t] = {"n": d["name"], "m": "US", "p": d["period"]}
            print("  ok %s %s 매출 %s 원가 %s R&D %s SG&A %s 영업 %s 순 %s" % (t, d.get("period"), d.get("rev"), d.get("cogs"), d.get("rnd"), d.get("sga"), d.get("op"), d.get("ni")))
    old = {}
    ip = os.path.join(OUT, "index.json")
    if os.path.exists(ip):
        old = json.load(open(ip, encoding="utf-8")).get("items", {})
    old.update(idx)
    old = {c: v for c, v in old.items() if usable(c)}       # 이상한 자료(누적 기간·오래된 것·영업이익>매출)는 카드에서 뺌
    json.dump({"updated": TODAY.isoformat(), "items": old}, open(ip, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("== 끝: %d곳" % len(idx))


if __name__ == "__main__":
    main()
