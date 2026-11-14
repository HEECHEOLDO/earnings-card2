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
BUDGET = int(os.environ.get("HOLDERS_BUDGET", "5000"))   # 한 번에 쓰는 DART 호출 수 (하루 한도 2만 회)
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


def newest_possible(today):
    """오늘 기준으로 나와 있을 수 있는 가장 새 정기보고서의 기준일 (분기 45일 · 사업 90일 뒤 제출 마감)"""
    best = None
    for y, rc, nm, asof in candidates(today):
        d = date(int(asof[:4]), int(asof[5:7]), int(asof[8:10]))
        if (today - d).days >= (90 if rc == "11011" else 45):
            if best is None or asof > best:
                best = asof
    return best


def latest(corp, endpoint, today, ok=None):
    """가장 최근 정기보고서의 표. ok 가 있으면 그 검사를 통과하는 것만 (최대주주 칸이 '-' 뿐인 보고서는 건너뛴다)"""
    for y, rc, nm, asof in candidates(today):
        if asof > today.isoformat():
            continue
        rows = rows_of(C.api_get(endpoint, {"corp_code": corp, "bsns_year": y, "reprt_code": rc}))
        if rows and (ok is None or ok(rows)):
            return rows, (y, rc, nm, asof)
    return None, None


def has_people(rows):
    return any(common(r) and (n(r.get("trmend_posesn_stock_qota_rt")) or 0) > 0 and (r.get("nm") or "").strip() not in ("계", "합계", "-")
               for r in rows)


def common(r):
    """보통주 줄만 (우선주 줄은 뺀다). 회사마다 '보통주'·'의결권있는주식'·'-' 등 적는 법이 달라 '우선'만 거른다"""
    k = (r.get("stock_knd") or r.get("se") or "").replace(" ", "")
    return "우선" not in k and "종류" not in k


def norm(s):
    s = (s or "").replace("㈜", "").replace("(주)", "").replace("주식회사", "").replace(" ", "").lower()
    return s.split("\n")[0].split("(")[0]


def one(code, cm, today, force=False):
    corp = cm[code]["corp_code"]
    path = os.path.join(OUT, code + ".json")
    old = None
    if os.path.exists(path):
        old = json.load(open(path, encoding="utf-8"))

    if old and not force and old.get("asof") == newest_possible(today):
        return old, "그대로"                      # 나올 수 있는 가장 새 보고서를 이미 받았다 — 묻지도 않는다
    major, rep = latest(corp, "hyslrSttus.json", today, has_people)
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

    # 소액주주: 같은 보고서에 없으면 가장 최근 사업보고서 (호출 수를 아끼려고 두 곳만 본다)
    minor = None
    mr, mrep = None, None
    for yy, rr_, nm2, as2 in [(y, rc, rname, asof), (str(int(y) - (0 if rc == "11011" else 1)), "11011", "사업보고서",
                                                      "%d-12-31" % (int(y) - (0 if rc == "11011" else 1)))]:
        mr = rows_of(C.api_get("mrhlSttus.json", {"corp_code": corp, "bsns_year": yy, "reprt_code": rr_}))
        if mr:
            mrep = (yy, rr_, nm2, as2)
            break
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
    # 5% 보고는 보고자와 특별관계자를 합친 지분이라, 최대주주 쪽 사람이 낸 보고(김성운 48.8%·삼성물산 19.7%)는 뺀다
    mine = [norm(p["n"]) for p in people]

    def same(a):                                   # '국민연금공단'(5% 보고) = '국민연금기금'(최대주주 표) 처럼 앞 네 글자가 같으면 같은 주주
        a = norm(a)
        return any(a == m or (len(a) >= 4 and a[:4] == m[:4]) for m in mine)
    big = [v for v in five.values() if v["pct"] >= 5 and not same(v["n"])]
    big.sort(key=lambda x: -x["pct"])

    if not issued and people:                      # 주식 총수 표가 없는 보고서 — 최대주주 주식 수 ÷ 지분율로
        issued = round(people[0]["sh"] / people[0]["pct"] * 100)
    if os.environ.get("HOLDERS_DEBUG"):
        print("  raw", code, [(r.get("nm"), r.get("stock_knd"), r.get("trmend_posesn_stock_qota_rt")) for r in major[:6]])
    out = {
        "name": cm[code]["name"], "asof": asof, "report": "%s %s" % (y, rname),
        "rcept_no": major[0].get("rcept_no") or "",
        "issued": int(issued) if issued else None,
        "treasury": int(treasury) if treasury is not None else None,     # 주식 총수 표가 없으면 모름(None)
        "major": people, "five": big[:8], "minor": minor,
        "updated": today.isoformat(),
    }
    return clean(out), "새로"


