#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비상장 실적 수집기 — DART 정기보고서를 내는 비상장사  ->  data/unlisted/{회사코드}.json

  python3 collect_unlisted.py                 목록(unlisted_list.txt) 수집
  python3 collect_unlisted.py 01212921        회사코드 직접 지정
  python3 collect_unlisted.py --status        무엇이 얼마나 받아졌는지만 (호출 0회)
  python3 collect_unlisted.py --index         목록의 이름·분류·대표 서비스만 반영 (호출 0회)
  python3 collect_unlisted.py --check         분기 숫자 검사 (호출 0회)
  python3 collect_unlisted.py --check --fix   잘못 들어간 분기를 지운다 (호출 0회)

상장사 수집기(collect.py)의 함수를 그대로 쓴다 — 계정 매칭, 분기 차감, 검산,
배당, 액면분할 보정이 모두 같다. 다른 점은 셋이다.
  · 비상장사는 종목코드가 없어 DART 회사코드(8자리)로 받는다
  · 결과를 data/ 가 아니라 data/unlisted/ 에 둔다 (국내 실적·스크리닝과 섞이지 않게)
  · 분기는 앞 보고서가 있을 때만 만든다 (아래 collect_quarterly 참고)

DART 하루 한도는 2만 회이고, 상장사 수집(collect.yml)이 매일 1만 8천 회를 쓴다.
그래서 여기서는 하루 1,500회만 쓰고(--budget), 받은 지 7일이 넘은 회사만
다시 받는다(--refresh-days). 비상장사 실적은 분기에 한 번 바뀌므로 충분하다.

키는 collect.py 와 같이 환경변수 DART_API_KEY 또는 key.txt 에서 읽는다.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import collect as C

LIST = "unlisted_list.txt"
OUT = os.path.join("data", "unlisted")
CHECKED = os.path.join(OUT, "_checked.json")
FAILED = os.path.join(OUT, "_failed.json")
CALLS = os.path.join(OUT, "_calls.json")       # 오늘 쓴 호출 수 (collect_audit.py 와 나눠 쓴다)
PER_COMPANY = 70          # 한 곳에 드는 호출 수 상한(연결이 없으면 별도까지 두 번 부른다)
KST = timezone(timedelta(hours=9))


def log(*a):
    C.log(*a)


def today():
    return datetime.now(KST).strftime("%Y-%m-%d")


def opt(name, default):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass
    return default


