#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘 기준 'N년 전에 샀다면' 카드를 위한 기준점을 모은다.

왜 따로 있나
------------
returns.json 에는 연도별 수익률만 들어 있고, 각 연도의 기준점은 직전 해
12월 31일 종가다. 그래서 그걸 이어 붙이면 '2015년 말에 사서 2025년 말에 판'
값이 나온다. 오늘이 10월 5일인데 10년 전은 2016년 10월 5일이어야 하므로
시작도 끝도 9개월씩 어긋난다. 이 파일이 그 어긋남을 없앤다.

기준이 시장마다 다르다
----------------------
  국내 : 네이버 일별 종가. 10월 5일이면 10월 5일(휴장이면 직전 거래일).
         수정주가라 액면분할은 반영되지만 배당은 빠져 있다.
  해외 : 알파밴티지 월말 조정종가. 하루 25회 제한에 일별이 유료 구간이라
         월말이 한계다. 배당 재투자는 포함돼 있다.

그래서 국내 카드와 해외 카드는 절대 한 장에 섞지 않는다. 같은
'1억원 투자했다면'이라도 국내는 배당을 버리고 해외는 담기 때문이다.

액면분할 검사
-------------
네이버 일별이 수정주가가 아니면 삼성전자 10년 수익률이 50배로 어긋난다.
눈으로는 안 보이고 카드에만 나타난다. 그래서 기준점마다 같은 달의
월말 종가를 월봉에서 가져와 맞춰 본다.
  - 2·5·10·50배처럼 분할 배수로 어긋나는 종목이 많으면 → 전체 중단
    (일별이 수정주가가 아니라는 뜻. 2026-10-05 확인 결과 수정주가가 맞다)
  - 그 외(증자·감자 등으로 0.85배처럼 어긋남) → 그 종목만 빼고 저장
  - 오늘 종가가 없는 종목(상장폐지·거래정지)은 검사 대상이 아니다 → 제외만

이어받기
--------
종목마다 결과를 data/anchor_kr_cache.json 에 25종목마다 저장한다.
중간에 끊겨도 같은 기준일이면 다시 실행할 때 받은 종목을 건너뛴다.
날짜가 바뀌면 기준점도 바뀌므로 처음부터 받는다 (--base 로 고정 가능).

사용법
------
  python3 collect_anchor.py             국내·해외 모두
  python3 collect_anchor.py --kr        국내만
  python3 collect_anchor.py --us        해외만 (호출 없음, monthly_us.json 만 읽는다)
  python3 collect_anchor.py --limit 20  앞 20종목만 (시험용)
  python3 collect_anchor.py --status    지금 파일에 뭐가 들었는지만 본다
  python3 collect_anchor.py --kr --base 2026-10-05   기준일 고정 (자정 넘겨 이어받을 때)
  python3 collect_anchor.py --kr --fresh  캐시를 무시하고 처음부터
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

NAVER = ("https://api.finance.naver.com/siseJson.naver"
         "?symbol=%s&requestType=1&startTime=%s&endTime=%s&timeframe=%s")

IN_RET = "data/returns.json"
IN_MON = "data/monthly_us.json"
OUT = "data/anchor.json"
CACHE_KR = "data/anchor_kr_cache.json"

# 카드에서 고를 수 있는 기간. 늘리려면 여기만 고치면 된다.
# (국내는 기준점 하나당 네이버 호출이 한 번 더 들어간다)
SPANS = [1, 2, 3, 5, 10, 15, 20]

# 일별과 월말이 이만큼 넘게 벌어지면 수정주가가 아니라고 본다.
# 같은 달 마지막 거래일끼리 비교하므로 사실상 0 이어야 한다.
SPLIT_TOL = 0.02

# 분할 배수로 어긋난 종목이 이만큼(또는 검사 종목의 1%) 넘으면 전체 중단.
SPLIT_HALT_MIN = 10

PAUSE = 0.15              # 네이버에 들이대지 않는다
_calls = [0]


def log(*a):
    print(*a)
    sys.stdout.flush()


def today():
    return datetime.now(KST).date()


# ---------------------------------------------------------------- 네트워크

def get_text(url, tries=3):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (fincard)",
        "Referer": "https://finance.naver.com/",
    })
    for i in range(tries):
        try:
            _calls[0] += 1
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace"), None
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            return None, "HTTP %d" % e.code
        except Exception as e:                # noqa: BLE001
            if i < tries - 1:
                time.sleep(1.0 * (i + 1))
                continue
            return None, type(e).__name__
    return None, "실패"


