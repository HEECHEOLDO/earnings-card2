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
TOTAL_M = re.compile(r"(?:^|:)(?:OperatingSegmentsMember|\w*SegmentsTotal\w*|AllSegments\w*)$|^영업부문 \[구성요소\]$", re.I)   # 회사가 만든 멤버 이름 안의 'OfOperatingSegmentsMember' 는 합계가 아니다
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
    s = REGION_KO.get(s, s)
    return KO.get(s, s)


GEO_AX = re.compile(r"Geograph|지역|국가|Countr|Region", re.I)       # 지역 축 — 매출 종류가 없을 때만 쓴다
REGION_KO = {"본사 소재지 국가": "국내", "대한민국": "국내", "한국": "국내", "UNITED STATES": "미국", "United States": "미국", "U.S.": "미국",
             "Americas": "미주", "Europe": "유럽", "Greater China": "중화권", "China": "중국", "Japan": "일본", "Rest of Asia Pacific": "기타 아시아",
             "Asia Pacific": "아시아·태평양", "EMEA": "유럽·중동·아프리카", "Non-US": "미국 외", "Non- U.S.": "미국 외", "International": "해외",
             "Latin America": "중남미", "North America": "북미", "Other Countries": "기타 국가", "Rest of World": "기타", "Taiwan": "대만",
             "Singapore": "싱가포르", "Other": "기타", "KUS": "미국(KUS)"}


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


def segments(ctx, facts, rev_names, per, rev, L, base_dim, geo_ok=False, want=None):
    """한 축(부문·제품)의 멤버별 매출. 합이 총매출과 맞는 축을 고른다. geo_ok: 지역 축도 허용(제품·부문이 없을 때)
    want: 연결/별도 중 쓸 쪽 — 다른 쪽(예: 별도에만 있는 '호주')이 섞여 들어오지 않게"""
    groups = {}
    for n, c, v in facts:
        if n not in rev_names:
            continue
        p = ctx[c]
        if (p["start"], p["end"]) != per:
            continue
        if want and any(base_dim(d) and not d[1].endswith(want) for d in p["dims"]):
            continue
        dims = [d for d in p["dims"] if not base_dim(d)]
        tot = any(TOTAL_M.search(m) or TOTAL_M.search(L.get(m, "")) for a, m in dims)
        dims = [d for d in dims if not (TOTAL_M.search(d[1]) or TOTAL_M.search(L.get(d[1], "")))]
        if len(dims) != 1:
            continue
        a, m = dims[0]
        al = a + " " + L.get(a, "")
        if SKIP_M.search(m) or SKIP_M.search(L.get(m, "")):
            continue
        if geo_ok and not GEO_AX.search(al):
            continue                              # 지역 단계에서는 지역 축만
        if GEO.search(al) and not geo_ok:
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
            if s <= rev * 1.12 or len(mem) <= 2:    # 부문끼리 사고판 몫(내부 거래)만큼은 합이 조금 클 수 있다
                break
            if generic:
                mem.pop(generic.pop(), None)
                continue
            # 다른 멤버들의 합과 같은 멤버(상위 범주)를 찾아 뺀다
            vals = sorted(mem.items(), key=lambda x: -x[1])
            drop = None
            for m, v in vals:
                rest = s - v
                if abs(rest - rev) / rev < 0.1:
                    drop = m
                    break
            mem.pop(drop or vals[0][0])
        s = sum(mem.values())
        if len(mem) < 2 or not (rev * 0.75 <= s <= rev * 1.45):
            continue
        geo = sum(1 for m in mem if GEO_M.search(L.get(m, "") or m)) / len(mem)          # 지역·거래 형태로 나눈 축은 뒤로
        if re.search(r"StatementBusinessSegmentsAxis", a):
            geo = 0                                   # 회사가 정한 사업 부문 (맥도날드 '미국·해외 직영·해외 라이선스' 처럼 이름이 지역이어도 부문이다)
        if geo >= 0.5 and not geo_ok:
            continue                              # 지역별·거래 형태별(재화/용역)은 '매출 종류'로 쓰지 않는다
        score = abs(s / rev - 1) + (0.0 if re.search(r"Product|Business|Segment|부문|제품", a + L.get(a, "")) else 0.05) + (0.03 if tot else 0) + geo * 0.5
        if best is None or score < best[0]:
            best = (score, a, mem)
    if not best:
        return []
    merged = {}
    for m, v in best[2].items():                  # 이름이 같은 멤버(표가 달라 두 번 나온 것)는 합친다
        k = clean_member(L.get(m), m)
        merged[k] = merged.get(k, 0) + v
    out = sorted(([k, v] for k, v in merged.items()), key=lambda x: -x[1])
    s = sum(v for _, v in out)
    if s < rev * 0.97:                            # 부문 합이 매출보다 모자라면 나머지는 '기타'
        out.append(["기타", rev - s])
    if len(out) > 7:
        out = out[:6] + [["기타", sum(v for _, v in out[6:])]]
    return out



