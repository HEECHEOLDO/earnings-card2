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
from datetime import date, datetime, timedelta

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


US_SPAN = {}                                       # frame → (시작일, 끝일) — 카드 아래 기간을 실제 달로 적으려고


def us_frames(facts, tags):
    """태그들 중 3개월 값(frame CYyyyyQn)을 {frame: 값} 으로"""
    g = (facts.get("facts") or {}).get("us-gaap") or {}
    out = {}
    for t in tags:
        for u in ((g.get(t) or {}).get("units") or {}).get("USD", []):
            fr = u.get("frame") or ""
            if len(fr) == 8 and fr.startswith("CY") and fr[6] == "Q" and fr not in out:
                out[fr] = u.get("val")
                if u.get("start") and u.get("end"):
                    US_SPAN.setdefault(fr, (u["start"], u["end"]))
    return out


def us_one(t, cik):
    facts = U.get_json(U.SEC_FACTS % str(cik).zfill(10))
    if not facts:
        return None
    US_SPAN.clear()
    rv = us_frames(facts, US_TAGS["rev"])
    if not rv:
        return None
    fr = max(rv)
    d = {"rev": rv[fr]}
    span = US_SPAN.get(fr)
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
    if span:
        out.update({"start": span[0], "end": span[1]})      # 실제 기간 (회계연도가 다른 회사는 달력 분기와 어긋난다)
    return out


# ------------------------------------------------------------------ 공시 원본(XBRL): 3개월 손익 + 매출 종류
DOC_VER = 2                                        # 국내: 보고서 원문 대체(매출 구분·판관비 세부) — 세부가 없던 회사만 다시
US_VER = 2                                         # 미국 영업비용 세부 읽는 법이 바뀌면 올림 — 세부가 없던 미국 회사만 다시
UL_VER = 3                                         # 비상장(감사보고서) 읽는 법이 바뀌면 올림 — 비상장만 다시
VER = 9                                            # 계산 방식이 바뀌면 올려서 다시 계산


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
            fa, ia = None, []
            if (not v.get("items") and v.get("sga")) or not v.get("segs"):
                for a in [r for r in rows if "사업보고서" in r["report_nm"]][:1]:     # 최근 사업보고서(연간) 한 번만 받는다
                    try:
                        fa = files if a is r0 else XD.unzip(C.api_get("fnlttXbrl.xml", {"rcept_no": a["rcept_no"], "reprt_code": "11011"}, raw=True) or b"")
                    except Exception:               # noqa: BLE001
                        fa = None
                    ia = [n for n in (fa or {}) if n.endswith(".xbrl")]
            if not v.get("segs") and ia:          # 분기 보고서에 매출 종류가 없으면 연간 보고서의 비중으로 나눈다
                try:
                    la = [n for n in fa if "lab-ko" in n]
                    av = FX.from_instance(fa[ia[0]], fa[la[0]] if la else "", us=False)
                    if av and av.get("segs"):
                        k = v["rev"] / sum(x for _, x in av["segs"])
                        v["segs"] = [[n, x * k] for n, x in av["segs"]]
                        v["seg_note"] = "매출 종류는 '%s년 연간 비중" % av["end"][2:4]
                        if av.get("seg_kind"):
                            v["seg_kind"] = av["seg_kind"]
                except Exception:                   # noqa: BLE001
                    pass
            if not v.get("items") and v.get("sga"):
                try:
                    mix = FX.kr_sga_mix(fa[ia[0]]) if ia else None
                    if mix and "mix" in mix:
                        v["items"] = FX.split_sga(v["sga"], mix)
                        v["items_from"] = mix["year"]
                    else:
                        v["mix_err"] = (mix or {}).get("err", "사업보고서 못 찾음")
                except Exception as e:              # noqa: BLE001
                    v["mix_err"] = str(e)[:120]
            if (not v.get("items") and v.get("sga")) or not v.get("segs"):
                try:                                # XBRL 에 세부가 없는 작은 회사 — 보고서 원문(주석 표)에서
                    doc_fallback(v, r0, [r for r in rows if "사업보고서" in r["report_nm"]][:1], fa, ia)
                except Exception as e:              # noqa: BLE001
                    v["doc_err"] = str(e)[:120]
            return v
    return None