def naver_rows(code, start, end, frame):
    """[(YYYYMMDD, 종가)] — 네이버는 파이썬 리터럴에 가까운 형태로 준다."""
    txt, why = get_text(NAVER % (code, start, end, frame))
    time.sleep(PAUSE)
    if not txt:
        return None, why
    try:
        rows = json.loads(txt.strip().replace("'", '"'))
    except Exception:                         # noqa: BLE001
        return None, "형식 오류"
    out = []
    for r in rows[1:]:
        try:
            v = float(r[4])
            if v > 0:
                out.append((str(r[0])[:8], v))
        except Exception:                     # noqa: BLE001
            continue
    out.sort()
    return (out, None) if out else (None, "값 없음")


# ---------------------------------------------------------------- 날짜 계산

def years_back(d, n):
    """n년 전 같은 날짜. 2월 29일은 28일로 내린다."""
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def month_span(d):
    """그 날짜가 속한 달의 첫날·마지막날 (YYYYMMDD 문자열)."""
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first.strftime("%Y%m%d"), (nxt - timedelta(days=1)).strftime("%Y%m%d")


def on_or_before(rows, ymd):
    """ymd 이하에서 가장 늦은 (날짜, 종가). 휴장이면 직전 거래일이 잡힌다."""
    pick = None
    for d, v in rows:
        if d <= ymd:
            pick = (d, v)
        else:
            break
    return pick


def fmt(ymd):
    return "%s-%s-%s" % (ymd[:4], ymd[4:6], ymd[6:8])


# ---------------------------------------------------------------- 국내

def is_split_ratio(r):
    """2·3·5·10·50배처럼 정수 배수로 어긋났는가 (액면분할·병합 패턴)."""
    x = r if r >= 1 else 1.0 / r
    k = round(x)
    return k >= 2 and abs(x / k - 1) < 0.03


def kr_one(code, base, months):
    """한 종목의 기준점. months 는 {YYYYMM: 월말종가} — 액면분할 검사용.

    돌려주는 값: (기준점 또는 None, 불일치 목록, 제외 사유 또는 None)
      불일치 = [{"ym", "day", "mon", "ratio"}]  — 진짜 일별·월봉 차이만
      제외 사유 = 상장 전·상장폐지·거래정지처럼 값을 만들 수 없는 경우
    """
    out, bad = {}, []
    for n in SPANS:
        tgt = years_back(base, n)
        s, e = month_span(tgt)
        rows, why = naver_rows(code, s, e, "day")
        if not rows:
            continue                          # 상장 전이면 그 기간은 그냥 비운다
        hit = on_or_before(rows, tgt.strftime("%Y%m%d"))
        if not hit:
            continue

        # 그 달 마지막 거래일 종가를 월봉과 맞춰 본다.
        # 수정주가가 아니면 액면분할 배수만큼 벌어진다.
        mk = tgt.strftime("%Y%m")
        if mk in months and months[mk]:
            r = rows[-1][1] / months[mk]
            if abs(r - 1) > SPLIT_TOL:
                bad.append({"ym": mk, "day": rows[-1][1], "mon": months[mk],
                            "ratio": round(r, 4)})
        out[str(n)] = {"d": fmt(hit[0]), "v": hit[1]}

    if not out:
        return None, [], "기준점 없음 (상장 1년 미만 또는 시세 없음)"

    # 오늘(휴장이면 직전 거래일) 종가
    s = (base - timedelta(days=14)).strftime("%Y%m%d")
    rows, _ = naver_rows(code, s, base.strftime("%Y%m%d"), "day")
    if not rows:
        return None, [], "최근 종가 없음 (상장폐지·거래정지)"
    out["now"] = {"d": fmt(rows[-1][0]), "v": rows[-1][1]}
    return out, bad, None


def load_cache(base, fresh):
    if fresh:
        return {}
    try:
        with open(CACHE_KR, encoding="utf-8") as f:
            c = json.load(f)
    except Exception:                         # noqa: BLE001
        return {}
    if c.get("base") != base.strftime("%Y-%m-%d"):
        log("캐시 기준일 %s ≠ 오늘 기준일 %s → 처음부터 받습니다"
            % (c.get("base"), base.strftime("%Y-%m-%d")))
        return {}
    return c.get("done") or {}


