#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 운용사·기관이 5% 넘게 들고 있는 상장사 → data/kr5.json (포트폴리오 탭 '국내 운용사')

  python3 collect_kr5.py                 7일 넘게 안 본 회사부터 차례로 (하루 한도 안에서)
  python3 collect_kr5.py --budget 3000   이번에 쓸 DART 호출 수
  python3 collect_kr5.py --build         호출 없이 kr5_raw.json 으로 kr5.json 만 다시 만든다

국내에는 미국 13F 처럼 보유 종목 전체를 내는 공시가 없다. 대신 한 회사 지분을 5% 넘게 가지면
'주식등의 대량보유상황보고서(5% 공시)'를 내야 하고, 1%p 이상 바뀌거나 5% 밑으로 내려가면 다시 낸다.
DART majorstock(대량보유 상황보고) API 는 '발행 회사' 단위로만 조회되므로, 상장사 전체를 돌며
보고자가 아래 FUNDS 인 보고서만 모은다. 회사·보고자마다 가장 최근 보고서가 지금 지분이다.

평가액 = 최근 보고 지분율 × 지금 시가총액(data/mcap.json). 5% 밑으로 내려간 마지막 보고는 '처분'으로 본다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

import collect as C

RAW = "data/kr5_raw.json"
OUT = "data/kr5.json"
REFRESH_DAYS = 7

# (키, 카드 제목, 보고자 이름에 들어가는 말들) — 이름의 공백·(주)·주식회사는 지우고 비교한다
FUNDS = [
    ("vip", "VIP자산운용", ["브이아이피자산운용", "VIP자산운용"]),
    ("shinyoung", "신영자산운용", ["신영자산운용"]),
    ("kivam", "한국투자밸류자산운용", ["한국투자밸류자산운용"]),
    ("truston", "트러스톤자산운용", ["트러스톤자산운용"]),
    ("align", "얼라인파트너스", ["얼라인파트너스"]),
    ("kcgi", "KCGI", ["케이씨지아이", "KCGI"]),
    ("must", "머스트자산운용", ["머스트자산운용"]),
    ("nps_kr", "국민연금 (국내)", ["국민연금공단", "국민연금기금"]),
]


def norm(s):
    s = re.sub(r"\(주\)|㈜|주식회사|\s", "", str(s or ""))
    return s.upper()


def which_fund(repror):
    n = norm(repror)
    for key, _, pats in FUNDS:
        if any(norm(p) in n for p in pats):
            return key
    return None


def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                          # noqa: BLE001
        return default


def fetch(budget):
    raw = load_json(RAW, {"checked": {}, "rows": {}})
    mc = load_json("data/mcap.json", {}).get("stocks", {})
    C.API_KEY = C.get_key()
    cmap = C.load_corp_map()
    today = dt.date.today()
    def age(code):
        d = raw["checked"].get(code)
        return (today - dt.date.fromisoformat(d)).days if d else 10 ** 6
    todo = sorted((c for c in mc if c in cmap and age(c) >= REFRESH_DAYS), key=lambda c: (-age(c), -mc[c].get("c", 0)))
    C.log("상장사 %d곳 중 이번에 볼 곳 %d곳 (한도 %d회)" % (len(mc), len(todo), budget))
    done = 0
    for code in todo[:budget]:
        res = C.api_get("majorstock.json", {"corp_code": cmap[code]["corp_code"]})
        if C.ABORT:
            break
        if res is None:
            continue
        st = str(res.get("status", ""))
        rows = []
        if st == "000":
            latest = {}
            for r in res.get("list", []):
                k = which_fund(r.get("repror"))
                if not k:
                    continue
                key = (r.get("rcept_dt") or "", r.get("rcept_no") or "")
                if k not in latest or key > latest[k][0]:
                    latest[k] = (key, r)
            for k, (_, r) in latest.items():
                rows.append({"fund": k, "repror": r.get("repror"), "date": r.get("rcept_dt"),
                             "rcept_no": r.get("rcept_no"), "rate": num(r.get("stkrt")),
                             "shares": num(r.get("stkqy")), "reason": (r.get("report_resn") or "")[:60]})
        elif st != "013":                      # 013 = 보고서 없음
            C.log("  ! %s %s" % (code, res.get("message")))
            continue
        if rows:
            raw["rows"][code] = rows
        else:
            raw["rows"].pop(code, None)
        raw["checked"][code] = today.isoformat()
        done += 1
        if done % 200 == 0:
            C.log("  %d곳 확인" % done)
            save(RAW, raw)
    save(RAW, raw)
    C.log("확인 %d곳 · 호출 %d회%s" % (done, C._call_count, (" · 중단: " + C.ABORT) if C.ABORT else ""))
    return raw


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def build(raw):
    mcj = load_json("data/mcap.json", {})
    mc = mcj.get("stocks", {})
    asof = mcj.get("asof") or dt.date.today().isoformat()
    checked = raw.get("checked", {})
    funds = {}
    for key, title, pats in FUNDS:
        hs, entity = [], None
        for code, rows in raw.get("rows", {}).items():
            if code not in mc:
                continue                       # 상장폐지·합병
            for r in rows:
                if r["fund"] != key or not r.get("rate") or r["rate"] < 5:
                    continue                   # 5% 밑으로 내려간 마지막 보고 = 처분
                cap = mc[code].get("c") or 0
                entity = entity or r.get("repror")
                hs.append({"name": mc[code].get("n") or code, "code": code, "stake": round(r["rate"], 2),
                           "value": round(cap * r["rate"] / 100, 1), "date": r.get("date"),
                           "logo": ("kr/" + code) if os.path.exists("logo/kr/%s.png" % code) else None})
        hs.sort(key=lambda h: -h["value"])
        total = sum(h["value"] for h in hs)
        for h in hs:
            h["weight"] = round(h["value"] / total * 100, 2) if total else 0
        funds[key] = {"title": title, "entity": entity or pats[0], "kind": "kr5", "period": asof,
                      "count": len(hs), "total_value": round(total, 1), "unit": "억원", "holdings": hs}
    out = {"updated": dt.date.today().isoformat(), "asof": asof, "source": "DART 주식등의 대량보유상황보고서",
           "coverage": "%d/%d" % (sum(1 for c in mc if c in checked), len(mc)), "funds": funds}
    save(OUT, out)
    C.log("%s 저장 — %s" % (OUT, ", ".join("%s %d종목" % (f["title"], f["count"]) for f in funds.values())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args()
    raw = load_json(RAW, {"checked": {}, "rows": {}}) if a.build else fetch(a.budget)
    build(raw)
    if C.ABORT and not a.build:
        sys.exit(0)                            # 한도 초과는 다음 날 이어서 하면 된다


if __name__ == "__main__":
    main()