def doc_fallback(v, r0, annual, fa, ia):
    """보고서 원문의 주석 표 — 합계가 손익계산서 숫자와 맞는 표만 쓴다.
    1) 이번 분기 보고서 원문에서 이번 분기 숫자와 맞는 표 → 그대로
    2) 없으면 최근 사업보고서 원문에서 연간 숫자와 맞는 표 → 그 비중으로 이번 분기를 나눈다"""
    import flow_audit as FA
    import probe_audit as P
    SGA_H = re.compile(r"^(판매비와관리비|판매비와일반관리비|판매관리비)(합계|계)?$")
    REV_H = re.compile(r"^(매출액|영업수익|수익|매출)(합계|계)?$")
    # 현금흐름표 조정 표 같은 엉뚱한 표가 합만 우연히 맞는 일을 막는다 — 판관비 계정 같지 않은 줄은 빼고(그러면 합이 안 맞아 탈락)
    BAD = re.compile(r"조정|증\s*\(?감|증가|감소|평가|처분|채무|채권|자산|부채|현금|손상차손|외화|이자|배당|법인세|지분|파생|환산|환차|투자|차입|매출액|매출원가")
    SGA_DROP = re.compile(FA.SGA_DROP.pattern + "|" + BAD.pattern)
    SGA_OK = re.compile(r"급여|상여|퇴직|복리|감가|상각|수수료|광고|판매촉진|운반|임차|세금|공과|여비|교통|통신|소모품|접대|교육|보험|연구|개발|대손|차량|수선|용역|수도|광열|전력|도서|회의|포장|보관|견본|판매|인건|사용권|임금|경상")
    def sga_ok(det):
        s = sum(x for _, x in det)
        return det and sum(x for n, x in det if SGA_OK.search(n)) >= s * 0.6
    want_i, want_s = not v.get("items") and v.get("sga"), not v.get("segs")
    doc = P.fetch_doc(r0["rcept_no"])
    tabs = FA._tables(doc) if doc else []
    if want_i and tabs:
        det = FA._breakdown(tabs, v["sga"], SGA_H, FA.SGA_KEEP, SGA_DROP, min_rows=4)
        it = FA._group(det, v["sga"], "기타 판관비") if sga_ok(det) else []
        if it:
            v["items"], v["items_from"], want_i = it, "본문", False
    if want_s and tabs:
        rv = FA._breakdown(tabs, v["rev"], REV_H, FA.REV_KEEP, FA.REV_DROP)
        sg = FA._segments([x for x in rv if not FA.REV_DROP.search(x[0])], v["rev"]) if rv else []
        if sg:
            v["segs"], want_s = sg, False
    if want_s and tabs and v.get("cum_rev"):      # 분기보고서 '매출 현황' 표는 대개 누적(1~9월) — 누적 매출과 합이 맞는 표의 비중으로 이번 분기를 나눈다
        rv = FA._breakdown(tabs, v["cum_rev"], REV_H, FA.REV_KEEP, FA.REV_DROP)
        sg = FA._segments([x for x in rv if not FA.REV_DROP.search(x[0])], v["cum_rev"]) if rv else []
        if sg:
            k = v["rev"] / v["cum_rev"]
            v["segs"], v["seg_note"], want_s = [[n, x * k] for n, x in sg], "매출 종류는 %s 누적 비중" % v.get("cum_lab", ""), False
    if not (want_i or want_s) or not annual:
        return
    a = annual[0]
    if a["rcept_no"] == r0["rcept_no"]:
        return
    av = None
    if ia:
        la = [n for n in fa if "lab-ko" in n]
        av = FX.from_instance(fa[ia[0]], fa[la[0]] if la else "", us=False)
    if not av:
        return
    doc = P.fetch_doc(a["rcept_no"])
    tabs = FA._tables(doc) if doc else []
    if not tabs:
        return
    if want_i and av.get("sga"):
        det = FA._breakdown(tabs, av["sga"], SGA_H, FA.SGA_KEEP, SGA_DROP, min_rows=4)
        it = FA._group(det, av["sga"], "기타 판관비") if sga_ok(det) else []
        if it:
            k = v["sga"] / av["sga"]
            v["items"], v["items_from"] = [[n, x * k] for n, x in it], "'%s년 연간 비중" % av["end"][2:4]
    if want_s and av.get("rev"):
        rv = FA._breakdown(tabs, av["rev"], REV_H, FA.REV_KEEP, FA.REV_DROP)
        sg = FA._segments([x for x in rv if not FA.REV_DROP.search(x[0])], av["rev"]) if rv else []
        if sg:
            k = v["rev"] / av["rev"]
            v["segs"], v["seg_note"] = [[n, x * k] for n, x in sg], "매출 종류는 '%s년 연간 비중" % av["end"][2:4]


def _us_files(cik, acc):
    base = U.SEC_ARCH % (int(cik), acc.replace("-", ""))
    idx = U.get_json(base + "index.json")
    names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
    pick = lambda suf: next((n for n in names if n.endswith(suf)), None)      # noqa: E731
    inst, lab, cal = pick("_htm.xml"), pick("_lab.xml"), pick("_cal.xml")
    if not inst:
        return None
    raw = U.get(base + inst)
    if not raw:
        return None
    dec = lambda n: (U.get(base + n) or b"").decode("utf-8", "replace") if n else ""      # noqa: E731
    return raw.decode("utf-8", "replace"), dec(lab), dec(cal)


# ------------------------------------------------------------------ 미국: 실적 발표(8-K 2.02) 손익표 — 10-Q 가 나오기 전 며칠 동안
_MON = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
# 줄 이름 → 항목 (앞에 있을수록 먼저 고른다)
PR_ROWS = [("rev", [r"^total (net )?revenues?$", r"^total net sales and revenues?$", r"^(net )?revenues?$", r"^total net sales$", r"^net sales$", r"^sales$"]),
           ("cogs", [r"^(total )?cost of (net )?(revenues?|sales|goods sold|products sold|products and services|goods and services)( \(exclusive of .*\))?$", r"^cost of sales(, including .*)?$"]),
           ("gross", [r"^gross (profit|margin)$"]),
           ("rnd", [r"^research and development( expenses?)?$", r"^research, development and (related|engineering)( expenses?)?$"]),
           ("sga", [r"^(operating, )?(sales|selling), general,? and administrative( expenses?)?$"]),
           ("sm", [r"^(sales|selling) and marketing( expenses?)?$", r"^marketing and (sales|selling)( expenses?)?$"]),
           ("ga", [r"^general and administrative( expenses?)?$"]),
           ("opex", [r"^total operating expenses$"]),
           ("tce", [r"^total costs and expenses$"]),
           ("op", [r"^(total )?operating income( \(loss\))?$", r"^(income|earnings)( \(loss\))? from operations$", r"^operating (profit|earnings)$"]),
           ("pretax", [r"^(income|earnings)( \(loss\))? before (provision for )?income tax(es)?( expense)?$", r"^pre-?tax (income|earnings)$", r"^(income|earnings) (from continuing operations )?before (income )?taxes( on earnings)?$"]),
           ("tax", [r"^(provision for|\(?benefit from\)?) income tax(es)?$", r"^provision for \(benefit from\) income taxes$", r"^income tax (expense|provision)( \(benefit\))?$", r"^income taxes$", r"^provision for (income )?taxes( on earnings)?$"]),
           ("cni", [r"^consolidated net (income|earnings)$"]),
           ("nic", [r"^net (income|earnings) from continuing operations(, net of (income )?taxes)?$"]),
           ("ni", [r"^(consolidated )?net (income|earnings)( \(loss\))? attributable to (?!non).*$", r"^net (income|earnings)( \(loss\))?$"])]