def save_cache(base, done):
    os.makedirs(os.path.dirname(CACHE_KR), exist_ok=True)
    tmp = CACHE_KR + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"base": base.strftime("%Y-%m-%d"), "done": done},
                  f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CACHE_KR)                 # 저장 도중 끊겨도 캐시가 깨지지 않는다


def collect_kr(codes, names, base, limit, fresh=False):
    """돌려주는 값: (items, 불일치 {code: [..]}, 제외 {code: 사유})"""
    todo = codes[:limit] if limit else codes
    done = load_cache(base, fresh)
    again = sum(1 for c in todo if c in done)
    log("국내 %d종목 — 기준일 %s%s" % (len(todo), base,
        ("  (이어받기: %d종목은 저장분 사용)" % again) if again else ""))
    fresh_n = 0
    for i, code in enumerate(todo, 1):
        if code not in done:
            # 월봉 한 번 (액면분할 검사용 · 호출 1회)
            s = years_back(base, max(SPANS) + 1).strftime("%Y%m%d")
            mrows, _ = naver_rows(code, s, base.strftime("%Y%m%d"), "month")
            months = {}
            for d, v in (mrows or []):
                months[d[:6]] = v
            got, bad, why = kr_one(code, base, months)
            done[code] = {"got": got, "bad": bad, "why": why}
            fresh_n += 1
            if fresh_n % 25 == 0:
                save_cache(base, done)
        if i % 25 == 0 or i == len(todo):
            log("  %d/%d  (호출 %d회)" % (i, len(todo), _calls[0]))
    if fresh_n:
        save_cache(base, done)

    items, mism, skip = {}, {}, {}
    for code in todo:
        r = done.get(code) or {}
        if r.get("bad"):
            mism[code] = r["bad"]
        elif r.get("got"):
            got = dict(r["got"])
            got["name"] = names.get(code, code)
            items[code] = got
        else:
            skip[code] = r.get("why") or "알 수 없음"
    return items, mism, skip


# ---------------------------------------------------------------- 해외

def us_month_index(ser, ym):
    """{"s":"YYYY-MM","v":[...]} 에서 YYYYMM 의 첨자."""
    y0, m0 = int(ser["s"][:4]), int(ser["s"][5:7])
    return (int(ym[:4]) - y0) * 12 + int(ym[4:6]) - m0


