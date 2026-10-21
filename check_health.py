#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자료가 제때 들어오고 있는지 점검해 data/health.json 에 적는다.
사이트의 '데이터 상태' 화면(status.html)과 모든 화면 메뉴 아래 한 줄이 이 파일을 읽는다.

  python3 check_health.py          점검 + data/health.json 저장 (DART 호출 수십 회)
  python3 check_health.py --local  DART 는 부르지 않고 파일 날짜만 본다 (호출 0회)

두 가지를 본다.
  1. 수집이 돌고 있나 — 탭마다 마지막으로 수집한 날이 며칠 전인지
  2. 새 공시가 반영됐나 — 최근 3주 DART 정기공시(사업·반기·분기보고서) 중
     우리가 가진 회사(국내 실적·비상장 정기)인데 아직 반영되지 않은 것
       · 늦음:    공시 뒤로 한 번도 다시 받지 않았다 (평소 주기보다 오래)
       · 숫자 없음: 공시 뒤에 받았는데 그 분기가 비어 있다 (DART 재무 API 에
                    아직 안 올라왔거나 계정을 못 읽음). 둘 다 평소 주기만큼 기다린 뒤에만 알린다

DART 하루 한도는 수집기들이 거의 다 쓰므로 여기서는 최대 60회만 쓴다.
키는 collect.py 와 같이 환경변수 DART_API_KEY 또는 key.txt.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.date()
OUT = os.path.join("data", "health.json")
MAX_CALLS = 60
LOOKBACK = 21          # 최근 며칠의 공시를 볼지

# 탭별 '마지막 수집일' 을 어디서 읽고, 며칠이면 주의/문제인지
#   (이름, 화면, 날짜를 읽을 파일들(앞에서부터), 주의, 문제)
#   _checked.json 은 {코드: 날짜} — 가장 늦은 날짜가 마지막 수집일이다.
#   나머지는 파일 안의 "updated".
SOURCES = [
    ("kr",       "국내 실적",   "index.html",    ["data/_checked.json", "data/index.json"], 2, 4),
    ("us",       "해외 실적",   "us.html",       ["data/us/_checked.json", "data/us/index.json"], 2, 4),
    ("unlisted", "비상장 실적 (정기보고서)", "unlisted.html", ["data/unlisted/_run.json", "data/unlisted/_checked.json"], 2, 4),
    ("audit",    "비상장 실적 (감사보고서)", "unlisted.html", ["data/unlisted/_audit_checked.json"], 4, 8),
    ("returns",  "연간 수익률", "returns.html",  ["data/returns.json"], 2, 4),
    ("buy_us",   "그때 샀다면 (해외 주가)", "buy.html", ["data/monthly_us.json"], 3, 6),
    ("mcap",     "시가총액",    "mcap.html",     ["data/mcap.json"], 4, 7),   # 평일 장 마감 뒤에만 받는다
    ("rank",     "시총 순위", "rank.html", ["data/rank.json"], 4, 7),
    ("fx",       "환율",       "buy.html",      ["data/fx_usdkrw.json"], 3, 6),
    ("guru",     "포트폴리오 (13F)", "guru.html", ["data/13f.json"], 7, 14),
]