def _cells(tr):
    out = []
    for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I):
        t = re.sub(r"<[^>]+>", " ", td)
        t = re.sub(r"&nbsp;|&#160;|&#xa0;", " ", t, flags=re.I).replace("&amp;", "&").replace("&#8217;", "'").replace("&#8212;", "—")
        t = re.sub(r"\s+", " ", t).strip()
        if t and t not in ("$", ")", "%"):
            out.append(t)
    return out


def _num(t):
    m = re.fullmatch(r"\(?\$?\s*([\d,]+(?:\.\d+)?)\s*\)?", t)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return -v if t.startswith("(") else v


def _txt(h):
    return re.sub(r"\s+", " ", re.sub(r"&nbsp;|&#160;|&#xa0;", " ", re.sub(r"<[^>]+>", " ", h), flags=re.I))


def pr_income(html):
    """실적 발표 자료의 손익계산서 표 → 이번 3개월 값. 서로 맞아떨어질 때만 돌려준다."""
    for tm in re.finditer(r"<table\b.*?</table>", html, re.S | re.I):
        before = _txt(html[max(0, tm.start() - 2500):tm.start()]).lower()
        first = _txt(tm.group(0)[:3000]).lower()                 # 표 첫 줄에 제목을 넣은 회사도 있다
        if not re.search(r"statements? of (consolidated )?(income|operations|earnings|current (and retained )?earnings)", before[-1200:] + " " + first[:600]):
            continue
        v = _pr_table(tm.group(0), before)
        if v:
            return v
    return None


PR_WHY = []


def _pr_table(tab, before):
    v = _pr_table1(tab, before)
    return v


def _pr_table1(tab, before):
    rows = [r for r in (_cells(tr) for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S | re.I)) if r]   # 빈 줄은 뺀다
    W = PR_WHY.append
    head = " ".join(" ".join(r) for r in rows[:9]) + " " + before[-600:]
    if not re.search(r"three months|quarter ended|thirteen weeks|13 weeks|fourth quarter|third quarter|second quarter|first quarter", head, re.I):
        W(1); return None
    ht = " ".join(" ".join(r) for r in rows[:9])
    dm = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b", ht, re.I)
    ym = re.search(r"\b(20\d\d)\b", ht[dm.end():]) if dm else None       # 'October 25, | October 26,' 다음 줄에 '2026 | 2025' 로 나뉜 표도 있다
    if not dm or not ym:
        W(2); return None
    end = date(int(ym.group(1)), _MON[dm.group(1).lower()], int(dm.group(2)))
    hb = head + " " + before[-1500:]
    unit = 1e6 if re.search(r"\bmillions\b", hb, re.I) else 1e3 if re.search(r"\bthousands\b|\$\s?000\b|\(000", hb, re.I) else None
    if not unit:
        W(3); return None
    cand = {}
    for c in rows:
        if len(c) < 2:
            continue
        lab = re.sub(r"\s*\(\d\)$|[:*]+$", "", c[0]).strip().lower()
        n = next((_num(x) for x in c[1:] if _num(x) is not None), None)
        if n is None:
            continue
        for key, rxs in PR_ROWS:
            for pri, rx in enumerate(rxs):
                if re.match(rx, lab) and (key not in cand or pri < cand[key][0]):
                    cand[key] = (pri, n * unit)
    v = {k: x[1] for k, x in cand.items()}
    if "sga" not in v and ("sm" in v or "ga" in v):
        v["sga"] = v.get("sm", 0) + v.get("ga", 0)
    if "ni" not in v and "cni" in v:
        v["ni"] = v["cni"]
    if any(x not in v for x in ("rev", "cogs", "op", "tax", "ni", "pretax")):
        W((4, sorted(v), unit)); return None
    tol = lambda a, b: abs(a - b) <= max(1.5 * unit, abs(b) * 0.002)      # noqa: E731
    gross = v.get("gross", v["rev"] - v["cogs"])
    if not tol(v["rev"] - v["cogs"], gross):
        W(5); return None                                             # 매출 − 원가 ≠ 매출총이익
    opex = v.get("opex", gross - v["op"])
    if "opex" in v and not tol(gross - opex, v["op"]):
        W(6); return None                                             # 총이익 − 영업비용 ≠ 영업이익
    if "tce" in v and not tol(v["rev"] - v["tce"], v["op"]):
        W(7); return None                                             # 매출 − 총비용 ≠ 영업이익
    if not (tol(v["pretax"] - v["tax"], v["ni"]) or any(k in v and tol(v["pretax"] - v["tax"], v[k]) for k in ("cni", "nic"))):
        W(8); return None                                             # 세전이익 − 법인세 ≠ 순이익
    if opex < 0 or v["rev"] <= 0:
        W(9); return None
    items = [["연구개발비", v["rnd"]]] if v.get("rnd") else []
    if v.get("sga"):
        items.append(["판매·관리비", v["sga"]])
    rest = opex - sum(x for _, x in items)
    if rest > max(abs(opex) * 0.01, 1.5 * unit):
        items.append(["기타 영업비용", rest])
    elif rest < -1.5 * unit:
        if -rest > abs(opex) * 0.03:
            W(10); return None                                         # 세부 합이 영업비용보다 크게 넘친다 — 표를 잘못 읽었다
        items = []                                              # 구조조정 환입 등 마이너스 항목이 있으면 세부 없이 영업비용 하나로
    return {"rev": v["rev"], "cogs": v["cogs"], "gross": gross, "rnd": v.get("rnd") or 0, "sga": v.get("sga") or 0,
            "op": v["op"], "tax": v["tax"], "ni": v["ni"], "items": items, "segs": [], "end": end.isoformat()}


PR_VER = "3"                                    # 실적 발표 표 읽는 방식 — 바꾸면 그 카드를 다시 읽는다