NOT_PERSON = ("소액주주", "자기주식", "자사주")


def clean(out):
    """보고서·5% 보고를 섞을 때 생기는 겹침을 걷어낸다 (전체가 100%를 넘지 않게)
      - 최대주주 표에 '기타소액주주'·'자기주식' 줄을 넣는 회사가 있다 → 뺀다
      - 5% 보고자가 최대주주 쪽과 이름이 달라도(POSCO홀딩스=포스코홀딩스, AK홀딩스=에이케이홀딩스)
        지분이 최대주주 한 명이나 최대주주 측 합계와 거의 같으면 같은 보고로 보고 뺀다
      - 그래도 합이 100%를 넘으면(보고서 뒤에 주인이 바뀐 회사·담보 보고 등) 넘치는 5% 보고는 뺀다"""
    out["major"] = [p for p in out["major"] if not any(w in p["n"] for w in NOT_PERSON) and p["n"] != "기타"]
    # 우선주 줄을 '보통주'로 적지 않은 회사(코오롱글로벌·롯데칠성) — 주식 수 ÷ 지분율로 본 '전체 주식 수'가
    # 보통주보다 훨씬 작으면 다른 종류 주식 줄이다
    tots = [p["sh"] / p["pct"] * 100 for p in out["major"] if p.get("sh") and p["pct"] >= 1]
    if tots:
        big = max(tots)
        out["major"] = [p for p in out["major"] if not p.get("sh") or not p["pct"] or p["sh"] / p["pct"] * 100 >= big * 0.5]
    ms = sum(p["pct"] for p in out["major"])
    tr = (out["treasury"] or 0) / out["issued"] * 100 if out.get("issued") else 0
    keep, used = [], ms + tr
    for f in sorted(out.get("five") or [], key=lambda x: -x["pct"]):
        if abs(f["pct"] - ms) <= 0.6 or any(abs(f["pct"] - p["pct"]) <= 0.3 and f["pct"] >= 5 for p in out["major"][:3]):
            continue
        # 최대주주 측 합계와 비슷한 큰 보고(합계의 ±10%)는 최대주주 쪽이 영문·약칭으로 낸 보고 (KC&A=케이씨엔에이, Lee Drew Sukhwan 이석환)
        if ms >= 10 and abs(f["pct"] - ms) <= ms * 0.1:
            continue
        # 최대주주 표의 한글 이름이 보고자 이름 안에 그대로 들어 있으면 같은 사람
        if any(len(p["n"]) >= 2 and p["n"] in f["n"] for p in out["major"][:5]):
            continue
        if used + f["pct"] > 100.0:
            continue
        keep.append(f)
        used += f["pct"]
    out["five"] = keep
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    C.API_KEY = C.get_key()
    cm = C.load_corp_map()
    if args:
        codes = args
    else:
        idx = json.load(open(os.path.join("data", "index.json"), encoding="utf-8"))
        codes = sorted(x["code"] for x in idx.get("companies") or [] if x.get("code") in cm)
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
            print("  %d/%d %s · DART 호출 %d" % (i, len(codes), cnt, C._call_count), flush=True)
        if C._call_count >= BUDGET:
            print("  호출 %d회 — 오늘은 여기까지 (DART 하루 한도를 실적 수집과 나눠 쓴다). 다음 실행 때 이어서" % C._call_count)
            break
    write_index()
    print("끝:", cnt, "· DART 호출", C._call_count)


def write_index():
    """data/holders/index.json — 탭의 종목 목록 {코드: [이름, 기준일]}"""
    items = {}
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".json") and f[:6].isdigit():
            try:
                j = json.load(open(os.path.join(OUT, f), encoding="utf-8"))
                items[f[:-5]] = [j.get("name"), j.get("asof")]
            except Exception:                     # noqa: BLE001
                pass
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": date.today().isoformat(), "items": items}, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
