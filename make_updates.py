#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘의 업데이트 — 지난 하루 동안 data/ 에 무엇이 새로 들어왔는지 사람이 읽을 문장으로 정리한다.
사이트 '데이터 상태' 화면(status.html)의 '오늘의 업데이트' 와 메뉴 아래 한 줄이 이 파일을 읽는다.

  python3 make_updates.py                지난 24시간 (매일 아침 점검 때 돈다) → data/updates.json
  python3 make_updates.py --hours 48     기간을 바꿔서
  python3 make_updates.py --base <커밋>  그 커밋부터 지금까지
  python3 make_updates.py --show         저장하지 않고 화면에만

API 를 부르지 않는다. git 기록에서 하루 전 파일과 지금 파일을 견준다
(워크플로에서 checkout 할 때 기록이 며칠 치 있어야 한다 — fetch-depth).

무엇을 보나
  · 국내 실적·해외 실적·비상장 실적 — 새로 생긴 분기·연도 (예: 삼성전자 2026.3Q), 처음 들어온 회사
  · 시가총액 — 기준일이 바뀌었는지, 상위 10위 안 순위가 바뀐 것 (예: 애플 2위 → 1위)
  · 주가(그때 샀다면·시가배당률) · 연간 수익률 · 환율 — 기준일
  · 종목 스크리닝 — 다시 계산된 종목 수, 빠른 조건마다 통과 종목 수 변화
  · 화면 고침 — 사람이 올린 커밋 (자동 수집 커밋은 빼고)
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "updates.json")
KEEP_DAYS = 30            # 며칠 치를 남기나
MAX_ITEMS = 40            # 한 칸에 이름을 몇 개까지 적나 (나머지는 '외 N곳')
BOT = "github-actions[bot]"

# 스크리닝 빠른 조건 (screen.html 의 PRESETS 와 같은 값)
PRESETS = [
    ("배당귀족", {"divGrowYears": [5, None], "payout": [20, 60], "profitStreak": [5, None]}),
    ("고ROE 우량주", {"roeAvg": [15, None], "debt": [None, 100], "profitStreak": [5, None]}),
    ("꾸준한 성장주", {"revStreak": [5, None], "margin": [10, None]}),
    ("턴어라운드", {"turnaround": [1, 1]}),
    ("고배당", {"yield": [4, None], "payout": [None, 70], "divYears": [3, None]}),
    ("실적 서프라이즈", {"qNew": [1, 1], "qOpYoy": [50, None]}),
    ("실적 쇼크", {"qNew": [1, 1], "qOpYoy": [None, -50]}),
    ("분기 흑자전환", {"qNew": [1, 1], "qTurn": [1, 1]}),
    ("분기 적자전환", {"qNew": [1, 1], "qTurn": [-1, -1]}),
    ("저평가 알짜", {"roe": [10, None], "debt": [None, 80], "margin": [10, None], "lossCount": [None, 0]}),
]


def git(*args):
    return subprocess.run(["git"] + list(args), capture_output=True, text=True, check=False).stdout


def old_json(base, path):
    """하루 전(base 커밋)의 파일. 없으면 None"""
    out = subprocess.run(["git", "show", "%s:%s" % (base, path)], capture_output=True, check=False)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout.decode("utf-8"))
    except Exception:      # noqa: BLE001
        return None


def new_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:      # noqa: BLE001
        return None


def opt(name, default=None):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


# ------------------------------------------------------------ 실적 (국내·해외·비상장)

def periods(d):
    if not d:
        return set(), set()
    a = {x.get("p") for x in d.get("annual") or [] if x.get("p")}
    q = {(x.get("y"), x.get("q")) for x in d.get("quarterly") or [] if x.get("y")}
    return a, q


def earnings(base, paths, label_of):
    """새 분기·연도 / 처음 들어온 회사. 같은 기간의 숫자만 바뀐 건 '고침' 으로 센다"""
    added, first, fixed = [], [], 0
    for p in paths:
        new = new_json(p)
        if not new:
            continue
        old = old_json(base, p)
        name = label_of(new, p)
        if old is None:
            first.append(name)
            continue
        oa, oq = periods(old)
        na, nq = periods(new)
        got = ["%d.%dQ" % k for k in sorted(nq - oq)] + ["%d년" % y for y in sorted(na - oa)]
        if got:
            added.append((name, got))
        elif (old.get("annual"), old.get("quarterly")) != (new.get("annual"), new.get("quarterly")):
            fixed += 1
    return added, first, fixed