def jload(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                         # noqa: BLE001
        return default


def day(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:                         # noqa: BLE001
        return None


def last_date(paths):
    """파일들에서 마지막 수집일을 찾는다"""
    for p in paths:
        j = jload(p)
        if not isinstance(j, dict):
            continue
        if p.endswith("_checked.json"):
            ds = [day(v) for v in j.values()]
            ds = [d for d in ds if d]
            if ds:
                return max(ds), p
        elif day(j.get("updated")):
            return day(j.get("updated")), p
    return None, None


def extra_note(key):
    """탭마다 한 줄 덧붙일 말 (몇 곳·몇 종목)"""
    if key == "kr":
        j = jload("data/index.json", {})
        return "%s곳" % format(j.get("count", 0), ",")
    if key == "us":
        j = jload("data/us/index.json", {})
        return "%s종목" % format(j.get("count", len(j.get("companies", []))), ",")
    if key in ("unlisted", "audit"):
        j = jload("data/unlisted/index.json", {})
        cs = j.get("companies", [])
        n = sum(1 for c in cs if bool(c.get("annual_only")) == (key == "audit"))
        if key == "audit":
            total = 0
            if os.path.exists("audit_list.txt"):
                total = sum(1 for ln in open("audit_list.txt", encoding="utf-8")
                            if re.match(r"\s*\d{8}", ln))
            return "%d곳" % n + (" / 목록 %d곳" % total if total else "")
        return "%d곳" % n
    if key == "mcap":
        j = jload("data/mcap.json", {})
        return "코스피 %d · 코스닥 %d종목" % (len(j.get("kospi", [])), len(j.get("kosdaq", [])))
    if key == "returns":
        j = jload("data/returns.json", {})
        it = j.get("items", {})
        us = sum(1 for c in it if not c.isdigit())
        return "국내 %s · 해외 %s종목" % (format(len(it) - us, ","), us)
    return ""


def freshness():
    out = []
    for key, name, page, paths, warn, bad in SOURCES:
        d, src = last_date(paths)
        if d is None:
            out.append({"key": key, "name": name, "page": page, "last": None,
                        "days": None, "status": "warn", "msg": "수집 기록을 찾지 못함",
                        "note": extra_note(key)})
            continue
        n = (TODAY - d).days
        st = "bad" if n > bad else "warn" if n > warn else "ok"
        msg = {"ok": "정상", "warn": "%d일째 수집 기록 없음" % n,
               "bad": "%d일째 수집 기록 없음 — 수집이 멈춘 것 같습니다" % n}[st]
        out.append({"key": key, "name": name, "page": page, "last": d.isoformat(),
                    "days": n, "status": st, "msg": msg, "note": extra_note(key)})
    return out


# ------------------------------------------------------------ 새 공시 반영

def expected(report_nm):
    """'분기보고서 (2026.09)' -> ('q', 2026, 3) / '사업보고서 (2025.12)' -> ('a', 2025, 12)"""
    m = re.search(r"\((\d{4})\.(\d{2})\)", report_nm)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    if "사업보고서" in report_nm:
        return ("a", y, mo)
    if "반기보고서" in report_nm or "분기보고서" in report_nm:
        return ("q", y, mo)
    return None


def has_period(d, kind, y, mo):
    """그 공시의 숫자가 파일에 있나. 12월 결산(달력 분기)인 회사만 판정하고
    아니면 None (결산월이 달라 분기 번호를 알 수 없다)."""
    if mo not in (3, 6, 9, 12):
        return None
    qs = {(q.get("y"), q.get("q")) for q in d.get("quarterly") or []}
    if kind == "a":
        return any(a.get("p") == y for a in d.get("annual") or [])
    q = mo // 3
    prev = (y, q - 1) if q > 1 else (y - 1, 4)
    if (y, q) in qs:
        return True
    return False if prev in qs else None      # 앞 분기도 없으면 결산월이 다른 회사일 수 있다


def lagging(calls_left):
    import collect as C
    C.API_KEY = C.get_key()
    kr_checked = jload("data/_checked.json", {}) or {}
    un_checked = jload("data/unlisted/_checked.json", {}) or {}
    filings, page, pages = [], 1, 1
    bgn = (TODAY - timedelta(days=LOOKBACK)).strftime("%Y%m%d")
    while page <= pages and C._call_count < calls_left:
        res = C.api_get("list.json", {"bgn_de": bgn, "end_de": TODAY.strftime("%Y%m%d"),
                                      "pblntf_ty": "A", "page_no": page, "page_count": 100})
        if not (res and res.get("status") == "000"):
            break
        filings += res.get("list", [])
        pages = int(res.get("total_page") or 1)
        page += 1
    partial = page <= pages

    late, missing, seen = [], [], set()
    # 같은 회사가 여러 건 내면 가장 최근 것만
    filings.sort(key=lambda r: r.get("rcept_dt", ""), reverse=True)
    for r in filings:
        nm = r.get("report_nm", "")
        if "기재정정" in nm or "첨부" in nm:
            continue
        exp = expected(nm)
        if not exp:
            continue
        stock = (r.get("stock_code") or "").strip()
        if stock and os.path.exists(os.path.join("data", stock + ".json")):
            tab, code, path, checked, grace = "국내 실적", stock, os.path.join("data", stock + ".json"), kr_checked, 9
        elif os.path.exists(os.path.join("data", "unlisted", r.get("corp_code", "") + ".json")):
            code = r["corp_code"]
            tab, path, checked, grace = "비상장 실적", os.path.join("data", "unlisted", code + ".json"), un_checked, 9
        else:
            continue
        if code in seen:
            continue
        seen.add(code)
        filed = day("%s-%s-%s" % (r["rcept_dt"][:4], r["rcept_dt"][4:6], r["rcept_dt"][6:8]))
        d = jload(path, {}) or {}
        if d.get("source") == "audit":
            continue
        last = day(checked.get(code, "")) or day(d.get("updated"))
        age = (TODAY - filed).days
        row = {"tab": tab, "name": d.get("name") or r.get("corp_name"), "code": code,
               "report": re.sub(r"\s+", " ", nm).strip(), "filed": filed.isoformat(),
               "days": age, "last": last.isoformat() if last else None}
        if (last is None or last < filed):
            if age > grace:
                late.append(row)
        elif age > grace and has_period(d, exp[0], exp[1], exp[2]) is False:
            missing.append(row)
    late.sort(key=lambda x: -x["days"])
    missing.sort(key=lambda x: -x["days"])
    return {"filings": len(filings), "partial": partial, "late": late, "missing": missing,
            "calls": C._call_count}


def main():
    src = freshness()
    lag = None
    if "--local" not in sys.argv:
        try:
            lag = lagging(MAX_CALLS)
        except Exception as e:                # noqa: BLE001
            lag = {"error": "%s" % e}
    if lag and not lag.get("error"):
        # 늦은 공시가 있으면 그 탭도 '주의'
        for s in src:
            tab = {"kr": "국내 실적", "unlisted": "비상장 실적"}.get(s["key"])
            n = sum(1 for x in lag["late"] + lag["missing"] if x["tab"] == tab)
            if tab and n and s["status"] == "ok":
                s["status"] = "warn"
                s["msg"] = "새 공시 %d건 반영 안 됨" % n
    worst = "bad" if any(s["status"] == "bad" for s in src) else \
            "warn" if any(s["status"] == "warn" for s in src) else "ok"
    payload = {"checked": NOW.strftime("%Y-%m-%d %H:%M"), "status": worst,
               "sources": src, "filings": lag}
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    mark = {"ok": "정상", "warn": "주의", "bad": "문제"}
    print("점검 %s · 전체 %s" % (payload["checked"], mark[worst]))
    for s in src:
        print("  [%s] %-22s 마지막 %s  %s  %s" % (mark[s["status"]], s["name"], s["last"] or "-",
                                             s["msg"], s["note"]))
    if lag and lag.get("error"):
        print("  ! 공시 점검 실패: %s" % lag["error"])
    elif lag:
        print("\n최근 %d일 정기공시 %d건%s · DART %d회"
              % (LOOKBACK, lag["filings"], " (일부만 봄)" if lag["partial"] else "", lag["calls"]))
        for x in lag["late"][:30]:
            print("  늦음     %-8s %-14s %s  %s 공시 · %d일째" % (x["tab"], x["name"], x["report"], x["filed"], x["days"]))
        for x in lag["missing"][:30]:
            print("  숫자 없음 %-8s %-14s %s  %s 공시" % (x["tab"], x["name"], x["report"], x["filed"]))
    print("\n저장: %s" % OUT)


if __name__ == "__main__":
    main()
