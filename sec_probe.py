#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEC 원자료 들여다보기 (점검용, 파일은 바꾸지 않는다) — 2026-11 해외 값 점검.

  python3 sec_probe.py NVDA TPL LHX ...

종목마다: 액면분할 관련 태그 전부 · 주당배당금 사실(공시별) · 최근 분기 매출 사실(기간·공시별)을 찍는다.
워크플로 'SEC 원자료 점검' 에서 돌리고 로그로 본다.
"""
import sys
import collect_us as U

DPS_TAGS = ("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid")
REV_TAGS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax")


def rows(facts, tag):
    g = (facts.get("facts") or {}).get("us-gaap", {}).get(tag) or {}
    out = []
    for unit, lst in (g.get("units") or {}).items():
        for r in lst:
            out.append(dict(r, unit=unit))
    return out


def main():
    cmap = U.load_cik_map()
    for t in sys.argv[1:]:
        t = t.upper()
        info = cmap.get(t)
        ciks = None
        if t in U.CIK_OVERRIDE:
            ciks = ["%010d" % int(x) for x in U.CIK_OVERRIDE[t].split()]
        elif info:
            ciks = [info["cik"]]
        if not ciks:
            print("!", t, "CIK 없음"); continue
        facts = U.fetch_facts(ciks)
        if not facts:
            print("!", t, "자료 없음"); continue
        print("\n" + "=" * 70 + "\n" + t)
        g = (facts.get("facts") or {}).get("us-gaap", {})
        for tag in sorted(g):
            if "Split" in tag:
                for r in rows(facts, tag):
                    print("  SPLIT %-60s %s ~ %s  %s  %s %s filed %s" % (tag[:60], r.get("start"), r.get("end"), r.get("val"),
                                                                    r.get("form"), r.get("fp"), r.get("filed")))
        for tag in DPS_TAGS:
            for r in sorted(rows(facts, tag), key=lambda r: (r.get("end"), r.get("filed"))):
                if (r.get("end") or "") >= "2016":
                    print("  DPS %-40s %s ~ %s  %-8s fy%s %s %-5s filed %s" % (tag[:40], r.get("start"), r.get("end"), r.get("val"),
                                                                       r.get("fy"), r.get("fp"), r.get("form"), r.get("filed")))
        if len(sys.argv) > 1 and t in ("LHX", "HON", "OXY", "KLAC", "APTV", "WAT"):
            for tag in REV_TAGS:
                for r in sorted(rows(facts, tag), key=lambda r: (r.get("end"), r.get("filed"))):
                    if (r.get("end") or "") >= "2024-01":
                        print("  REV %-30s %s ~ %s  %14s fy%s %s %-5s filed %s" % (tag[:30], r.get("start"), r.get("end"), r.get("val"),
                                                                           r.get("fy"), r.get("fp"), r.get("form"), r.get("filed")))


if __name__ == "__main__":
    main()
