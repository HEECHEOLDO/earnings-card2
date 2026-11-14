#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 상장사 주주현황 → data/holders/{종목코드}.json  (주주현황 탭, 2026-11)

  python3 collect_holders.py 005930 257720     몇 종목만
  python3 collect_holders.py                   전 종목 (data/index.json 의 국내 종목) — 새 정기보고서가 나온 종목만 다시 받는다
  python3 collect_holders.py --force ...       이미 받은 보고서여도 다시

출처: 금융감독원 DART 오픈API (정기보고서 기준)
  hyslrSttus      최대주주 및 특수관계인 (보통주, 기말 보유 주식 수·지분율)
  stockTotqySttus 발행주식 총수 · 자기주식 수
  mrhlSttus       소액주주 (사업보고서에만 있는 경우가 많다 — 가장 최근 것을 찾아 쓴다)
  majorstock      5% 이상 대량보유 보고 (국민연금·자산운용사 등) — 보고자별 가장 최근 보고
정기보고서는 분기마다 나오므로 분기마다 저절로 바뀐다 (1분기 5월, 반기 8월, 3분기 11월, 사업 3월).
키: DART_API_KEY 또는 key.txt (collect.py 와 같다)
"""
import json
import os
import sys
from datetime import date

import collect as C

OUT = os.path.join("data", "holders")
# 보고서 코드: 사업 11011 · 반기 11012 · 1분기 11013 · 3분기 11014
REPORTS = [("11014", "3분기보고서", "09-30"), ("11012", "반기보고서", "06-30"),
           ("11013", "1분기보고서", "03-31"), ("11011", "사업보고서", "12-31")]


def n(v):
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:                             # noqa: BLE001
        return None


def rows_of(res):
    if not res or str(res.get("status")) != "000":
        return None
    return res.get("list") or None


def candidates(today):
    """새것부터: (연도, 보고서코드, 이름, 기준일)"""
    out = []
    for y in range(today.year, today.year - 3, -1):
        for code, nm, md in REPORTS:
            out.append((str(y), code, nm, "%d-%s" % (y, md)))
    return out


def latest(corp, endpoint, today):
    for y, rc, nm, asof in candidates(today):
        if asof > today.isoformat():
            continue
        rows = rows_of(C.api_get(endpoint, {"corp_code": corp, "bsns_year": y, "reprt_code": rc}))
        if rows:
            return rows, (y, rc, nm, asof)
    return None, None


def common(r):
    k = (r.get("stock_knd") or r.get("se") or "").replace(" ", "")
    return (not k) or ("보통" in k) or (k in ("-",))


def one(code, cm, today, force=False):
    corp = cm[code]["corp_code"]
    path = os.path.join(OUT, code + ".json")
    old = None
    if os.path.exists(path):
        old = json.load(open(path, encoding="utf-8"))

    major, rep = latest(corp, "hyslrSttus.json", today)
    if not major:
        return None, "최대주주 자료 없음"
    y, rc, rname, asof = rep
    if old and not force and old.get("asof") == asof and old.get("rcept_no") == (major[0].get("rcept_no") or ""):
        return old, "그대로"

    people = []
    for r in major:
        if not common(r) or (r.get("nm") or "").strip() in ("계", "합계", "-"):
            continue
        sh, pct = n(r.get("trmend_posesn_stock_co")), n(r.get("trmend_posesn_stock_qota_rt"))
        if not sh or not pct:
            continue
        people.append({"n": (r.get("nm") or "").strip(), "rel": (r.get("relate") or "").strip(),
                       "sh": int(sh), "pct": round(pct, 2)})
    people.sort(key=lambda x: -x["pct"])

    tot = rows_of(C.api_get("stockTotqySttus.json", {"corp_code": corp, "bsns_year": y, "reprt_code": rc})) or []
    issued = treasury = None
    for r in tot:
        se = (r.get("se") or "").replace(" ", "")
        if "보통" in se:
            issued = n(r.get("istc_totqy"))
            treasury = n(r.get("tesstk_co"))
    if issued is None:
        for r in tot:
            if "합계" in (r.get("se") or ""):
                issued, treasury = n(r.get("istc_totqy")), n(r.get("tesstk_co"))

    minor = None
    mr, mrep = latest(corp, "mrhlSttus.json", today)
    for r in mr or []:
        hc, rate = n(r.get("shrholdr_co")), n(r.get("hold_stock_rate"))
        if hc:
            minor = {"holders": int(hc), "pct": rate, "asof": mrep[3]}
            break

    five = {}
    ms = rows_of(C.api_get("majorstock.json", {"corp_code": corp})) or []
    for r in sorted(ms, key=lambda r: r.get("rcept_dt") or ""):
        who = (r.get("repror") or "").strip()
        pct = n(r.get("stkrt"))
        if who and pct is not None:
            five[who] = {"n": who, "pct": round(pct, 2), "dt": r.get("rcept_dt") or ""}
    big = [v for v in five.values() if v["pct"] >= 5]
    big.sort(key=lambda x: -x["pct"])

    out = {
        "name": cm[code]["name"], "asof": asof, "report": "%s %s" % (y, rname),
        "rcept_no": major[0].get("rcept_no") or "",
        "issued": int(issued) if issued else None, "treasury": int(treasury) if treasury else 0,
        "major": people, "five": big[:8], "minor": minor,
        "updated": today.isoformat(),
    }
    return out, "새로"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    C.API_KEY = C.get_key()
    cm = C.load_corp_map()
    if args:
        codes = args
    else:
        idx = json.load(open(os.path.join("data", "index.json"), encoding="utf-8"))
        items = idx.get("items") or idx
        codes = sorted(k for k in (items if isinstance(items, dict) else [x.get("code") for x in items]) if k in cm)
    os.makedirs(OUT, exist_ok=True)
    today = date.today()
    cnt = {}
    for i, code in enumerate(codes, 1):
        if code not in cm:
            cnt["코드 없음"] = cnt.get("코드 없음", 0) + 1
            continue
        got, why = one(code, cm, today, force)
        cnt[why] = cnt.get(why, 0) + 1
        if got and why == "새로":
            with open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8") as f:
                json.dump(got, f, ensure_ascii=False, separators=(",", ":"))
        if args:
            print(json.dumps(got, ensure_ascii=False)[:1500] if got else why)
        if C.ABORT:
            print("!! 중단:", C.ABORT)
            break
        if i % 100 == 0:
            print("  %d/%d %s" % (i, len(codes), cnt), flush=True)
    print("끝:", cnt)


if __name__ == "__main__":
    main()
