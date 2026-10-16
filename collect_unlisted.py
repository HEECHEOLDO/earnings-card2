#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비상장 실적 수집기 — DART 정기보고서를 내는 비상장사  ->  data/unlisted/{회사코드}.json

  python3 collect_unlisted.py                 목록(unlisted_list.txt) 수집
  python3 collect_unlisted.py 01212921        회사코드 직접 지정
  python3 collect_unlisted.py --status        무엇이 얼마나 받아졌는지만 (호출 0회)

상장사 수집기(collect.py)의 함수를 그대로 쓴다 — 계정 매칭, 분기 차감, 검산,
배당, 액면분할 보정이 모두 같다. 다른 점은 둘뿐이다.
  · 비상장사는 종목코드가 없어 DART 회사코드(8자리)로 받는다
  · 결과를 data/ 가 아니라 data/unlisted/ 에 둔다 (국내 실적·스크리닝과 섞이지 않게)

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
    """회사코드 | 카드에 쓸 이름 | 분류   (# 뒤는 주석)"""
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
        out.append({"code": code, "name": p[1] if len(p) > 1 and p[1] else code,
                    "sector": p[2] if len(p) > 2 else ""})
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


def collect_one(item, latest_year):
    code = item["code"]
    log("\n=== %s (%s) ===" % (item["name"], code))
    log(" [연간]")
    annual = C.collect_annual(code, latest_year)
    log(" [분기]")
    quarterly = C.collect_quarterly(code, latest_year)
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
        "basis": basis_of(code),
        "updated": today(),
        "annual": annual,
        "quarterly": quarterly,
    }, worst


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
    n = rebuild_index()
    log("\n" + "=" * 50)
    for nm, st, note in done:
        log("  %-14s %-4s %s" % (nm, st, note))
    log("이번 %d곳 · API %d회 · 비상장 목록 총 %d곳" % (len(done), C._call_count, n))


if __name__ == "__main__":
    main()