def us_pr(cik, rc, old):
    """10-Q·10-K 보다 새로운 실적 발표(8-K 2.02)가 있으면 그 손익표로 카드를 만든다 — 10-Q 가 나오면 그걸로 바뀐다"""
    last_q = next((rc["filingDate"][i] for i, f in enumerate(rc["form"]) if f in ("10-Q", "10-K")), "")
    for i, f in enumerate(rc["form"]):
        if rc["filingDate"][i] <= last_q:
            return None
        if f != "8-K" or "2.02" not in (rc.get("items") or [""] * len(rc["form"]))[i]:
            continue
        acc = rc["accessionNumber"][i]
        if old and old.get("src") == acc and old.get("ver") == VER and old.get("prv") == PR_VER:
            return "SAME"
        base = U.SEC_ARCH % (int(cik), acc.replace("-", ""))
        idx = U.get_json(base + "index.json")
        names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
        prim = rc["primaryDocument"][i]
        docs = [n for n in names if n.lower().endswith((".htm", ".html")) and n != prim and "index" not in n.lower()]
        docs.sort(key=lambda n: (0 if re.search(r"ex-?99|pr|press|earn", n, re.I) else 1, n))
        for n in docs[:3]:
            raw = U.get(base + n)
            v = pr_income((raw or b"").decode("utf-8", "replace"))
            if not v:
                continue
            end = date.fromisoformat(v["end"])
            try:
                oe = date.fromisoformat(old["end"]) if old else None
            except Exception:                       # noqa: BLE001
                oe = None
            st = oe + timedelta(days=1) if oe and 80 <= (end - oe).days <= 100 else end - timedelta(days=90)
            v["start"] = st.isoformat()
            v["period"] = FX.q_label(v["start"], v["end"])
            v["report"] = "실적발표 " + v["end"]
            v["src"] = acc
            v["prv"] = PR_VER
            v["pr"] = "8-K"                         # 실적 발표 기준 — 매출 구분은 10-Q 가 나오면 채운다
            return v
        FX.WHY = "실적 발표 손익표를 못 읽음 %s" % acc
        return None
    return None


def us_xbrl(cik, old=None):
    sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))
    if not sub:
        return None
    rc = sub["filings"]["recent"]
    try:
        p = us_pr(cik, rc, old)
    except Exception as e:                          # noqa: BLE001
        p, FX.WHY = None, "실적 발표 읽기 오류 %r" % e
    if p:
        return p
    for i, f in enumerate(rc["form"]):
        if f not in ("10-Q", "10-K"):
            continue
        acc = rc["accessionNumber"][i]
        if old and old.get("src") == acc and old.get("ver") == VER:
            return "SAME"
        got = _us_files(cik, acc)
        if not got:
            FX.WHY = "공시에 XBRL 파일 없음 %s" % acc
            return None
        v = FX.from_instance(got[0], got[1], us=True, caltext=got[2])
        if v:
            v["report"] = f + " " + rc["reportDate"][i]
            v["src"] = acc
            if not v.get("segs"):                     # 분기 보고서에 매출 종류가 없으면 최근 10-K 의 비중으로
                for k in range(i + (0 if f == "10-K" else 1), len(rc["form"])):
                    if rc["form"][k] != "10-K":
                        continue
                    try:
                        ga = got if k == i else _us_files(cik, rc["accessionNumber"][k])
                        av = FX.from_instance(ga[0], ga[1], us=True) if ga else None
                        if av and av.get("segs"):
                            r = v["rev"] / sum(x for _, x in av["segs"])
                            v["segs"] = [[n, x * r] for n, x in av["segs"]]
                            v["seg_note"] = "매출 종류는 연간(%s) 비중" % rc["reportDate"][k]
                            if av.get("seg_kind"):
                                v["seg_kind"] = av["seg_kind"]
                    except Exception:               # noqa: BLE001
                        pass
                    break
        return v
    return None


def xcheck_kr(code, corp, d):
    """DART 재무제표 API(fnlttSinglAcntAll) 로 같은 기간 매출·영업이익 — XBRL 원문과 다른 길이라 서로 검증이 된다"""
    if not d.get("end"):
        return {"err": "기간 없음"}
    end = date.fromisoformat(d["end"])
    days = (end - date.fromisoformat(d["start"])).days
    q = 0 if days > 100 else (end.month + 2) // 3
    rc = {1: "11013", 2: "11012", 3: "11014", 0: "11011", 4: "11011"}[q]
    rows = C.fetch_fs(corp, end.year, rc)
    if not rows:
        return {"err": "API 자료 없음"}
    o = {k: kr_pick(rows, k, q) for k in ("rev", "op", "ni")}
    if not o["rev"] or o["op"] is None:
        return {"err": "API 매출 없음"}
    return {"src": "DART API", "rev": round(o["rev"] / 1e8, 1), "op": round(o["op"] / 1e8, 1), "ni": None if o["ni"] is None else round(o["ni"] / 1e8, 1)}


def _same(a, b):
    """두 출처 숫자가 같은가 — 매출 0.5%, 영업이익 3%(또는 매출의 0.5%) 안"""
    if not b.get("rev"):
        return False
    if abs(a["rev"] - b["rev"]) > abs(b["rev"]) * 0.005 + 0.15:
        return False
    if b.get("op") is not None and abs(a["op"] - b["op"]) > max(abs(b["op"]) * 0.03, abs(b["rev"]) * 0.005) + 0.15:
        return False
    if b.get("ni") is not None and a.get("ni") is not None and abs(a["ni"] - b["ni"]) > max(abs(b["ni"]) * 0.03, abs(b["rev"]) * 0.005) + 0.15:
        return False                                # 순이익도 맞아야 한다 (지배주주 몫만 적은 경우 등)
    return True


