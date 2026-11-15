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
from datetime import date, timedelta

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
UL_VER = 2                                         # 비상장(감사보고서) 읽는 법이 바뀌면 올림 — 비상장만 다시
VER = 7                                            # 계산 방식이 바뀌면 올려서 다시 계산


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
    if gross - op < 0 or gross < 0:
        return False
    days = (date.fromisoformat(d["end"]) - date.fromisoformat(d["start"])).days
    if not (80 <= days <= 100 or 350 <= days <= 380):
        return False
    lim = 520 if (len(code) == 8 and code.isdigit()) else 200          # 비상장(감사보고서·연간)은 1년 넘게 기다린다
    return (TODAY - date.fromisoformat(d["end"])).days < lim            # 분기 끝 + 제출 기한(45~90일)보다 오래되면 뺌


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
FAILP = os.path.join(OUT, "_fail.json")                     # 못 읽은 회사 — 1주일 뒤에 다시


def time_left():
    return time.time() - T0 < MINUTES * 60


def recent_kr(days=12):
    """최근 정기보고서(분기·반기·사업)를 낸 회사 corp_code — 이 회사들만 새로 읽는다"""
    out = set()
    for p in range(1, 60):
        res = C.api_get("list.json", {"bgn_de": (TODAY - timedelta(days=days)).strftime("%Y%m%d"), "end_de": TODAY.strftime("%Y%m%d"),
                                      "pblntf_ty": "A", "page_no": p, "page_count": 100})
        if not res or res.get("status") != "000":
            break
        for r in res.get("list", []):
            out.add(r.get("corp_code"))
        if p >= int(res.get("total_page") or 1):
            break
    for p in range(1, 30):                                   # 감사보고서(비상장)
        res = C.api_get("list.json", {"bgn_de": (TODAY - timedelta(days=days)).strftime("%Y%m%d"), "end_de": TODAY.strftime("%Y%m%d"),
                                      "pblntf_ty": "F", "page_no": p, "page_count": 100})
        if not res or res.get("status") != "000":
            break
        for r in res.get("list", []):
            out.add(r.get("corp_code"))
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
        raw = U.get("https://www.sec.gov/Archives/edgar/daily-index/%d/QTR%d/form.%s.idx" % (d.year, (d.month - 1) // 3 + 1, d.strftime("%Y%m%d")))
        if not raw:
            continue
        for line in raw.decode("latin-1").splitlines():
            if line.startswith(("10-Q ", "10-K ", "10-Q/A", "10-K/A")):
                m = re.search(r"\s(\d{3,10})\s+\d{4}-?\d{2}-?\d{2}\s", line)
                if m:
                    out.add(int(m.group(1)))
    return out


def jl(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:                               # noqa: BLE001
        return d


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
        if d:
            d["unit"] = "억원"
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
    except Exception as e:                          # noqa: BLE001
        x, FX.WHY = None, "오류 %s" % e
    if x == "SAME":
        return job, "SAME", "", time.time() - t0
    d = scaled(x, 1e6) if x else None
    if not d:
        try:
            d = us_one(t, cik)
        except Exception:                           # noqa: BLE001
            d = None
        if d:
            d["xbrl_err"] = FX.WHY or "까닭 모름"
    if d:
        d["unit"] = "백만달러"
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
    for fn in os.listdir(OUT):
        if not fn.endswith(".json") or fn.startswith(("_", "index")):
            continue
        code = fn[:-5]
        if usable(code):
            d = jl(os.path.join(OUT, fn), {})
            m = d.get("market") or ("US" if not code.isdigit() else "UL" if len(code) == 8 else "KR")
            idx[code] = {"n": d.get("name") or code, "m": m, "p": d.get("period")}
    json.dump({"updated": TODAY.isoformat(), "items": idx}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
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

    def need(key, old, recent_hit):
        """0: 새 보고서 · 1: 아직 없음 · 2: 계산 방식이 바뀜 · None: 그대로"""
        if old and old.get("ver") == VER and not recent_hit:
            return None
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
                save(code, old, mk, old.get("name") or name)
            done["same"] += 1
        elif d:
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
            pr = need(code, old, info["corp_code"] in rk)
            if pr is not None:
                jobs.append((pr, i, "KR", code, info["corp_code"], old, mc[code].get("n")))
        for i, c in enumerate(ul):
            old = jl(os.path.join(OUT, c["code"] + ".json"))
            pr = need(c["code"], old, c["code"] in rk)
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
        n = run_pool(work_kr, jobs, W, on_kr, lambda: time_left() and C._call_count + done["calls"] < DART_MAX)
        print("  국내 %d/%d곳 처리 · 한 곳 평균 %.1f초 · DART 호출 %d" % (n, len(jobs), done["sec"] / max(1, n), done["calls"]), flush=True)
    if "--kr-only" not in sys.argv and time_left():
        ru = recent_us()
        print("최근 10-Q·10-K 낸 미국 회사 %d곳" % len(ru), flush=True)
        jobs = []
        for i, t in enumerate(us):
            cik = (jl(os.path.join("data", "us", t + ".json"), {}) or {}).get("cik")
            if not cik:
                continue
            old = jl(os.path.join(OUT, t + ".json"))
            pr = need(t, old, int(cik) in ru)
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