def section_earnings(base, files, key, title, page, prefix, label_of):
    paths = [f for f in files if f.startswith(prefix) and f.endswith(".json")
             and not os.path.basename(f).startswith("_") and os.path.basename(f)[:-5] not in ("index", "screen")]
    if key == "kr":
        paths = [f for f in paths if os.path.dirname(f) == "data" and os.path.basename(f)[:-5].isdigit()]
    added, first, fixed = earnings(base, paths, label_of)
    if not (added or first or fixed):
        return None
    # 새 분기 종류별로 몇 곳인지 (예: 2026.3Q 12곳)
    by = {}
    for _, got in added:
        for g in got:
            by[g] = by.get(g, 0) + 1
    def pkey(g):                      # '2026.3Q' · '2026년' → 최근 것이 앞
        return (int(g[:4]), int(g[5]) if g.endswith("Q") else 5)
    parts = ["%s %d곳" % (g, n) for g, n in sorted(by.items(), key=lambda x: pkey(x[0]), reverse=True)]
    added.sort(key=lambda x: max(pkey(g) for g in x[1]), reverse=True)
    if first:
        parts.append("새 회사 %d곳" % len(first))
    if fixed:
        parts.append("숫자 고침 %d곳" % fixed)
    items = ["%s %s" % (nm, " · ".join(got)) for nm, got in added[:MAX_ITEMS]]
    items += ["%s (새로 추가)" % nm for nm in first[:max(0, MAX_ITEMS - len(items))]]
    more = len(added) + len(first) - len(items)
    return {"key": key, "name": title, "page": page, "summary": " · ".join(parts),
            "items": items, "more": max(0, more), "count": len(added) + len(first)}


# ------------------------------------------------------------ 시가총액

def rank_moves(old_list, new_list, top=10):
    """상위 top 안에서 순위가 바뀐 회사 (예: 애플 2위 → 1위)"""
    if not old_list or not new_list:
        return []
    o = {r["code"]: i + 1 for i, r in enumerate(old_list)}
    out = []
    for i, r in enumerate(new_list[:top]):
        was = o.get(r["code"])
        if was is None:
            out.append("%s %d위 진입" % (r["name"], i + 1))
        elif was != i + 1 and (was <= top or i + 1 <= top):
            out.append("%s %d위 → %d위" % (r["name"], was, i + 1))
    return out


def section_mcap(base, files):
    items, parts = [], []
    if "data/mcap.json" in files:
        o, n = old_json(base, "data/mcap.json"), new_json("data/mcap.json")
        if n:
            if not o or o.get("asof") != n.get("asof"):
                parts.append("국내 %s 종가" % dot(n.get("asof")))
            allo = sorted((o or {}).get("kospi", []) + (o or {}).get("kosdaq", []), key=lambda r: -r["cap"])
            alln = sorted(n.get("kospi", []) + n.get("kosdaq", []), key=lambda r: -r["cap"])
            items += ["국내 " + x for x in rank_moves(allo, alln)]
    if "data/mcap_us.json" in files:
        o, n = old_json(base, "data/mcap_us.json"), new_json("data/mcap_us.json")
        if n:
            if not o or o.get("asof") != n.get("asof"):
                parts.append("미국 %s 종가" % dot(n.get("asof")))
            items += ["미국 " + x for x in rank_moves((o or {}).get("us"), n.get("us"))]
    if not (parts or items):
        return None
    if items:
        parts.append("상위 10위 순위 변동 %d건" % len(items))
    return {"key": "mcap", "name": "시가총액 · 시총 순위", "page": "mcap.html",
            "summary": " · ".join(parts), "items": items[:MAX_ITEMS], "more": max(0, len(items) - MAX_ITEMS),
            "count": len(items)}


# ------------------------------------------------------------ 주가 · 수익률 · 환율

def section_prices(base, files):
    parts = []
    if "data/anchor.json" in files:
        o, n = old_json(base, "data/anchor.json") or {}, new_json("data/anchor.json") or {}
        for mk, nm in (("kr", "국내"), ("us", "해외")):
            na = (n.get(mk) or {}).get("asof")
            if na and na != (o.get(mk) or {}).get("asof"):
                parts.append("%s 주가 %s" % (nm, dot(na)))
    for path, nm in (("data/returns.json", "연간 수익률"), ("data/monthly_us.json", "해외 월별 주가"), ("data/fx.json", "환율")):
        if path in files:
            n = new_json(path) or {}
            if n.get("updated") and n.get("updated") != (old_json(base, path) or {}).get("updated"):
                parts.append("%s %s" % (nm, dot(n.get("updated"))))
    if not parts:
        return None
    return {"key": "prices", "name": "주가 · 수익률 · 환율", "page": "buy.html",
            "summary": " · ".join(parts), "items": [], "more": 0, "count": len(parts)}


# ------------------------------------------------------------ 스크리닝