def shift_month(ym, back):
    y, m = int(ym[:4]), int(ym[4:6])
    t = y * 12 + (m - 1) - back
    return "%04d%02d" % (t // 12, t % 12 + 1)


def common_end(mon, share=0.85):
    """해외 종목들이 '다 같이' 가지고 있는 가장 최근 달.

    알파밴티지가 하루 25회라 한 바퀴 도는 데 3주쯤 걸린다. 그래서 어떤
    종목은 9월까지, 어떤 종목은 7월까지만 있다. 종목마다 자기 최신 달을
    끝으로 잡으면 한 카드 안에서 기간이 제각각이 되어 '2016.08 ~ 2026.08'
    같은 한 줄짜리 라벨을 붙일 수 없다. 그래서 끝점을 하나로 못박는다.
    몇 종목이 뒤처졌다고 전체를 끌어내리면 안 되니 85%% 선에서 끊는다.
    """
    ends = []
    for ser in mon.values():
        v = ser.get("v") or []
        i = len(v) - 1
        while i >= 0 and v[i] is None:
            i -= 1
        if i < 0:
            continue
        y0, m0 = int(ser["s"][:4]), int(ser["s"][5:7])
        t = y0 * 12 + m0 - 1 + i
        ends.append(t)
    if not ends:
        return None
    # 이번 달은 아직 안 끝났다. 알파밴티지는 진행 중인 달도 한 칸 주는데,
    # 그 값은 '월말 종가'가 아니라 받아온 날의 종가다. 10년 전은 진짜
    # 월말인데 이번 달만 월중이면 기간이 어긋난다. 그래서 끝난 달로 내린다.
    # 버리는 게 아니라 내리는 것이다 — 10월까지 있는 종목은 9월도 있다.
    d = today()
    cap = d.year * 12 + (d.month - 1) - 1
    ends = sorted((min(t, cap) for t in ends), reverse=True)
    t = ends[min(len(ends) - 1, int(len(ends) * share))]
    return "%04d%02d" % (t // 12, t % 12 + 1)


def collect_us(mon, names, limit):
    """월말 종가 파일만 읽는다 — API 호출 0회.

    끝점은 common_end() 가 고른 한 달로 통일한다. 거기까지 못 온 종목은
    stale 로 빼둔다 (카드에서 고를 수 없게). 숨기는 것보다 드러내는 쪽이
    낫다 — 알파밴티지 한도 때문에 밀린 종목이 몇 개인지 바로 보인다.
    """
    items, miss, stale = {}, [], []
    end_ym = common_end(mon)
    if not end_ym:
        return {}, [], [], ""
    codes = sorted(mon)
    if limit:
        codes = codes[:limit]
    log("해외 %d종목 — 월말 종가 파일에서 계산 (호출 없음) · 공통 끝점 %s"
        % (len(codes), fmt_ym(end_ym)))
    for code in codes:
        ser = mon[code]
        v = ser.get("v") or []
        y0, m0 = int(ser["s"][:4]), int(ser["s"][5:7])
        end = (int(end_ym[:4]) * 12 + int(end_ym[4:6]) - 1) - (y0 * 12 + m0 - 1)
        if end >= len(v) or end < 12:
            stale.append(code)                # 공통 달까지 아직 못 받아온 종목
            continue
        if v[end] is None:                    # 그 달이 비면 앞으로 두 달까지
            k, step = end, 0
            while k >= 0 and v[k] is None and step < 2:
                k -= 1
                step += 1
            if k < 0 or v[k] is None:
                stale.append(code)
                continue
            end = k
        got = {"now": {"d": fmt_ym(end_ym), "v": v[end]}, "name": names.get(code, code)}
        for n in SPANS:
            k, step = end - n * 12, 0
            while k >= 0 and v[k] is None and step < 3:   # 비면 앞으로 세 달까지
                k -= 1
                step += 1
            if k < 0 or v[k] is None:
                continue
            got[str(n)] = {"d": fmt_ym(shift_month(end_ym, end - k)), "v": v[k]}
        if len(got) > 2:
            items[code] = got
        else:
            miss.append(code)
    return items, miss, stale, end_ym


def fmt_ym(ym):
    return "%s-%s" % (ym[:4], ym[4:6])


# ---------------------------------------------------------------- 보기

def status():
    try:
        with open(OUT, encoding="utf-8") as f:
            j = json.load(f)
    except Exception:                         # noqa: BLE001
        log("%s 가 아직 없습니다." % OUT)
        return
    log("갱신 %s" % j.get("updated"))
    for mk in ("kr", "us"):
        b = j.get(mk) or {}
        it = b.get("items") or {}
        log("\n[%s] 기준 %s · %d종목 · asof %s%s"
            % (mk.upper(), b.get("basis", "?"), len(it), b.get("asof", "?"),
               (" · 제외 %d" % len(b["excluded"])) if b.get("excluded") else ""))
        have = {}
        for v in it.values():
            for n in SPANS:
                if str(n) in v:
                    have[n] = have.get(n, 0) + 1
        log("  " + "  ".join("%d년 %d개" % (n, have.get(n, 0)) for n in SPANS))
        for code in sorted(it)[:3]:
            v = it[code]
            cuts = ["%d년 %s %s" % (n, v[str(n)]["d"], fmt_won(v[str(n)]["v"]))
                    for n in SPANS if str(n) in v]
            log("  %-8s %-12s 현재 %s %s"
                % (code, str(v.get("name"))[:12], v["now"]["d"], fmt_won(v["now"]["v"])))
            for c in cuts:
                log("      " + c)


def fmt_won(v):
    return "{:,.2f}".format(v).rstrip("0").rstrip(".")


# ---------------------------------------------------------------- 본체

def main():
    argv = sys.argv[1:]
    if "--status" in argv:
        status()
        return
    only_kr, only_us = "--kr" in argv, "--us" in argv
    limit = 0
    if "--limit" in argv:
        try:
            limit = int(argv[argv.index("--limit") + 1])
        except Exception:                     # noqa: BLE001
            limit = 0

    try:
        with open(IN_RET, encoding="utf-8") as f:
            ret = json.load(f).get("items", {})
    except Exception:                         # noqa: BLE001
        log("!! %s 를 읽지 못했습니다. collect_prices.py 를 먼저 돌리세요." % IN_RET)
        return
    names = {c: (v.get("name") or c) for c, v in ret.items()}

    base = today()
    if "--base" in argv:
        try:
            base = datetime.strptime(argv[argv.index("--base") + 1], "%Y-%m-%d").date()
        except Exception:                     # noqa: BLE001
            log("!! --base 는 YYYY-MM-DD 형식이어야 합니다.")
            return
    out = {"updated": base.strftime("%Y-%m-%d"), "spans": SPANS}
    halt = False

    if not only_us:
        codes = sorted(c for c in ret if c.isdigit())
        items, mism, skip = collect_kr(codes, names, base, limit, "--fresh" in argv)

        # 불일치를 '분할 배수' 와 '그 외' 로 나눈다
        split_codes = {c for c, b in mism.items() if any(is_split_ratio(x["ratio"]) for x in b)}
        other_codes = set(mism) - split_codes
        excluded = dict(skip)
        for c in split_codes:
            excluded[c] = "일별·월봉 분할 배수 불일치 %s" % mism[c][0]["ym"]
        for c in other_codes:
            x = mism[c][0]
            excluded[c] = "일별·월봉 불일치 %s (%.2f배, 증자·감자 추정)" % (x["ym"], x["ratio"])

        out["kr"] = {"asof": base.strftime("%Y-%m-%d"),
                     "basis": "일별 종가 · 배당 제외 · 수정주가",
                     "items": items,
                     "excluded": excluded}

        reasons = {}
        for why in skip.values():
            k = why.split(" (")[0]
            reasons[k] = reasons.get(k, 0) + 1
        log("\n국내 %d종목 확보 · 제외 %d종목" % (len(items), len(excluded)))
        for k, n in sorted(reasons.items(), key=lambda x: -x[1]):
            log("  - %s: %d" % (k, n))
        if other_codes:
            log("  - 일별·월봉 불일치(증자·감자 추정, 그 종목만 제외): %d" % len(other_codes))
            for c in sorted(other_codes)[:10]:
                x = mism[c][0]
                log("      %s %-10s %s: 일별 %.0f vs 월말 %.0f (%.2f배)"
                    % (c, str(names.get(c, c))[:10], x["ym"], x["day"], x["mon"], x["ratio"]))
        if split_codes:
            log("  - 분할 배수 불일치: %d" % len(split_codes))
            for c in sorted(split_codes)[:10]:
                x = mism[c][0]
                log("      %s %-10s %s: 일별 %.0f vs 월말 %.0f (%.2f배)"
                    % (c, str(names.get(c, c))[:10], x["ym"], x["day"], x["mon"], x["ratio"]))

        checked = len(items) + len(mism)
        if len(split_codes) >= max(SPLIT_HALT_MIN, int(checked * 0.01)):
            halt = True
            log("\n" + "!" * 52)
            log("분할 배수(2·5·10·50배 등)로 어긋난 종목이 %d개입니다." % len(split_codes))
            log("네이버 일별이 수정주가가 아닐 가능성이 큽니다.")
            log("파일을 쓰지 않고 멈춥니다. 받은 값은 %s 에 남아 있어" % CACHE_KR)
            log("원인을 고친 뒤 다시 실행하면 네트워크 호출 없이 바로 끝납니다.")

    if not only_kr:
        mon = {}
        try:
            with open(IN_MON, encoding="utf-8") as f:
                mon = json.load(f).get("items", {})
        except Exception:                     # noqa: BLE001
            log("! %s 가 없습니다. collect_prices.py 를 한 바퀴 돌려야 쌓입니다." % IN_MON)
        if mon:
            items, miss, stale, end_ym = collect_us(mon, names, limit)
            out["us"] = {"basis": "월말 조정종가 · 배당 재투자 포함",
                         "asof": fmt_ym(end_ym) if end_ym else "",
                         "items": items}
            log("해외 %d종목 확보%s%s"
                % (len(items),
                   ("  (자료 부족 %d)" % len(miss)) if miss else "",
                   ("  (아직 %s 까지 못 온 종목 %d — 알파밴티지 한도 탓, 며칠 뒤 따라옵니다)"
                    % (fmt_ym(end_ym), len(stale))) if stale else ""))

    # ---- 액면분할 검사 ----
    if halt:
        if "--force" not in argv:
            return
        log("\n--force 가 있어 그대로 저장합니다 (불일치 종목은 이미 제외됨).")

    # --kr / --us 하나만 돌렸을 때 다른 시장 자료를 지우지 않는다
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
        for mk in ("kr", "us"):
            if mk not in out and prev.get(mk):
                out[mk] = prev[mk]
    except Exception:                         # noqa: BLE001
        pass

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    log("\n저장 %s · %.2fMB · 호출 %d회"
        % (OUT, os.path.getsize(OUT) / 1024 / 1024, _calls[0]))


if __name__ == "__main__":
    main()