def ext_check(code, d, m, days):
    """다른 탭 실적 자료(따로 수집한 것)와 같은 기간 숫자 비교 → ('ok'|'diff'|'none', 설명)"""
    p = {"US": os.path.join("data", "us", code + ".json"), "KR": os.path.join("data", code + ".json"),
         "UL": os.path.join("data", "unlisted", code + ".json")}[m]
    src = jl(p, {}) or {}
    rows = (src.get("annual") if days > 100 else src.get("quarterly")) or []
    if not rows:
        return "none", "비교할 실적 자료 없음"
    if m == "US":                                   # 미국은 회계 분기 번호가 달라 숫자로 찾는다
        return ("ok", "미국 실적 자료와 일치") if any(_same(d, r) for r in rows[-8:]) else ("diff", "미국 실적 자료와 다름")
    end = date.fromisoformat(d["end"])
    if days > 100:
        same = [r for r in rows if (r.get("y") or r.get("p")) == end.year]
    else:
        same = [r for r in rows if r.get("y") == end.year and r.get("q") == (end.month + 2) // 3]
    if not same or not same[0].get("rev"):
        return "none", "같은 기간 실적 자료 없음"
    return ("ok", "실적 자료와 일치") if _same(d, same[0]) else ("diff", "실적 자료와 다름 (매출 %s vs %s)" % (d["rev"], same[0]["rev"]))


def verify(code, d, m, days):
    """올리기 전 검증 — 서로 다른 두 출처가 같은 숫자를 말할 때만 통과. → (통과?, 까닭)"""
    s, why = ext_check(code, d, m, days)
    xc = d.get("xcheck") or {}
    if s == "ok":
        return True, why
    if m == "US" and d.get("pr"):                   # 10-Q 전 실적 발표 — 공시 손익표가 매출−원가=총이익, 총이익−영업비용=영업이익, 세전−법인세=순이익으로 맞아떨어진 것만 여기 온다
        return True, "실적 발표 손익표 검산 일치 (10-Q 나오면 다시 대조)"
    if xc.get("rev") and _same(d, xc):              # 실적 탭 자료가 아직 없거나 다르면 DART API(공식 재무제표)와 맞는지
        if s == "none":
            return True, "DART API 와 일치"
        r = ext_ratio(code, d, days)
        if r and 1 / 3 <= r <= 3:                   # 공시 원문·DART API 가 서로 맞고 실적 탭만 다르면 카드를 믿는다 (실적 탭 쪽 확인 대상)
            XTAB[code] = {"name": d.get("name"), "card_rev": d["rev"], "tab_ratio": round(r, 3)}
            return True, "DART API 와 일치 (실적 탭과는 다름)"
        return False, why + " · DART API 와는 일치하지만 실적 탭과 3배 넘게 달라(통화·단위) 보류"
    return False, why + ("" if not xc else " · DART API " + (xc.get("err") or "와 다름"))


HOLD = {}
XTAB = {}                                               # 카드·DART API 는 맞는데 실적 탭만 다른 회사 (실적 탭 점검용)


def ext_ratio(code, d, days):
    """카드 매출 ÷ 실적 탭 같은 기간 매출"""
    src = jl(os.path.join("data", code + ".json"), {}) or {}
    rows = (src.get("annual") if days > 100 else src.get("quarterly")) or []
    end = date.fromisoformat(d["end"])
    same = [r for r in rows if r.get("y") == end.year and (days > 100 or r.get("q") == (end.month + 2) // 3)]
    return d["rev"] / same[0]["rev"] if same and same[0].get("rev") else None


def usable(code):
    p = os.path.join(OUT, code + ".json")
    if not os.path.exists(p):
        return False
    d = json.load(open(p, encoding="utf-8"))
    rev, op = d.get("rev"), d.get("op")
    if not rev or rev <= 0 or op is None or op >= rev or d.get("ni") is None:      # 순이익이 없으면 그림이 끊긴다
        return False
    if not d.get("start") and d.get("y") and d.get("q"):          # 예전 방식(분기 번호만 있는 자료)
        d["start"], d["end"] = "%d-%02d-01" % (d["y"], d["q"] * 3 - 2), "%d-%02d-28" % (d["y"], d["q"] * 3)
    if not d.get("start") or not d.get("end"):
        return False
    g1, g2 = d.get("gross"), rev - (d.get("cogs") or 0)      # 카드(화면)와 같은 규칙으로 매출총이익을 고른다
    gross = g1 if g1 is not None else g2
    if g1 is not None and d.get("cogs") is not None and abs(g1 - g2) > rev * 0.01:
        gross = g1 if d.get("sga") is not None and abs(g1 - d["sga"] - op) <= rev * 0.01 else g2
    if gross - op < 0 or gross < 0 or gross > rev * 1.0001:      # 매출원가가 음수(환입)라 매출총이익이 매출보다 큰 건 그리지 않는다
        return False
    days = (date.fromisoformat(d["end"]) - date.fromisoformat(d["start"])).days
    if not (80 <= days <= 100 or 350 <= days <= 380):
        return False
    lim = 520 if (len(code) == 8 and code.isdigit()) else 200          # 비상장(감사보고서·연간)은 1년 넘게 기다린다
    if (TODAY - date.fromisoformat(d["end"])).days >= lim:              # 분기 끝 + 제출 기한(45~90일)보다 오래되면 뺌
        return False
    m = "UL" if (len(code) == 8 and code.isdigit()) else ("KR" if (len(code) == 6 and code[:1].isdigit()) else "US")
    ok, why = verify(code, d, m, days)
    if not ok:
        HOLD[code] = {"name": d.get("name"), "market": m, "why": why, "period": d.get("period")}
    return ok


def cross_ok(code, d, days):
    """국내 상장사 — 국내 실적 탭 자료(data/<코드>.json)의 같은 분기 매출과 크게 다르면(달러로 공시한 회사·단위 실수) 뺀다"""
    p = os.path.join("data", code + ".json")
    if not (len(code) == 6 and os.path.exists(p)) or days > 100:
        return True
    try:
        end = date.fromisoformat(d["end"])
        q = [x for x in (json.load(open(p, encoding="utf-8")).get("quarterly") or []) if x.get("y") == end.year and x.get("q") == (end.month + 2) // 3]
        if not q or not q[0].get("rev"):
            return True
        r = d["rev"] / q[0]["rev"]
        return 0.8 <= r <= 1.25
    except Exception:                                   # noqa: BLE001
        return True


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


T0 = time.time()
MINUTES = float(os.environ.get("FLOW_MINUTES", "75"))      # 한 번 돌 때 쓸 시간 — 남은 회사는 다음 번에
DART_MAX = int(os.environ.get("FLOW_DART_MAX", "7000"))     # DART 하루 한도(2만)를 다른 수집기와 나눠 쓴다
# DART 하루 한도 2만 번 나눠 쓰기 (자정 KST 초기화): 국내 실적 14,000 · 국내5 1,000 · 비상장 1,500 · 대주주 등 ~500 → 돈의 흐름은 하루 2,500
FLOW_DAY = int(os.environ.get("FLOW_DART_DAY", "2500"))
USAGE = os.path.join("data", "flow", "_dart_usage.json")


def kst_now():
    return datetime.utcnow() + timedelta(hours=9)


def used_today():
    u = jl(USAGE, {}) or {}
    return int(u.get(kst_now().strftime("%Y-%m-%d"), 0))


def add_usage(n):
    day = kst_now().strftime("%Y-%m-%d")
    u = jl(USAGE, {}) or {}
    u = {k: v for k, v in u.items() if k >= (kst_now() - timedelta(days=7)).strftime("%Y-%m-%d")}
    u[day] = int(u.get(day, 0)) + int(n)
    json.dump(u, open(USAGE, "w", encoding="utf-8"))
FAILP = os.path.join(OUT, "_fail.json")                     # 못 읽은 회사 — 1주일 뒤에 다시


def time_left():
    return time.time() - T0 < MINUTES * 60


def recent_kr(days=12):
    """최근 정기보고서(분기·반기·사업)를 낸 회사 corp_code → 가장 최근 접수번호 — 이 회사들만 새로 읽는다"""
    out = {}
    for p in range(1, 60):
        res = C.api_get("list.json", {"bgn_de": (TODAY - timedelta(days=days)).strftime("%Y%m%d"), "end_de": TODAY.strftime("%Y%m%d"),
                                      "pblntf_ty": "A", "page_no": p, "page_count": 100})
        if not res or res.get("status") != "000":
            break
        for r in res.get("list", []):
            cc, rn = r.get("corp_code"), r.get("rcept_no") or ""
            if rn > out.get(cc, ""):
                out[cc] = rn
        if p >= int(res.get("total_page") or 1):
            break
    for p in range(1, 30):                                   # 감사보고서(비상장)
        res = C.api_get("list.json", {"bgn_de": (TODAY - timedelta(days=days)).strftime("%Y%m%d"), "end_de": TODAY.strftime("%Y%m%d"),
                                      "pblntf_ty": "F", "page_no": p, "page_count": 100})
        if not res or res.get("status") != "000":
            break
        for r in res.get("list", []):
            cc, rn = r.get("corp_code"), r.get("rcept_no") or ""
            if rn > out.get(cc, ""):
                out[cc] = rn
        if p >= int(res.get("total_page") or 1):
            break
    return out


def recent_us(days=12):
    """최근 10-Q·10-K 를 낸 회사 CIK — SEC 날짜별 목록(form.YYYYMMDD.idx)"""
    out = set()
    for k in range(days + 1):
        d = TODAY - timedelta(days=k)
        if d.weekday() >= 5:
            continue
        try:                                        # 없는 날짜(휴일·아직 안 올라온 오늘)는 SEC 가 403 을 준다 — collect_us.get 은 403 이면 멈추므로 막는다
            raw = U.get("https://www.sec.gov/Archives/edgar/daily-index/%d/QTR%d/form.%s.idx" % (d.year, (d.month - 1) // 3 + 1, d.strftime("%Y%m%d")), tries=1)
        except SystemExit:
            raw = None
        if not raw:
            continue
        for line in raw.decode("latin-1").splitlines():
            if line.startswith(("10-Q ", "10-K ", "10-Q/A", "10-K/A", "8-K ")):
                m = re.search(r"\s(\d{3,10})\s+\d{4}-?\d{2}-?\d{2}\s", line)
                if m:
                    out.add(int(m.group(1)))
    return out


def jl(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:                               # noqa: BLE001
        return d


def items_off(d):
    """영업비용 세부 합이 영업비용(매출총이익 - 영업이익)과 1% 넘게 다르면 True"""
    try:
        g = d.get("gross") if d.get("gross") is not None else d["rev"] - (d.get("cogs") or 0)
        opex = g - d["op"]
        s = sum(v for _, v in d.get("items") or [])
        return opex > 0 and abs(s - opex) > opex * 0.01
    except Exception:                                   # noqa: BLE001
        return False


def save(code, d, market, name):
    d.update({"code": code, "name": name, "market": market, "updated": TODAY.isoformat(), "ver": VER})
    json.dump(d, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False)


def work_kr(job):
    """국내·비상장 한 곳 (다른 프로세스에서 돈다) → (job, d|None|'SAME', 까닭, 호출 수, 걸린 초)"""
    pr, _, mk, code, corp, old, name = job
    t0, c0 = time.time(), C._call_count
    try:
        ulmeta = (jl(os.path.join("data", "unlisted", code + ".json"), {}) or {}) if mk == "UL" else {}
        if mk == "UL" and ulmeta.get("source") == "audit":
            import flow_audit as FA
            x = FA.flow(code)
            why = FA.WHY
            if x and old and old.get("src") == x.get("src") and old.get("ver") == VER and old.get("uver") == UL_VER:
                x = "SAME"
        else:
            FX.WHY = ""
            x = kr_xbrl(corp, old)
            why = FX.WHY
        if x == "SAME":
            return job, "SAME", "", C._call_count - c0, time.time() - t0
        d = scaled(x, 1e8) if x else None
        if not d and mk == "KR":
            d = kr_one(code, corp)
        if d and mk == "KR" and x:                  # 다른 길(DART 재무제표 API)로 같은 분기 매출·영업이익을 한 번 더 받아 맞춰 본다
            try:
                d["xcheck"] = xcheck_kr(code, corp, d)
            except Exception as e:                  # noqa: BLE001
                d["xcheck"] = {"err": str(e)[:80]}
        if d:
            d["unit"] = "억원"
            d["docv"] = DOC_VER
            if mk == "UL":
                d["uver"] = UL_VER
        return job, d, why, C._call_count - c0, time.time() - t0
    except Exception as e:                          # noqa: BLE001
        return job, None, "오류 %s" % e, C._call_count - c0, time.time() - t0


def work_us(job):
    pr, _, t, cik, old = job
    t0 = time.time()
    FX.WHY = ""
    try:
        x = us_xbrl(cik, old)
    except (Exception, SystemExit) as e:            # noqa: BLE001  (SEC 403 이면 collect_us.get 이 멈추려 한다 — 이 회사만 건너뛴다)
        x, FX.WHY = None, "오류 %r" % e
    if x == "SAME":
        return job, "SAME", "", time.time() - t0
    d = scaled(x, 1e6) if x else None
    if not d:
        try:
            d = us_one(t, cik)
        except (Exception, SystemExit):             # noqa: BLE001
            d = None
        if d:
            d["xbrl_err"] = FX.WHY or "까닭 모름"
    if d:
        d["unit"] = "백만달러"
        d["usver"] = US_VER
    return job, d, FX.WHY, time.time() - t0


def run_pool(fn, jobs, workers, on_done, budget_ok):
    """여러 프로세스로 나눠 돌린다 — 시간이 다 되면 새 일은 넣지 않는다"""
    from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
    it, live, n = iter(jobs), set(), 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        while True:
            while len(live) < workers * 2 and budget_ok():
                j = next(it, None)
                if j is None:
                    break
                live.add(ex.submit(fn, j))
            if not live:
                break
            done, live = wait(live, return_when=FIRST_COMPLETED)
            for f in done:
                n += 1
                on_done(f.result())
    return n


def build_index():
    idx = {}
    HOLD.clear()
    XTAB.clear()
    for fn in os.listdir(OUT):
        if not fn.endswith(".json") or fn.startswith(("_", "index")):
            continue
        code = fn[:-5]
        if usable(code):
            d = jl(os.path.join(OUT, fn), {})
            m = d.get("market") or ("US" if not code.isdigit() else "UL" if len(code) == 8 else "KR")
            idx[code] = {"n": d.get("name") or code, "m": m, "p": d.get("period")}
    json.dump({"updated": TODAY.isoformat(), "items": idx}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"updated": TODAY.isoformat(), "note": "카드·DART API 는 맞는데 국내 실적 탭 숫자가 다른 회사 — 실적 탭 점검 대상", "items": XTAB},
              open(os.path.join(OUT, "_tabdiff.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"updated": TODAY.isoformat(), "note": "두 출처가 같은 숫자를 말하지 않아 카드에 올리지 않은 회사", "items": HOLD},
              open(os.path.join(OUT, "_hold.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return idx


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--index-only" in sys.argv:
        print("카드 %d곳" % len(build_index()))
        return
    mc = json.load(open("data/mcap.json", encoding="utf-8"))["stocks"]
    mu = json.load(open("data/mcap_us.json", encoding="utf-8"))["stocks"]
    ul = (jl("data/unlisted/index.json", {}) or {}).get("companies", [])
    # 대상: 국내 상장 보통주 전부 · 미국 전부 · 비상장 탭 회사 전부 (시총 큰 순서로)
    kr = [c for c in sorted(mc, key=lambda c: -(mc[c].get("c") or 0)) if c.endswith("0") and mc[c].get("c")]
    us = sorted([t for t in mu if mu[t].get("c")], key=lambda t: -mu[t]["c"])
    if "--top" in sys.argv:
        n = int(sys.argv[sys.argv.index("--top") + 1]); kr, us, ul = kr[:n], us[:n], ul[:n]
    failp = FAILP.replace(".json", "_us.json") if "--us-only" in sys.argv else FAILP
    fail = jl(failp, {}) or {}
    W = int(os.environ.get("FLOW_WORKERS", "6"))

    def skip_fail(k):
        f = fail.get(k)
        return f and (TODAY - date.fromisoformat(f["d"])).days < 7

    def stale(old):
        """다음 분기 보고서가 나왔어야 할 때가 지났는데 카드는 아직 예전 분기 (최근 12일 목록에서 빠진 회사도 놓치지 않게)"""
        try:
            end = date.fromisoformat(old["end"])
        except Exception:                           # noqa: BLE001
            return False
        if (old.get("chk") or "") >= (TODAY - timedelta(days=7)).isoformat():
            return False                            # 일주일 안에 확인했는데 새 보고서가 없었다
        return end + timedelta(days=92 + 50) < TODAY

    def need(key, old, recent_hit, latest=None):
        """0: 새 보고서 · 1: 아직 없음 · 2: 계산 방식이 바뀜 · None: 그대로"""
        if old and old.get("ver") == VER and recent_hit and latest and old.get("src") == latest:
            return None                             # 최근 보고서를 이미 카드에 담았다 — 매일 다시 읽지 않는다
        if old and old.get("ver") == VER and not recent_hit:
            return 1 if stale(old) else None       # 새 보고서 다음 차례
        if old and old.get("ver") == VER:
            return 0
        if not old:
            return None if skip_fail(key) else 1
        return 2 if not recent_hit else 0

    done = {"kr": 0, "us": 0, "ul": 0, "same": 0, "fail": 0, "sec": 0.0, "calls": 0}

    def finish(code, d, mk, name, why, old):
        if d == "SAME":
            if old:
                old["ver"] = VER
                old["chk"] = TODAY.isoformat()
                save(code, old, mk, old.get("name") or name)
            done["same"] += 1
        elif d:
            try:                                    # 새 숫자가 검증을 못 넘고 예전 카드는 검증된 것이면 예전 카드를 그대로 둔다
                days = (date.fromisoformat(d["end"]) - date.fromisoformat(d["start"])).days if d.get("end") and d.get("start") else 90
                if old and not verify(code, d, mk, days)[0] and usable(code):
                    print("  보류 %s %s — 새 숫자 검증 실패, 예전 카드 유지" % (code, name))
                    return
            except Exception:                       # noqa: BLE001
                pass
            save(code, d, mk, name)
            fail.pop(code, None)
            done[{"KR": "kr", "UL": "ul", "US": "us"}[mk]] += 1
            print("  ok %s %s %s 매출 %s 영업 %s 순 %s 부문 %d 비용 %d %s" % (mk, code, name, d.get("rev"), d.get("op"), d.get("ni"),
                  len(d.get("segs") or []), len(d.get("items") or []), d.get("xbrl_err", "")), flush=True)
        else:
            fail[code] = {"d": TODAY.isoformat(), "why": why or "자료 없음"}
            done["fail"] += 1

    if "--us-only" not in sys.argv:
        C.API_KEY = C.get_key()
        cmap = C.load_corp_map()
        rk = recent_kr()
        print("최근 정기·감사보고서 낸 국내 회사 %d곳" % len(rk), flush=True)
        jobs = []
        for i, code in enumerate(kr):
            info = cmap.get(code)
            if not info:
                continue
            old = jl(os.path.join(OUT, code + ".json"))
            pr = need(code, old, info["corp_code"] in rk, rk.get(info["corp_code"]))
            if old and old.get("docv") != DOC_VER and (len(old.get("items") or []) < 2 or len(old.get("segs") or []) < 2):
                pr, old = 2, None                       # 매출 구분·판관비 세부가 없던 회사 — 보고서 원문에서 다시
            elif old and "xcheck" not in old and not usable(code):
                pr, old = (2 if pr is None else pr), None   # 아직 검증 못 한 카드 — DART API 로 맞춰 보려고 다시 (그대로 건너뛰지 않게)
            if pr is not None:
                jobs.append((pr, i, "KR", code, info["corp_code"], old, mc[code].get("n")))
        for i, c in enumerate(ul):
            old = jl(os.path.join(OUT, c["code"] + ".json"))
            pr = need(c["code"], old, c["code"] in rk, rk.get(c["code"]))
            if old and old.get("uver") != UL_VER:
                pr, old = -1, None                       # 비상장은 탭 회사 수가 적어 먼저 다시 읽는다
            if pr is not None:
                jobs.append((pr, i, "UL", c["code"], c["code"], old, c.get("name")))
        jobs.sort(key=lambda j: (j[0], j[1]))
        print("국내·비상장 할 일 %d곳 · 동시에 %d개" % (len(jobs), W), flush=True)

        def on_kr(r):
            job, d, why, calls, sec = r
            done["calls"] += calls; done["sec"] += sec
            finish(job[3], d, job[2], job[6], why, job[5])
        left = min(DART_MAX, FLOW_DAY - used_today())
        h = kst_now().hour
        if 0 <= h < 7:                                   # 자정~아침 7시는 국내 실적·비상장 수집이 DART 를 쓰는 시간 — 돈의 흐름은 쉬기
            left = 0
        print("  DART 오늘 쓴 %d · 이번에 쓸 수 있는 %d" % (used_today(), max(0, left)), flush=True)
        # 한 곳에 원문·API 를 여러 번 부르니 여유를 두고 멈춘다 (병렬로 도는 몫까지)
        n = run_pool(work_kr, jobs, W, on_kr, lambda: time_left() and C._call_count + done["calls"] + W * 12 < left) if left > W * 12 else 0
        add_usage(C._call_count + done["calls"])
        print("  국내 %d/%d곳 처리 · 한 곳 평균 %.1f초 · DART 호출 %d" % (n, len(jobs), done["sec"] / max(1, n), done["calls"]), flush=True)
    if "--kr-only" not in sys.argv and time_left():
        ru = recent_us()
        print("최근 10-Q·10-K 낸 미국 회사 %d곳" % len(ru), flush=True)
        jobs = []
        for i, t in enumerate(us):
            cik = (jl(os.path.join("data", "us", t + ".json"), {}) or {}).get("cik")
            if isinstance(cik, (list, tuple)):          # 여러 CIK 를 적어 둔 회사 — 첫 번째(본사)
                cik = cik[0] if cik else None
            try:
                cik = int(cik) if cik else None
            except (TypeError, ValueError):
                cik = None
            if not cik:
                continue
            old = jl(os.path.join(OUT, t + ".json"))
            pr = need(t, old, cik in ru)
            if old and old.get("usver") != US_VER and (len(old.get("items") or []) < 2 or items_off(old)):
                pr, old = 2, None                       # 영업비용 세부가 없던 회사 — 새 방식으로 다시
            if pr is not None:
                jobs.append((pr, i, t, cik, old))
        jobs.sort(key=lambda j: (j[0], j[1]))
        print("미국 할 일 %d곳 · 동시에 %d개" % (len(jobs), min(W, 4)), flush=True)
        t_us = [0.0]

        def on_us(r):
            job, d, why, sec = r
            t_us[0] += sec
            finish(job[2], d, "US", mu[job[2]].get("n"), why, job[4])
        n = run_pool(work_us, jobs, min(W, 4), on_us, time_left)      # SEC 는 초당 10번까지 — 4개면 넉넉
        print("  미국 %d/%d곳 처리 · 한 곳 평균 %.1f초" % (n, len(jobs), t_us[0] / max(1, n)), flush=True)
    json.dump(fail, open(failp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    idx = build_index()
    print("끝: 국내 %(kr)d · 미국 %(us)d · 비상장 %(ul)d 새로 · 그대로 %(same)d · 실패 %(fail)d" % done, "· 카드 %d곳" % len(idx), flush=True)

if __name__ == "__main__":
    main()
