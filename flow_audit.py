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


def _tables(doc):
    """원문의 표마다 (줄들, 단위) — 단위는 표 바로 앞 글에서 읽는다(표마다 다를 수 있다)"""
    out = []
    for m in re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I):
        before = doc[max(0, m.start() - 900):m.start()]
        out.append((P.rows_of(m.group(1)), P.unit_of(before + m.group(1)[:300]), re.sub(r"<[^>]+>", " ", before)[-300:]))
    return out


TOTAL_RX = re.compile(r"^(합계|계|총계|소계|합\s*계|총\s*계)$")


def _breakdown(tables, target, total_rx, keep, drop, min_rows=2, tol=0.02):
    """합계(또는 합)가 target(원)과 맞는 표에서 항목들 → [[이름, 원], ...]. 못 찾으면 []"""
    best = None
    if not target or target <= 0:
        return []
    for rows, u, ctx in tables:
        items, tot = [], None
        for r in rows:
            if not r:
                continue
            n = P.acct(r[0])
            v = P.first_amount(r)
            if v is None or not n:
                continue
            if TOTAL_RX.match(n) or total_rx.search(n):
                if tot is None:
                    tot = v * u
                continue
            if drop.search(n) or not keep.search(n):
                continue
            items.append([n, v * u])
        items = [x for x in items if x[1] > 0]
        if len(items) < min_rows:
            continue
        s = sum(v for _, v in items)
        ok_tot = tot is not None and abs(abs(tot) - target) <= target * tol
        ok_sum = abs(s - target) <= target * tol
        if not (ok_sum or (ok_tot and target * 0.9 <= s <= target * 1.1)):
            continue
        score = abs(s - target) / max(target, 1)
        if best is None or score < best[0]:
            best = (score, items)
    return best[1] if best else []


REV_KEEP = re.compile(r"(매출|수익|수입|수수료)$|매출액$")
REV_DROP = re.compile(r"^지급|판매수수료|잡수익|잡이익|고객과의\s*계약|기타\s*원천|원가|총이익|영업외|이자|금융|배당|기타수익|잡이익|환|평가|처분|지분법|법인세|시점|기간에\s*걸쳐|특수관계|채권|선수|미수|충당")
SGA_KEEP = re.compile(r".")
SGA_DROP = re.compile(r"^(판매비와관리비|판매비와일반관리비|영업비용|매출원가)$|원가|합계|소계")


def _group(items, total, label_rest):
    """판관비 세부 → 묶음 상위 3 + 나머지"""
    cat, other = {}, 0.0
    for n, v in items:
        k = next((c for c, rx in CAT if re.search(rx, n)), None)
        if k:
            cat[k] = cat.get(k, 0) + v
        else:
            other += v
    if not cat:
        return []
    s = sum(cat.values()) + other
    k = total / s if s else 1
    top = sorted(cat.items(), key=lambda x: -x[1])[:3]
    out = [[c, v * k] for c, v in top if v > 0]
    rest = total - sum(v for _, v in out)
    if rest > total * 0.02:
        out.append([label_rest, rest])
    return out if len(out) >= 2 else []


def _segments(items, rev):
    """매출 구분(제품·상품·용역 …) → 큰 순서, 6개 넘으면 기타로"""
    nm = lambda n: re.sub(r"\(.*?\)", "", n).strip()      # noqa: E731
    merged = {}
    for n, v in items:
        merged[nm(n)] = merged.get(nm(n), 0) + v
    out = sorted(([k, v] for k, v in merged.items()), key=lambda x: -x[1])
    if len(out) > 6:
        out = out[:5] + [["기타", sum(v for _, v in out[5:])]]
    sm = sum(v for _, v in out)
    if sm <= 0:
        return []
    k = rev / sm
    return [[n, v * k] for n, v in out] if len(out) >= 2 else []


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
        # 주석에서 매출 구분 · 판관비(또는 영업비용) 세부 — 합계가 손익계산서 숫자와 맞는 표만 쓴다
        tables = _tables(doc)
        gross = d["gross"] if d["gross"] is not None else d["rev"]
        opex = gross - d["op"]
        d["segs"] = _segments(_breakdown(tables, d["rev"], re.compile(r"^(매출액|영업수익|수익|매출)(합계)?$"), REV_KEEP, REV_DROP), d["rev"])
        ref = d["sga"] if d["sga"] else opex
        det = _breakdown(tables, ref, re.compile(r"^(판매비와관리비|판매비와일반관리비|영업비용)(합계)?$"), SGA_KEEP, SGA_DROP, min_rows=4) if ref and ref > 0 else []
        d["items"] = _group(det, ref, "기타 판관비" if d["cogs"] is not None else "기타 영업비용")
        y, m = per
        end = date(y, m, calendar.monthrange(y, m)[1])
        py, pm = (y - 1, m)
        start = date(py, pm, calendar.monthrange(py, pm)[1]) + timedelta(days=1)    # 1년 전 결산일 다음 날
        d["start"], d["end"] = start.isoformat(), end.isoformat()
        d["period"] = "'%s년" % str(y)[2:]
        d["report"] = r["report_nm"]
        d["src"] = r["rcept_no"]
        return d
    WHY = "손익 표를 못 읽음"
    return None
