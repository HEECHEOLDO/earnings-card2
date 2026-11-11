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
import io
import zipfile
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


def ymd(d):
    d = re.sub(r"\D", "", str(d or ""))
    return "%s-%s-%s" % (d[:4], d[4:6], d[6:8]) if len(d) == 8 else ""


def dec(b):
    """예전 공시 본문은 EUC-KR(cp949)이다."""
    head = b[:200].decode("ascii", "ignore").lower()
    for enc in (["euc-kr", "cp949"] if "euc-kr" in head else []) + ["utf-8", "cp949"]:
        try:
            return b.decode("cp949" if enc == "euc-kr" else enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


def parse_doc_rate(rno):
    """5% 보고서 본문에서 '이번 보고서' 보유주식 수·보유비율을 읽는다 (요약정보 표)."""
    blob = C.api_get("document.xml", {"rcept_no": rno}, raw=True) or b""
    if blob[:2] != b"PK":
        return None
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for nm in z.namelist():
            t = re.sub(r"<[^>]+>", " ", dec(z.read(nm)))
            t = re.sub(r"\s+", " ", t)
            m = re.search(r"보유주식등의 수 및 보유비율 보유주식등의 수 보유비율 직전 보고서 \S+ \S+ "
                          r"이번 보고서 ([\d,]+) ([\d.]+)", t)
            if m:
                return num(m.group(1)), num(m.group(2))
    return None


def deep_old(code, corp_code, have):
    """majorstock API 는 최근 2년치만 준다. 그보다 오래 바뀌지 않은 지분(국민연금의 삼성전자 등)은
    공시 목록(list.json)에서 그 보고자의 마지막 5% 보고서를 찾아 본문에서 지분율을 읽는다."""
    latest, page = {}, 1
    while True:
        res = C.api_get("list.json", {"corp_code": corp_code, "bgn_de": "20000101",
                                      "end_de": dt.date.today().strftime("%Y%m%d"),
                                      "pblntf_detail_ty": "D001", "page_count": 100, "page_no": page})
        if not res or str(res.get("status")) != "000":
            return [] if res and str(res.get("status")) == "013" else None
        for r in res.get("list", []):
            k = which_fund(r.get("flr_nm"))
            if k and k not in have and (k not in latest or r["rcept_no"] > latest[k]["rcept_no"]):
                latest[k] = r
        if page >= int(res.get("total_page") or 1) or page >= 5:
            break
        page += 1
    rows = []
    for k, r in latest.items():
        got = parse_doc_rate(r["rcept_no"])
        if C.ABORT:
            return None
        if got:
            rows.append({"fund": k, "repror": r.get("flr_nm"), "date": ymd(r.get("rcept_dt")), "rcept_no": r["rcept_no"],
                         "rate": got[1], "shares": got[0], "reason": "본문(" + (r.get("report_nm") or "")[:30] + ")"})
        else:
            C.log("  ! %s %s 본문에서 지분율을 못 읽음" % (code, r["rcept_no"]))
    return rows


T0 = dt.datetime.now()
MAX_MIN = 70                                    # 워크플로 제한 시간 안에 저장하고 끝내도록


def late():
    return (dt.datetime.now() - T0).total_seconds() > MAX_MIN * 60


def fetch(budget):
    raw = load_json(RAW, {"checked": {}, "rows": {}})
    raw.setdefault("deep", {})
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
    for code in todo:
        if C._call_count >= budget or late():
            break
        res = C.api_get("majorstock.json", {"corp_code": cmap[code]["corp_code"]})
        if C.ABORT:
            break
        if res is None:
            continue
        st = str(res.get("status", ""))
        if st not in ("000", "013"):           # 013 = 보고서 없음
            C.log("  ! %s %s" % (code, res.get("message")))
            continue
        latest = {}
        for r in (res.get("list", []) if st == "000" else []):
            k = which_fund(r.get("repror"))
            if not k:
                continue
            key = (r.get("rcept_dt") or "", r.get("rcept_no") or "")
            if k not in latest or key > latest[k][0]:
                latest[k] = (key, r)
        # 최근 2년 창에서 빠진 보고자는 예전 줄을 그대로 둔다 (빠졌다고 판 게 아니다 — 5% 밑으로 내려가면 보고가 나온다)
        rows = {r["fund"]: r for r in raw["rows"].get(code, [])}
        for k, (_, r) in latest.items():
            rows[k] = {"fund": k, "repror": r.get("repror"), "date": ymd(r.get("rcept_dt")),
                       "rcept_no": r.get("rcept_no"), "rate": num(r.get("stkrt")),
                       "shares": num(r.get("stkqy")), "reason": (r.get("report_resn") or "")[:60]}
        if rows:
            raw["rows"][code] = list(rows.values())
        raw["checked"][code] = today.isoformat()
        done += 1
        if done % 200 == 0:
            C.log("  %d곳 확인" % done)
            save(RAW, raw)
    # 오래된 지분 한 번씩 (회사마다 1번, 공시 목록 + 찾은 보고서 본문)
    deep_todo = sorted((c for c in mc if c in cmap and c not in raw["deep"]), key=lambda c: -mc[c].get("c", 0))
    dn = 0
    for code in deep_todo:
        if C.ABORT or C._call_count >= budget or late():
            break
        have = {r["fund"] for r in raw["rows"].get(code, [])}
        add = deep_old(code, cmap[code]["corp_code"], have)
        if add is None:
            continue
        if add:
            raw["rows"][code] = raw["rows"].get(code, []) + add
        raw["deep"][code] = today.isoformat()
        dn += 1
        if dn % 200 == 0:
            C.log("  오래된 지분 %d곳 확인" % dn)
            save(RAW, raw)
    save(RAW, raw)
    C.log("확인 %d곳 · 오래된 지분 %d곳 (남은 %d곳) · 호출 %d회%s" % (done, dn, len(deep_todo) - dn, C._call_count,
          (" · 중단: " + C.ABORT) if C.ABORT else ""))
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
    ap.add_argument("--debug", default="", help="쉼표로 종목코드: 응답 요약만 찍는다")
    a = ap.parse_args()
    if a.debug.startswith("fs:"):
        C.API_KEY = C.get_key()
        cmap = C.load_corp_map()
        for spec in a.debug[3:].split(","):
            code, y, rc = spec.split(":")
            rows = C.fetch_fs(cmap[code]["corp_code"], int(y), rc) or []
            C.log("== %s %s %s %s행" % (code, y, rc, len(rows)))
            for r in rows:
                if r.get("sj_div") in ("IS", "CIS"):
                    C.log("   %s|%s|%s|%s|%s" % (r.get("sj_div"), r.get("ord"), (r.get("account_id") or "")[:60],
                                               r.get("account_nm"), r.get("thstrm_amount")))
        return
    if a.debug.startswith("doc:"):
        import io as _io, zipfile as _zf
        C.API_KEY = C.get_key()
        for rno in a.debug[4:].split(","):
            blob = C.api_get("document.xml", {"rcept_no": rno}, raw=True) or b""
            if blob[:2] != b"PK":
                C.log(rno, blob[:200]); continue
            with _zf.ZipFile(_io.BytesIO(blob)) as z:
                for nm in z.namelist():
                    t = dec(z.read(nm))
                    t = re.sub(r"<[^>]+>", " ", t); t = re.sub(r"\s+", " ", t)
                    i = t.find("보유비율")
                    C.log("== %s %s len=%d" % (rno, nm, len(t)))
                    for m in list(re.finditer("보유비율|보유주식등의 수", t))[:6]:
                        C.log("   ..." + t[max(0, m.start() - 150): m.start() + 450])
        return
    if a.debug.startswith("list:"):
        C.API_KEY = C.get_key()
        cmap = C.load_corp_map()
        for code in a.debug[5:].split(","):
            res = C.api_get("list.json", {"corp_code": cmap[code]["corp_code"], "bgn_de": "20100101", "end_de": "20241231",
                                          "pblntf_detail_ty": "D001", "page_count": 100}) or {}
            L = res.get("list", [])
            C.log("%s status=%s total=%s n=%d %s" % (code, res.get("status"), res.get("total_count"), len(L), res.get("message")))
            for r in L[:12]:
                C.log("   %s %s %s %s" % (r.get("rcept_dt"), r.get("rcept_no"), r.get("flr_nm"), r.get("report_nm")))
        return
    if a.debug:
        C.API_KEY = C.get_key()
        cmap = C.load_corp_map()
        for code in a.debug.split(","):
            res = C.api_get("majorstock.json", {"corp_code": cmap[code]["corp_code"]}) or {}
            L = res.get("list", [])
            C.log("%s status=%s n=%d keys=%s" % (code, res.get("status"), len(L), sorted(L[0].keys()) if L else "-"))
            reps = {}
            for r in L:
                reps.setdefault(r.get("repror"), []).append(r.get("rcept_dt"))
            for k, v in sorted(reps.items(), key=lambda kv: -len(kv[1]))[:15]:
                C.log("   %s  %d건  %s ~ %s" % (k, len(v), min(v), max(v)))
        return
    raw = load_json(RAW, {"checked": {}, "rows": {}}) if a.build else fetch(a.budget)
    build(raw)
    if C.ABORT and not a.build:
        sys.exit(0)                            # 한도 초과는 다음 날 이어서 하면 된다


if __name__ == "__main__":
    main()
