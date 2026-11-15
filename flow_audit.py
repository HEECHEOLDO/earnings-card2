#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""돈의 흐름 카드 — 감사보고서만 내는 비상장 회사. 가장 최근 감사보고서 원문(손익계산서·판관비 주석)을 읽는다.
collect_flow.py 가 부른다. 값은 원 단위로 돌려준다(나누기는 부르는 쪽)."""
import re
from datetime import date, timedelta
import calendar

import collect_audit as A
import probe_audit as P

COGS = ["매출원가", "영업원가", "매출원가및영업비용"]
GROSS = ["매출총이익", "매출총이익(손실)", "매출총손익", "매출총손실"]
SGA = ["판매비와관리비", "판매비와일반관리비", "판매관리비", "판매비및관리비", "판매비와관리비합계"]
TAX = ["법인세비용", "법인세비용(수익)", "법인세비용(이익)", "법인세수익(비용)", "법인세등", "법인세비용(환급)"]
CAT = [("인건비", r"급여|상여|퇴직|복리후생|인건비|임금"), ("광고·판촉비", r"광고|판매촉진|판촉|마케팅|홍보"), ("수수료·용역비", r"수수료|용역"),
       ("임차료", r"임차료|사용권|리스료"), ("감가상각비", r"감가상각|상각비"), ("운반·물류비", r"운반|물류|보관|배송|포장"),
       ("연구개발비", r"연구|개발비|경상"), ("판매보증비", r"보증")]
WHY = ""


def _sga_items(tables, sga):
    """판관비 주석 표 — 급여·지급수수료 같은 줄이 여럿 있고 합계가 판관비와 맞는 표"""
    for rows in tables:
        names = [P.acct(r[0]) for r in rows if r]
        if sum(1 for n in names if re.search(r"급여|지급수수료|감가상각|광고|임차료|복리후생", n)) < 3:
            continue
        cat, tot, other = {}, None, 0.0
        for r in rows:
            if not r:
                continue
            n = P.acct(r[0])
            v = P.first_amount(r)
            if v is None:
                continue
            if re.fullmatch(r"(합계|계|판매비와관리비(합계)?|총계)", n):
                tot = v
                continue
            k = next((c for c, rx in CAT if re.search(rx, n)), None)
            if k:
                cat[k] = cat.get(k, 0) + v
            else:
                other += v
        s = sum(cat.values()) + other
        if not cat or s <= 0:
            continue
        ref = sga or tot or s
        if abs(s - ref) / ref > 0.05 and not (tot and abs(tot - ref) / ref < 0.03):
            continue                              # 다른 표(제조원가명세서 등)
        k = ref / s                               # 단위·반올림 차이는 비율로 맞춘다
        top = sorted(cat.items(), key=lambda x: -x[1])[:3]
        out = [[c, v * k] for c, v in top if v > 0]
        rest = ref - sum(v for _, v in out)
        if rest > ref * 0.02:
            out.append(["기타 판관비", rest])
        return out if len(out) >= 2 else []
    return []


def flow(code):
    """가장 최근 감사보고서 한 해 → dict(rev, cogs, gross, sga, op, tax, ni, items, start, end, period, src) 원 단위"""
    global WHY
    WHY = ""
    by = A.list_reports([code], date.today().year - 2)
    if not by:
        WHY = "감사보고서 없음"
        return None
    per = sorted(by)[-1]
    want = any("연결" in r["report_nm"] or r["_kind"] == "A" for r in by[per])
    r = A.choose(by[per], want)
    doc = P.fetch_doc(r["rcept_no"])
    if not doc:
        WHY = "원문을 못 받음"
        return None
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I))
    rowsets = [P.rows_of(m.group(1)) for m in tabs]
    for i, rows in enumerate(rowsets):
        rev = A.pick2(rows, P.REV, False)
        if not rev:
            continue
        grab = rows + [x for nxt in rowsets[i + 1:i + 3] for x in nxt]      # 표가 둘로 나뉜 경우
        op, ni = A.pick2(grab, P.OP, True), A.pick2(grab, P.NI, True)
        if not op or not ni:
            continue
        cogs, gross = A.pick2(rows, COGS, True), A.pick2(rows, GROSS, True)
        sga, tax = A.pick2(grab, SGA, True), A.pick2(grab, TAX, False)
        before = doc[max(0, tabs[i].start() - 1500):tabs[i].start()]
        u = P.unit_of(before + doc[tabs[i].start():tabs[i].start() + 400])
        v = lambda x: None if not x or x[1] is None else x[1] * u      # noqa: E731
        d = {"rev": v(rev), "cogs": v(cogs), "gross": v(gross), "sga": v(sga), "op": v(op), "tax": v(tax), "ni": v(ni)}
        if d["cogs"] is not None and d["cogs"] < 0:
            d["cogs"] = -d["cogs"]
        if d["sga"] is not None and d["sga"] < 0:
            d["sga"] = -d["sga"]
        if d["gross"] is None and d["cogs"] is not None:
            d["gross"] = d["rev"] - d["cogs"]
        if d["cogs"] is None and d["gross"] is not None:
            d["cogs"] = d["rev"] - d["gross"]
        if not d["rev"] or d["rev"] <= 0:
            continue
        # 판관비 주석 (단위는 표마다 다를 수 있어 비율로 맞춘다)
        sg_ref = d["sga"] if d["sga"] else ((d["gross"] - d["op"]) if d["gross"] is not None else None)
        items = _sga_items(rowsets, sg_ref / u if sg_ref else None)
        d["items"] = [[n, x * u] for n, x in items]
        y, m = per
        end = date(y, m, calendar.monthrange(y, m)[1])
        py, pm = (y - 1, m)
        start = date(py, pm, calendar.monthrange(py, pm)[1]) + timedelta(days=1)    # 1년 전 결산일 다음 날
        d["start"], d["end"] = start.isoformat(), end.isoformat()
        d["period"] = "'%s년" % str(y)[2:]
        d["report"] = r["report_nm"]
        d["src"] = r["rcept_no"]
        d["segs"] = []
        return d
    WHY = "손익 표를 못 읽음"
    return None