OPEX_KO = {"ResearchAndDevelopmentExpense": "연구개발비", "SellingGeneralAndAdministrativeExpense": "판매·관리비", "SellingAndMarketingExpense": "마케팅비",
           "MarketingExpense": "마케팅비", "GeneralAndAdministrativeExpense": "일반관리비", "FulfillmentExpense": "물류·배송비", "TechnologyAndInfrastructureExpense": "기술·인프라",
           "TechnologyAndContentExpense": "기술·콘텐츠", "RestructuringCharges": "구조조정비", "AmortizationOfIntangibleAssets": "무형자산 상각", "SellingExpense": "판매비",
           "DepreciationDepletionAndAmortization": "감가상각비", "OtherCostAndExpenseOperating": "기타 영업비용", "LaborAndRelatedExpense": "인건비",
           "AdvertisingExpense": "광고비", "MarketingAndAdvertisingExpense": "마케팅·광고", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost": "연구개발비"}


def _fit_opex(out, val):
    """영업비용(매출총이익 - 영업이익)과 맞춘다 — 모자라면 '기타 영업비용', 넘치면 버린다"""
    if val.get("gross") is None or val.get("op") is None:
        return out
    opex = val["gross"] - val["op"]
    s = sum(v for _, v in out)
    if opex <= 0 or s > opex * 1.01:
        return []
    if opex - s > opex * 0.01:
        out = out + [["기타 영업비용", opex - s]]
    return out


def opex_items(ctx, facts, per, base_ok, CAL, L, us, val):
    vals = {}
    for n, c, v in facts:
        p = ctx[c]
        if (p["start"], p["end"]) == per and base_ok(p) and n not in vals:
            vals[n] = v
    got = _opex_cal(vals, CAL, L, us) if CAL else []
    if us:
        if got:
            got = _fit_opex(got, val)
        if not got:
            got = _opex_cal(vals, CAL, L, us, via_op=True) if CAL else []      # 영업비용 합계 줄이 없는 회사(MSFT 등): 영업이익 = 매출총이익 - 각 비용
            got = _fit_opex(got, val) if got else []
        if not got:                                                          # 계산 링크가 없거나 안 맞으면 알려진 비용 태그로
            pick = ["ResearchAndDevelopmentExpense", "SellingAndMarketingExpense", "MarketingAndAdvertisingExpense", "GeneralAndAdministrativeExpense",
                    "FulfillmentExpense", "TechnologyAndInfrastructureExpense"]
            if not any("us-gaap:" + k in vals for k in ("SellingAndMarketingExpense", "GeneralAndAdministrativeExpense")):
                pick.append("SellingGeneralAndAdministrativeExpense")
            out = [[OPEX_KO.get(k, k), vals["us-gaap:" + k]] for k in pick if vals.get("us-gaap:" + k, 0) > 0]
            out.sort(key=lambda x: -x[1])
            got = _fit_opex(out, val) if len(out) >= 2 or (len(out) == 1 and val.get("gross") is not None and (val["gross"] - val["op"]) - out[0][1] > (val["gross"] - val["op"]) * 0.05) else []
        return got if len(got) >= 2 else []
    return got


def _opex_cal(vals, CAL, L, us, via_op=False):
    parents = (["us-gaap:OperatingExpenses", "us-gaap:CostsAndExpenses", "us-gaap:OperatingCostsAndExpenses"] if us
               else ["dart:TotalSellingGeneralAdministrativeExpenses", "ifrs-full:SellingGeneralAndAdministrativeExpense"])
    if via_op:
        parents = ["us-gaap:OperatingIncomeLoss"]
    skip = {"us-gaap:CostOfRevenue", "us-gaap:CostOfGoodsAndServicesSold", "us-gaap:CostOfGoodsSold", "us-gaap:CostOfServices", "ifrs-full:CostOfSales",
            "us-gaap:GrossProfit", "us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:OperatingExpenses", "us-gaap:CostsAndExpenses"}
    for par in parents:
        kids = [(k, w) for k, w in CAL.get(par, []) if k in vals and k not in skip and (w < 0 if via_op else w > 0)]
        if len(kids) < 2:
            continue
        out = []
        for k, w in kids:
            nm = k.split(":")[-1]
            lab = OPEX_KO.get(nm) or re.sub(r"\\s*\\[.*?\\]\\s*$", "", L.get(k, "")) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", nm)
            out.append([lab, vals[k]])
        out = [x for x in out if x[1] > 0]
        out.sort(key=lambda x: -x[1])
        if len(out) >= 2:
            return out[:6]
    return []


WHY = ""


def from_instance(text, labtext, us, caltext=""):
    ctx, facts = XD.parse(text)
    L = XD.labels(labtext) if labtext else {}
    CAL = XD.calc(caltext) if caltext else {}
    if us:
        base_dim = lambda d: False                              # noqa: E731
        base_ok = lambda p: not p["dims"]                       # noqa: E731
        N = {"rev": ["us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:SalesRevenueNet",
                     "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "us-gaap:RegulatedAndUnregulatedOperatingRevenue"],   # 뒤 둘: 앞 셋이 없는 회사만 (운송·전력 등)
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
    global WHY
    per = pick_period(ctx, facts, set(N["rev"]), base_ok)
    if not per:
        WHY = "매출 기간 없음 (facts %d)" % len(facts)
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
    if us:                                          # 소수주주 몫 포함 순이익(ProfitLoss) — 실적 탭은 이 줄을 쓰는 회사가 있어 대조용으로 남긴다
        for n, c, v in facts:
            p = ctx[c]
            if n == "us-gaap:ProfitLoss" and (p["start"], p["end"]) == per and base_ok(p):
                val["ni_all"] = v
                break
    rev_tag = next((nm for nm in N["rev"] for n, c, v in facts if n == nm and (ctx[c]["start"], ctx[c]["end"]) == per and base_ok(ctx[c])), None)
    REVN = set(N["rev"][:3] if us else N["rev"]) | ({rev_tag} if rev_tag else set())   # 부문 매출은 총매출과 같은 태그(+기존 태그)로만
    if not val.get("rev") or val.get("op") is None or val.get("ni") is None:
        WHY = "빠진 값 %s · 기간 %s" % ([k for k in ("rev", "op", "ni") if val.get(k) is None], per)
        return None
    if val.get("gross") is None and val.get("cogs") is not None:
        val["gross"] = val["rev"] - val["cogs"]
    if val.get("cogs") is None and val.get("gross") is not None:
        val["cogs"] = val["rev"] - val["gross"]
    bd = base_dim if not us else (lambda d: False)
    cum = None                                    # 같은 날 끝나는 누적 기간(1~6월 등)
    for n, c, v in facts:
        p = ctx[c]
        if n in N["rev"] and p["end"] == per[1] and p["start"] < per[0] and base_ok(p):
            if cum is None or p["start"] < cum[0][0]:
                cum = ((p["start"], p["end"]), v)

    def find(geo):
        sg = segments(ctx, facts, REVN, per, val["rev"], L, bd, geo, None if us else want)
        if cum:                                   # 누적 기간 부문 매출 (원래 금액) — 앞 보고서 누적을 빼서 이번 3개월 실제 값을 구하려고 남긴다
            try:
                sc0 = segments(ctx, facts, REVN, cum[0], cum[1], L, bd, geo, None if us else want)
                if sc0:
                    val["cum_segs_geo" if geo else "cum_segs"] = [[n, v] for n, v in sc0]
            except Exception:                     # noqa: BLE001
                pass
        if sg or not cum:
            return sg, ""
        sc = segments(ctx, facts, REVN, cum[0], cum[1], L, bd, geo, None if us else want)   # 부문 매출이 누적으로만 있으면 그 비중으로 나눈다
        if not sc:
            return [], ""
        k = val["rev"] / sum(v for _, v in sc)
        return [[n, v * k] for n, v in sc], "매출 종류는 " + q_label(*cum[0]).split(" ")[-1] + " 비중"

    segs, note = find(False)                      # 1) 제품·사업 부문
    if not segs:
        segs, note = find(True)                   # 2) 없으면 지역별 (미주·유럽·중국·국내 …)
        if segs:
            val["seg_kind"] = "지역"
    if note:
        val["seg_note"] = note
    val["segs"] = segs
    if cum:                                       # 누적 매출 — 보고서 원문의 '매출 현황' 표가 누적(1~9월 등)으로만 있을 때 비중을 구하려고
        val["cum_rev"], val["cum_lab"] = cum[1], q_label(*cum[0]).split(" ")[-1]
    # 영업비용 세부 — 계산 링크베이스에서 영업비용(또는 판관비)의 자식 항목들
    val["items"] = opex_items(ctx, facts, per, base_ok, CAL, L, us, val)
    val["start"], val["end"] = per
    val["period"] = q_label(*per)
    return val


# ------------------------------------------------------------------ 국내: 사업보고서(연간)의 판관비 세부 → 묶어서 비율로
SGA_CAT = [("연구개발비", r"OrdinaryDevelopment|ExperimentalResearch|ResearchAndDevelopment"),
           ("판매보증비", r"Warranty"),
           ("광고·판촉비", r"Advertising|SalesPromotion|Marketing"),
           ("인건비", r"SalariesWages|Bonus|Severance|EmployeeBenefits|Retirement|Wages"),
           ("수수료·용역비", r"Commission|Outsourcing|ServiceFee"),
           ("운반·수출비", r"Freight|ExportOverall|Transportation|Storage|Distribution"),
           ("감가상각비", r"Depreciation|Amortisation|Amortization")]


def kr_sga_mix(text):
    """연간 판관비 세부를 몇 묶음으로 → {묶음: 비율}, 판관비 합계 대비. 세부가 합계의 60% 미만이면 None"""
    ctx, facts = XD.parse(text)
    cons = any(m.endswith("ConsolidatedMember") for p in ctx.values() for a, m in p["dims"])
    want = "ConsolidatedMember" if cons else "SeparateMember"
    gen = lambda a, m: "ConsolidatedAndSeparate" in a or re.search(r"CarryingAmount|ReportedAmount|Disclos", a + m)   # 공시금액 같은 일반 축은 허용  # noqa: E731
    ok = lambda p: all(gen(a, m) for a, m in p["dims"]) and (not p["dims"] or any(m.endswith(want) for a, m in p["dims"]))  # noqa: E731
    ann = [ctx[c] for n, c, v in facts if (ctx[c].get("start") or "")[5:] == "01-01" and ctx[c]["end"][5:] == "12-31"]
    if not ann:
        return {"err": "연간 기간 없음"}
    end = max(p["end"] for p in ann)
    vals = {}
    for n, c, v in facts:
        p = ctx[c]
        if p["end"] == end and (p.get("start") or "")[5:] == "01-01" and ok(p) and n not in vals:
            vals[n] = v
    tot = vals.get("dart:TotalSellingGeneralAdministrativeExpenses") or vals.get("ifrs-full:SellingGeneralAndAdministrativeExpense")
    if not tot or tot <= 0:
        return {"err": "판관비 합계 없음 %d" % len(vals)}
    det = {n: v for n, v in vals.items() if v > 0 and "Total" not in n and "TableOfItems" not in n and "ExceptFor" not in n
           and (n.endswith("SellingGeneralAdministrativeExpenses") or n.split(":")[-1] in ("SalariesWages", "ProvisionForSeveranceIndemnities"))}
    if sum(det.values()) < tot * 0.6:
        return {"err": "세부 부족 %.2f %d" % (sum(det.values()) / tot, len(det))}
    cat = {}
    for n, v in det.items():
        k = next((c for c, rx in SGA_CAT if re.search(rx, n.split(":")[-1])), None)
        if k:
            cat[k] = cat.get(k, 0) + v
    return {"year": end[:4], "mix": {k: v / tot for k, v in cat.items()}}


def split_sga(sga, mix, keep=3):
    """분기 판관비를 연간 비율로 나눔 → 큰 묶음 keep 개 + 기타"""
    if not sga or not mix or "mix" not in mix:
        return []
    top = sorted(mix["mix"].items(), key=lambda x: -x[1])[:keep]
    top = [(k, r) for k, r in top if r >= 0.04]
    out = [[k, sga * r] for k, r in top]
    rest = sga - sum(v for k, v in out)
    if rest > sga * 0.02:
        out.append(["기타 판관비", rest])
    return out if len(out) >= 2 else []
