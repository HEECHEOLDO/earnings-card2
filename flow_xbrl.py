#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""돈의 흐름 카드 — 공시 원본(XBRL)에서 '가장 최근 3개월' 손익과 매출 종류(사업 부문·제품)를 뽑는다.
국내: DART 보고서 원본(fnlttXbrl) · 미국: SEC 10-Q/10-K 원본. collect_flow.py 가 부른다."""
import re
from datetime import date

import xbrl_dims as XD

GEO = re.compile(r"Geograph|지역|국가|Countr|Timing|이전하는|이행하는|고객|Customer|Consolidat|Equity|Investee|Secondary|Related|관계|Carrying|Subsidiar|Joint|Associate|Range|Scenario|Restatement|Adjust")
SKIP_M = re.compile(r"공시금액|ReportedAmount|조정|제거|Elimination|Adjust|Reconcil|연결|Consolidat|Intersegment|부문간|Corporate|전사|수행의무|한 시점|기간에 걸쳐|PointInTime|OverTime", re.I)
GEO_M = re.compile(r"Americas|Europe|China|Japan|Asia|Pacific|EMEA|United States|International|미주|유럽|중국|아시아|국내|해외|북미|재화의 판매|용역의 제공", re.I)
TOTAL_M = re.compile(r"OperatingSegmentsMember|영업부문 \[구성요소\]|SegmentsTotal|AllSegments", re.I)
KO = {"Online Stores": "온라인 스토어", "Third-Party Seller Services": "판매자 서비스", "Amazon Web Services": "AWS", "Advertising Services": "광고", "Subscription Services": "구독",
      "Physical Stores": "오프라인 매장", "Automotive Sales": "자동차 판매", "Services And Other": "서비스 등", "Energy Generation And Storage Sales": "에너지 저장",
      "Energy Generation And Storage Leasing": "에너지 리스", "Automotive Leasing": "자동차 리스", "Automotive Regulatory Credits": "탄소 배출권", "Hyperscale": "하이퍼스케일",
      "AI Clouds, Industrial, & Enterprise": "AI 클라우드·기업", "Edge Computing": "엣지 컴퓨팅", "Client and Gaming": "PC·게이밍", "Embedded": "임베디드",
      "DRAM Products": "DRAM", "NAND Products": "NAND", "Other Product Sales": "기타", "Subscriptions and Services": "구독·서비스", "Other Operating Segment": "기타",
      "Walmart US": "월마트 미국", "Walmart International": "월마트 해외", "Sam's Club US": "샘스클럽", "Azure": "애저", "Productivity And Server Licensing": "오피스·서버",
      "Search And Advertising": "검색·광고", "Industry Solutions": "기업 솔루션", "Windows OEM And Devices": "윈도·기기", "Frontier And Support Services": "지원 서비스",
      "Microsoft Three Six Five Cloud": "M365 클라우드", "XBOX": "엑스박스", "Client": "PC", "Infrastructure Software": "인프라 소프트웨어", "Semiconductor Solutions": "반도체",
      "Service": "서비스", "Services": "서비스", "Product": "제품", "Products": "제품", "Data Center": "데이터센터", "Gaming": "게이밍", "Automotive": "자동차",
      "Professional Visualization": "전문 시각화", "Wearables, Home and Accessories": "웨어러블·홈", "Advertising": "광고", "Subscriptions, platforms, and devices": "구독·기기",
      "Google Cloud": "구글 클라우드", "Google Services": "구글 서비스", "Other": "기타", "Others": "기타", "Energy generation and storage": "에너지 저장", "Automotive sales": "자동차 판매",
      "Regulatory credits": "탄소 배출권", "Services and other": "서비스 등", "Family of Apps": "앱(페이스북 등)", "Reality Labs": "리얼리티 랩스"}


def clean_member(lab, name):
    s = lab or name.split(":")[-1]
    s = re.sub(r"\s*\[(구성요소|Member)\]\s*$", "", s).replace("&amp;", "&").strip()
    if not lab:
        s = re.sub(r"Member$", "", s)
        s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    return KO.get(s, s)


def q_label(start, end):
    a, b = start.split("-"), end.split("-")
    if a[0] == b[0]:
        return "'%s년 %d~%d월" % (b[0][2:], int(a[1]), int(b[1]))
    return "'%s.%d~'%s.%d" % (a[0][2:], int(a[1]), b[0][2:], int(b[1]))


def pick_period(ctx, facts, rev_names, base_ok):
    """가장 최근에 끝나는 3개월(80~100일) 기간 — 없으면 가장 긴 기간(연간)"""
    best = None
    for n, c, v in facts:
        if n not in rev_names or not base_ok(ctx[c]):
            continue
        p = ctx[c]
        d = (date.fromisoformat(p["end"]) - date.fromisoformat(p["start"])).days
        key = (p["end"], 1 if 80 <= d <= 100 else 0, d)
        if best is None or key > best[0]:
            best = (key, (p["start"], p["end"]))
    return best[1] if best else None


def segments(ctx, facts, rev_names, per, rev, L, base_dim):
    """한 축(부문·제품)의 멤버별 매출. 합이 총매출과 맞는 축을 고른다."""
    groups = {}
    for n, c, v in facts:
        if n not in rev_names:
            continue
        p = ctx[c]
        if (p["start"], p["end"]) != per:
            continue
        dims = [d for d in p["dims"] if not base_dim(d)]
        tot = any(TOTAL_M.search(m) or TOTAL_M.search(L.get(m, "")) for a, m in dims)
        dims = [d for d in dims if not (TOTAL_M.search(d[1]) or TOTAL_M.search(L.get(d[1], "")))]
        if len(dims) != 1:
            continue
        a, m = dims[0]
        if GEO.search(a) or GEO.search(L.get(a, "")) or SKIP_M.search(m) or SKIP_M.search(L.get(m, "")):
            continue
        g = groups.setdefault((a, tot), {})
        if m not in g:
            g[m] = v
    best = None
    for (a, tot), g in groups.items():
        mem = dict((m, v) for m, v in g.items() if v > 0)
        if len(mem) < 2:
            continue
        generic = [m for m in ("us-gaap:ServiceOtherMember", "us-gaap:ServiceMember", "us-gaap:ProductMember") if m in mem]
        for _ in range(6):                       # 합이 너무 크면 겹치는 묶음(제품/서비스 합계, 상위 범주)을 뺀다
            s = sum(mem.values())
            if s <= rev * 1.06 or len(mem) <= 2:
                break
            if generic:
                mem.pop(generic.pop(), None)
                continue
            # 다른 멤버들의 합과 같은 멤버(상위 범주)를 찾아 뺀다
            vals = sorted(mem.items(), key=lambda x: -x[1])
            drop = None
            for m, v in vals:
                rest = s - v
                if abs(rest - rev) / rev < 0.06:
                    drop = m
                    break
            mem.pop(drop or vals[0][0])
        s = sum(mem.values())
        if len(mem) < 2 or not (rev * 0.85 <= s <= rev * 1.45):
            continue
        geo = sum(1 for m in mem if GEO_M.search(L.get(m, "") or m)) / len(mem)          # 지역·거래 형태로 나눈 축은 뒤로
        score = abs(s / rev - 1) + (0.0 if re.search(r"Product|Business|Segment|부문|제품", a + L.get(a, "")) else 0.05) + (0.03 if tot else 0) + geo * 0.5
        if best is None or score < best[0]:
            best = (score, a, mem)
    if not best:
        return []
    out = sorted(([clean_member(L.get(m), m), v] for m, v in best[2].items()), key=lambda x: -x[1])
    if len(out) > 7:
        out = out[:6] + [["기타", sum(v for _, v in out[6:])]]
    return out


def from_instance(text, labtext, us):
    ctx, facts = XD.parse(text)
    L = XD.labels(labtext) if labtext else {}
    if us:
        base_dim = lambda d: False                              # noqa: E731
        base_ok = lambda p: not p["dims"]                       # noqa: E731
        N = {"rev": ["us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:SalesRevenueNet"],
             "cogs": ["us-gaap:CostOfRevenue", "us-gaap:CostOfGoodsAndServicesSold", "us-gaap:CostOfGoodsSold"],
             "gross": ["us-gaap:GrossProfit"], "rnd": ["us-gaap:ResearchAndDevelopmentExpense"],
             "sga": ["us-gaap:SellingGeneralAndAdministrativeExpense"], "sm": ["us-gaap:SellingAndMarketingExpense", "us-gaap:MarketingAndAdvertisingExpense"],
             "ga": ["us-gaap:GeneralAndAdministrativeExpense"], "op": ["us-gaap:OperatingIncomeLoss"],
             "tax": ["us-gaap:IncomeTaxExpenseBenefit"], "ni": ["us-gaap:NetIncomeLoss", "us-gaap:ProfitLoss"]}
    else:
        cons = any(m.endswith("ConsolidatedMember") for p in ctx.values() for a, m in p["dims"])
        want = "ConsolidatedMember" if cons else "SeparateMember"
        base_dim = lambda d: "ConsolidatedAndSeparate" in d[0]  # noqa: E731
        base_ok = lambda p: (all(base_dim(d) for d in p["dims"]) and (not p["dims"] or any(m.endswith(want) for a, m in p["dims"])))   # noqa: E731
        N = {"rev": ["ifrs-full:Revenue", "ifrs-full:RevenueFromContractsWithCustomers"], "cogs": ["ifrs-full:CostOfSales"], "gross": ["ifrs-full:GrossProfit"],
             "sga": ["dart:TotalSellingGeneralAdministrativeExpenses", "ifrs-full:SellingGeneralAndAdministrativeExpense"],
             "op": ["dart:OperatingIncomeLoss", "ifrs-full:ProfitLossFromOperatingActivities"], "tax": ["ifrs-full:IncomeTaxExpenseContinuingOperations"],
             "ni": ["ifrs-full:ProfitLoss"]}
    per = pick_period(ctx, facts, set(N["rev"]), base_ok)
    if not per:
        return None
    val = {}
    for k, names in N.items():
        for nm in names:
            for n, c, v in facts:
                p = ctx[c]
                if n == nm and (p["start"], p["end"]) == per and base_ok(p):
                    val[k] = v
                    break
            if k in val:
                break
    if not val.get("rev") or val.get("op") is None or val.get("ni") is None:
        return None
    if val.get("gross") is None and val.get("cogs") is not None:
        val["gross"] = val["rev"] - val["cogs"]
    if val.get("cogs") is None and val.get("gross") is not None:
        val["cogs"] = val["rev"] - val["gross"]
    bd = base_dim if not us else (lambda d: False)
    segs = segments(ctx, facts, set(N["rev"]), per, val["rev"], L, bd)
    if not segs:                                  # 부문 매출이 누적(1~6월 등)으로만 있으면 그 비중으로 나눈다
        cum = None
        for n, c, v in facts:
            p = ctx[c]
            if n in N["rev"] and p["end"] == per[1] and p["start"] < per[0] and base_ok(p):
                if cum is None or p["start"] < cum[0][0]:
                    cum = ((p["start"], p["end"]), v)
        if cum:
            sc = segments(ctx, facts, set(N["rev"]), cum[0], cum[1], L, bd)
            if sc:
                k = val["rev"] / sum(v for _, v in sc)
                segs = [[n, v * k] for n, v in sc]
                val["seg_note"] = "매출 종류는 " + q_label(*cum[0]).split(" ")[-1] + " 비중"
    val["segs"] = segs
    val["start"], val["end"] = per
    val["period"] = q_label(*per)
    return val