def preset_counts(d):
    if not d:
        return {}
    I = {k: i for i, k in enumerate(d["fields"])}
    out = {}
    for name, f in PRESETS:
        out[name] = sum(1 for r in d["rows"] if all(
            r[I[k]] is not None and (lo is None or r[I[k]] >= lo) and (hi is None or r[I[k]] <= hi)
            for k, (lo, hi) in f.items() if k in I))
    return out


def section_screen(base, files):
    if "data/screen.json" not in files:
        return None
    o, n = old_json(base, "data/screen.json"), new_json("data/screen.json")
    if not n:
        return None
    co, cn = preset_counts(o), preset_counts(n)
    items = ["%s %d → %d종목" % (k, co.get(k, 0), v) for k, v in cn.items() if co.get(k) != v]
    summary = "%s종목 다시 계산" % format(len(n["rows"]), ",")
    if n.get("price_asof"):
        summary += " · 시가배당률 %s 종가" % dot(n["price_asof"])
    return {"key": "screen", "name": "종목 스크리닝", "page": "screen.html", "summary": summary,
            "items": items, "more": 0, "count": len(items)}


# ------------------------------------------------------------ 사람이 올린 커밋

def section_site(base):
    lines = git("log", "--format=%an\t%s", "%s..HEAD" % base).splitlines()
    msgs = [s for a, _, s in (l.partition("\t") for l in lines) if a and a != BOT]
    if not msgs:
        return None
    return {"key": "site", "name": "화면 고침", "page": "status.html", "summary": "%d건" % len(msgs),
            "items": list(reversed(msgs))[:MAX_ITEMS], "more": max(0, len(msgs) - MAX_ITEMS), "count": len(msgs)}


def dot(d):
    return (d or "").replace("-", ".")


# ------------------------------------------------------------ 본체

def main():
    now = datetime.now(KST)
    base = opt("--base")
    if not base:
        hours = int(opt("--hours", "24"))
        since = (now - timedelta(hours=hours)).isoformat()
        base = git("rev-list", "-1", "--before=" + since, "HEAD").strip()
        if not base:      # 기록이 얕아 하루 전 커밋이 없으면 가장 오래된 것
            base = git("rev-list", "--max-parents=0", "HEAD").strip().splitlines()[-1]
    files = set(git("diff", "--name-only", base, "HEAD", "--", "data").split())

    kr_name = lambda d, p: d.get("name") or os.path.basename(p)[:-5]
    # 해외는 name 이 티커라 정식 이름을 줄여 앞에 쓴다 — 'Apple (AAPL)' · 'Fedex (FDX)'
    import re as _re
    def us_name(d, p):
        ln = (d.get("legal_name") or "").strip()
        if not ln:
            return d.get("name") or os.path.basename(p)[:-5]
        for _ in range(2):
            ln = _re.sub(r"[,\s]+(inc|corp|corporation|co|company|ltd|limited|plc|n\.v|holdings?|group|the)\.?$", "", ln, flags=_re.I).strip()
        if ln.isupper():
            ln = ln.title()
        return "%s (%s)" % (ln, d.get("name"))
    un_name = lambda d, p: d.get("name") or d.get("legal_name") or os.path.basename(p)[:-5]
    sections = [s for s in [
        section_earnings(base, files, "kr", "국내 실적", "index.html", "data/", kr_name),
        section_earnings(base, files, "us", "해외 실적", "us.html", "data/us/", us_name),
        section_earnings(base, files, "unlisted", "비상장 실적", "unlisted.html", "data/unlisted/", un_name),
        section_mcap(base, files),
        section_prices(base, files),
        section_screen(base, files),
        section_site(base),
    ] if s]

    day = {"date": now.strftime("%Y-%m-%d"), "made": now.strftime("%Y-%m-%d %H:%M"),
           # 커밋마다 시간대가 달라(+0000 · +0900) 한국 시각으로 바꿔 적는다
           "from": datetime.fromtimestamp(int(git("show", "-s", "--format=%ct", base).strip() or 0), KST).strftime("%Y-%m-%d %H:%M"),
           "sections": sections}

    for s in sections:
        print("■ %s — %s" % (s["name"], s["summary"]))
        for it in s["items"][:8]:
            print("    %s" % it)
        if len(s["items"]) > 8 or s["more"]:
            print("    … 외 %d" % (len(s["items"]) - 8 + s["more"]))
    if not sections:
        print("지난 기간에 바뀐 것이 없습니다")
    if "--show" in sys.argv:
        return

    try:
        hist = new_json(OUT) or {}
    except Exception:      # noqa: BLE001
        hist = {}
    days = [d for d in hist.get("days", []) if d.get("date") != day["date"]]
    days = ([day] + days)[:KEEP_DAYS]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": day["made"], "days": days}, f, ensure_ascii=False, separators=(",", ":"))
    print("\n저장 %s (%d일 치)" % (OUT, len(days)))


if __name__ == "__main__":
    main()