def load_list():
    """회사코드 | 카드에 쓸 이름 | 분류 | 대표 서비스 (# 뒤는 주석)"""
    out = []
    if not os.path.exists(LIST):
        log("!! %s 가 없습니다." % LIST)
        return out
    for line in open(LIST, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|")]
        code = p[0]
        if not (code.isdigit() and len(code) == 8):
            log("  ? 무시된 줄: %s" % line)
            continue
        brand = ", ".join(x.strip() for x in (p[3] if len(p) > 3 else "").split(",") if x.strip())
        out.append({"code": code, "name": p[1] if len(p) > 1 and p[1] else code,
                    "sector": p[2] if len(p) > 2 else "", "brand": brand})
    return out


def jload(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                         # noqa: BLE001
        return default


def jsave(path, obj, **kw):
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, **kw)


def age_days(s):
    try:
        return (datetime.now(KST).date() - datetime.strptime(s, "%Y-%m-%d").date()).days
    except Exception:                         # noqa: BLE001
        return 9999


# 어느 재무제표로 받았는지 센다. collect.fetch_fs 와 똑같이 연결(CFS)을 먼저,
# 없으면 별도(OFS)를 부르고, 쓰인 쪽을 기록한다. 비상장사는 자회사가 없어
# 별도만 내는 곳이 많은데, 카드에 '연결' 이라고 찍히면 틀린 말이 된다.
_basis = {}


def fetch_fs(corp_code, year, reprt_code):
    key = (corp_code, year, reprt_code)
    if key in C._fs_cache:
        return C._fs_cache[key]
    rows = None
    for fs_div in ("CFS", "OFS"):
        res = C.api_get("fnlttSinglAcntAll.json", {
            "corp_code": corp_code, "bsns_year": str(year),
            "reprt_code": reprt_code, "fs_div": fs_div,
        })
        if res and res.get("status") == "000" and res.get("list"):
            rows = res["list"]
            _basis.setdefault(corp_code, {}).setdefault(fs_div, 0)
            _basis[corp_code][fs_div] += 1
            break
    C._fs_cache[key] = rows
    return rows


C.fetch_fs = fetch_fs          # collect_annual · collect_quarterly 가 이것을 쓰게 한다


def basis_of(code):
    b = _basis.get(code, {})
    if b.get("CFS") and not b.get("OFS"):
        return "연결"
    if b.get("OFS") and not b.get("CFS"):
        return "별도"
    return "연결·별도" if b else ""


def collect_quarterly(corp_code, latest_year):
    """collect.collect_quarterly 와 같되, 빼야 할 앞 보고서가 없으면 그 분기를 만들지 않는다.

    DART 에는 2Q·4Q 단독 보고서가 없어 누적에서 앞 분기를 뺀다.
        2Q = 반기 - 1Q    3Q = 3분기누적 - 반기    4Q = 연간 - 3분기누적
    collect.py 는 앞 보고서가 없으면 빼지 않고 누적값을 그대로 쓴다. 상장사는
    분기보고서를 빠짐없이 내서 문제가 없지만, 비상장사는 빠진 보고서가 있어
    상반기 6개월치가 '2Q' 로, 1년치가 '4Q' 로 들어갈 수 있다. 틀린 숫자보다
    빈칸이 낫다.
    """
    out = []
    order = (("Q1", C.REPRT["Q1"]), ("HALF", C.REPRT["HALF"]),
             ("Q3", C.REPRT["Q3"]), ("YEAR", C.REPRT["YEAR"]))
    for y in range(latest_year - 3, latest_year + 1):
        cum = {}
        for tag, code in order:
            fs = C.fetch_fs(corp_code, y, code)
            if not fs:
                continue
            use_cum = tag != "YEAR"
            cum[tag] = {k: C.pick_account(fs, k, cumulative=use_cum) for k in ("rev", "op", "ni")}

        def g(tag, k):
            return cum.get(tag, {}).get(k)

        def sub(a, b):
            return None if (a is None or b is None) else a - b

        steps = [(1, lambda k: g("Q1", k)),
                 (2, lambda k: sub(g("HALF", k), g("Q1", k))),
                 (3, lambda k: sub(g("Q3", k), g("HALF", k))),
                 (4, lambda k: sub(g("YEAR", k), g("Q3", k)))]
        for q, fn in steps:
            rev, op, ni = fn("rev"), fn("op"), fn("ni")
            if rev is None or op is None:
                continue
            out.append({"y": y, "q": q, "rev": C.eok(rev), "op": C.eok(op),
                        "ni": C.eok(ni) if ni is not None else None})
            log("  %d.%dQ  매출 %s억  영업이익 %s억" % (y, q, f"{C.eok(rev):,.0f}", f"{C.eok(op):,.0f}"))
    return out[-C.QUARTERS:]


def check(lst, fix):
    """받아둔 파일만 읽어 분기를 검사한다. API 를 쓰지 않는다.

    · 같은 해에 앞 분기 없이 뒷 분기만 있으면, 그 분기는 누적값이 들어간 것이다
      (예전 방식으로 받은 파일). --fix 면 지운다.
    · 4개 분기 합이 연간과 2% 넘게 다르면 알려준다 (연결/별도가 섞였거나
      결산월이 12월이 아닌 회사).
    """
    bad_n = fixed = 0
    for x in lst:
        path = os.path.join(OUT, x["code"] + ".json")
        d = jload(path, None)
        if not d:
            continue
        qs = d.get("quarterly") or []
        have = {(q["y"], q["q"]) for q in qs}
        # 새 방식으로 받았거나 이미 고친 파일은 분기가 원래 맞다. 그런 파일에서
        # 앞 분기가 비어 있는 건 앞 보고서가 없어 빈칸으로 둔 것이라 검사하지 않는다.
        # 맨 앞 분기는 앞 분기가 10분기 창 밖에 있을 뿐이므로 검사하지 않는다.
        strict = d.get("q_method") == "strict"
        wrong = [] if strict else [q for q in qs[1:]
                                   if q["q"] > 1 and (q["y"], q["q"] - 1) not in have]
        notes = []
        if wrong:
            notes.append("누적값이 들어간 분기 " + ", ".join("%d.%dQ" % (q["y"], q["q"]) for q in wrong))
        by = {}
        for q in qs:
            if q not in wrong:
                by.setdefault(q["y"], []).append(q)
        for a in d.get("annual") or []:
            ys = by.get(a["p"], [])
            if len(ys) == 4 and a.get("rev"):
                gap = abs(sum(q["rev"] for q in ys) - a["rev"]) / abs(a["rev"]) * 100
                if gap > 2:
                    notes.append("%d년 분기합이 연간과 %.1f%% 다름" % (a["p"], gap))
        if notes:
            bad_n += 1
            log("  %-14s %s" % (x["name"], " / ".join(notes)))
        if fix and not strict:
            d["quarterly"] = [q for q in qs if q not in wrong]
            d["q_method"] = "strict"
            jsave(path, d, indent=1)
            fixed += bool(wrong)
    log("\n검사 %d곳 · 확인 필요 %d곳%s"
        % (len(lst), bad_n, (" · 고친 파일 %d개" % fixed) if fix else ""))
    if bad_n and not fix:
        log("누적값이 들어간 분기는  python3 collect_unlisted.py --check --fix  로 지웁니다.")


def collect_one(item, latest_year):
    code = item["code"]
    log("\n=== %s (%s) ===" % (item["name"], code))
    log(" [연간]")
    annual = C.collect_annual(code, latest_year)
    log(" [분기]")
    quarterly = collect_quarterly(code, latest_year)
    if not annual and not quarterly:
        return None, "재무 데이터 없음"
    worst = C.check_quarters_vs_annual(annual, quarterly)
    if basis_of(code) == "연결·별도":
        log("  ! 해마다 연결/별도가 섞여 있습니다. 분기 차감이 어긋날 수 있어 검산을 보세요.")
    split = C.adjust_for_splits(annual)
    return {
        "name": item["name"],
        "split_adjusted": split,
        "legal_name": item.get("legal", item["name"]),
        "code": code,
        "market": "비상장",
        "sector": item["sector"],
        "brand": item.get("brand", ""),
        "basis": basis_of(code),
        "q_method": "strict",        # 앞 보고서가 있을 때만 분기를 만든 파일
        "updated": today(),
        "annual": annual,
        "quarterly": quarterly,
    }, worst


def sync_meta(lst):
    """목록에서 고친 이름·분류·대표 서비스를 받아둔 파일에 반영한다. API 를 쓰지 않는다.
    목록에서 이름을 바꾸면 카드 기본 제목도 그 이름이 된다."""
    n = 0
    for x in lst:
        path = os.path.join(OUT, x["code"] + ".json")
        d = jload(path, None)
        if not d:
            continue
        new = dict(d, name=x["name"], sector=x["sector"], brand=x.get("brand", ""))
        if new != d:
            jsave(path, new, indent=1)
            n += 1
    return n


def rebuild_index():
    items = []
    for fn in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        if not (fn.endswith(".json") and fn[:-5].isdigit()):
            continue
        d = jload(os.path.join(OUT, fn), None)
        if not d:
            continue
        items.append({"name": d.get("name", fn[:-5]), "code": d.get("code", fn[:-5]),
                      "market": "비상장", "sector": d.get("sector", ""),
                      "brand": d.get("brand", ""),
                      "annual_only": not d.get("quarterly"),
                      "updated": d.get("updated", "")})
    items.sort(key=lambda x: x["name"])
    payload = {"updated": today(), "count": len(items),
               "markets": {"비상장": len(items)}, "companies": items}
    path = os.path.join(OUT, "index.json")
    if not (os.path.exists(path) and C.data_unchanged(path, payload)):
        jsave(path, payload, indent=1)
    return len(items)


def status(lst):
    checked = jload(CHECKED, {})
    failed = jload(FAILED, {})
    have = [x for x in lst if os.path.exists(os.path.join(OUT, x["code"] + ".json"))]
    log("목록 %d곳 · 받음 %d곳 · 실패 %d곳" % (len(lst), len(have), len(failed)))
    for x in lst:
        p = os.path.join(OUT, x["code"] + ".json")
        if os.path.exists(p):
            d = jload(p, {})
            a, q = d.get("annual") or [], d.get("quarterly") or []
            last = ("%d.%dQ" % (q[-1]["y"], q[-1]["q"])) if q else "-"
            log("  %-14s 연간 %2d년  분기 %2d개 (최근 %s)  확인 %s"
                % (x["name"], len(a), len(q), last, checked.get(x["code"], "-")))
        elif x["code"] in failed:
            log("  %-14s 실패 — %s" % (x["name"], failed[x["code"]].get("reason")))
        else:
            log("  %-14s 아직" % x["name"])


def main():
    args = [a for a in C.parse_args()]
    lst = load_list()
    if args:                                  # 회사코드 직접 지정
        named = {x["code"]: x for x in lst}
        lst = [named.get(a, {"code": a, "name": a, "sector": ""}) for a in args]
    if "--status" in sys.argv:
        status(lst)
        return
    if "--check" in sys.argv:
        check(lst, "--fix" in sys.argv)
        if "--fix" in sys.argv:
            rebuild_index()
        return
    if "--index" in sys.argv:
        n = sync_meta(load_list())
        total = rebuild_index()
        log("이름·분류·대표 서비스 반영 %d곳 · 목록 총 %d곳 (API 0회)" % (n, total))
        return
    if not lst:
        return

    C.API_KEY = C.get_key()
    budget = opt("--budget", 1500)
    refresh = opt("--refresh-days", 7)
    force = "--force" in sys.argv or bool(args)
    latest_year = datetime.now().year
    os.makedirs(OUT, exist_ok=True)

    checked = jload(CHECKED, {})
    failed = jload(FAILED, {})
    fresh, stale = [], []
    for x in lst:
        has = os.path.exists(os.path.join(OUT, x["code"] + ".json"))
        if has and jload(os.path.join(OUT, x["code"] + ".json"), {}).get("source") == "audit":
            continue                          # 감사보고서 수집기(collect_audit.py)가 맡은 회사
        if (not force and not has
                and failed.get(x["code"], {}).get("reason") == "재무 데이터 없음"):
            continue                          # 숫자가 없던 회사는 매일 다시 부르지 않는다
        if not has:
            fresh.append(x)
        else:
            a = age_days(checked.get(x["code"], ""))
            if force or a >= refresh:
                stale.append((a, x))
    stale.sort(key=lambda t: -t[0])
    todo = fresh + [x for _, x in stale]
    log("목록 %d곳 | 새로 %d | 갱신 %d | 건너뜀(실패) %d | 예산 %d회"
        % (len(lst), len(fresh), len(stale), sum(1 for x in lst if x["code"] in failed), budget))

    done = []
    for x in todo:
        if C.ABORT:
            log("\n>> 중단: %s" % C.ABORT)
            break
        if C._call_count + PER_COMPANY > budget:
            log("\n>> 예산 %d회에 닿아 여기서 멈춥니다. 다음 실행에서 이어갑니다." % budget)
            break
        try:
            data, worst = collect_one(x, latest_year)
        except Exception as e:                # noqa: BLE001
            log("! 예외: %r" % e)
            failed[x["code"]] = {"name": x["name"], "reason": "예외 %s" % type(e).__name__}
            continue
        if not data:
            if C.ABORT:
                break
            failed[x["code"]] = {"name": x["name"], "reason": worst}
            done.append((x["name"], "실패", worst))
            continue
        failed.pop(x["code"], None)
        path = os.path.join(OUT, x["code"] + ".json")
        wrote = not (os.path.exists(path) and C.data_unchanged(path, data))
        if wrote:
            jsave(path, data, indent=1)
        checked[x["code"]] = today()
        note = "분기합 차이 %.1f%%" % worst if (worst is not None and worst >= 2) else ""
        done.append((x["name"], "정상" if wrote else "동일",
                     "연간 %d · 분기 %d %s" % (len(data["annual"]), len(data["quarterly"]), note)))

    jsave(CHECKED, checked, sort_keys=True, separators=(",", ":"))
    jsave(FAILED, failed, indent=1)
    if not C.ABORT:                           # 끝까지 돈 날을 남긴다 (받을 회사가 없던 날도)
        jsave(os.path.join(OUT, "_run.json"),
              {"updated": today(), "done": len(done), "calls": C._call_count}, indent=1)
    # 오늘 쓴 호출 수를 남긴다 — collect_audit.py 가 남은 만큼만 쓴다
    prev = jload(CALLS, {})
    calls = C._call_count + (prev.get("calls", 0) if prev.get("date") == today() else 0)
    jsave(CALLS, {"date": today(), "calls": calls})
    sync_meta(load_list())
    n = rebuild_index()
    log("\n" + "=" * 50)
    for nm, st, note in done:
        log("  %-14s %-4s %s" % (nm, st, note))
    log("이번 %d곳 · API %d회 · 비상장 목록 총 %d곳" % (len(done), C._call_count, n))


if __name__ == "__main__":
    main()
