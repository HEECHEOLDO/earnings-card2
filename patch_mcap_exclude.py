#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""업종·테마에서 어울리지 않는 종목을 뺀다 (예: 화장품 테마의 코웨이).

  python3 patch_mcap_exclude.py

1) collect_mcap.py 에 '빼는 종목' 표(EXCLUDE)를 넣는다 → 매일 수집할 때마다 계속 빠진다.
2) 지금 있는 data/mcap.json 에서도 바로 뺀다 → 내일 수집을 기다리지 않아도 된다.
더 빼고 싶으면 collect_mcap.py 의 EXCLUDE 에 '테마이름': ['종목명', ...] 을 더하고
이 스크립트를 다시 돌리면 된다. 두 번 돌려도 괜찮다.
"""
import json
import re
import sys

PY, DATA = "collect_mcap.py", "data/mcap.json"

TABLE = '''# 업종·테마에서 일부러 빼는 종목 — 열쇠는 업종·테마 이름(띄어쓰기 무시), 값은 종목명 목록.
# 네이버가 넓게 묶어 둔 것 중 카드에 어울리지 않는 것을 뺀다.
EXCLUDE = {
    "화장품": ["코웨이"],
}


def excluded(name, caps):
    """이 업종·테마에서 뺄 종목코드들"""
    bad = set(EXCLUDE.get(re.sub(r"\\s", "", name), []))
    return {c for c, v in caps.items() if v.get("n") in bad} if bad else set()


def groups(kind, keep, caps):'''

OLD_CODES = "            codes = [c for c in members(kind, no) if c in keep]"
NEW_CODES = ("            drop = excluded(name, caps)\n"
             "            codes = [c for c in members(kind, no) if c in keep and c not in drop]")


def patch_py():
    s = open(PY, encoding="utf-8").read()
    if "EXCLUDE = {" in s:
        print("  그대로  %s  이미 빼는 종목 표가 있음" % PY)
        return s
    if s.count("def groups(kind, keep, caps):") != 1 or s.count(OLD_CODES) != 1:
        print("!! %s 이 예상과 달라 고치지 않았습니다. collect_mcap.py 를 보내 주세요." % PY)
        sys.exit(1)
    s = s.replace("def groups(kind, keep, caps):", TABLE).replace(OLD_CODES, NEW_CODES)
    open(PY, "w", encoding="utf-8").write(s)
    print("  고침    %s  — 빼는 종목 표 (화장품: 코웨이)" % PY)
    return s


def apply_now(src):
    ns = {}
    m = re.search(r"EXCLUDE = (\{.*?\n\})", src, re.S)
    exec("EXCLUDE = " + m.group(1), ns)
    ex = {re.sub(r"\s", "", k): set(v) for k, v in ns["EXCLUDE"].items()}
    j = json.load(open(DATA, encoding="utf-8"))
    stocks, n = j.get("stocks", {}), 0
    for kind in ("industry", "theme"):
        for g in (j.get("groups") or {}).get(kind, []):
            bad = ex.get(re.sub(r"\s", "", g["name"]))
            if not bad:
                continue
            for c in [c for c in g["codes"] if stocks.get(c, {}).get("n") in bad]:
                g["codes"].remove(c)
                g["n"] -= 1
                g["sum"] = round(g["sum"] - stocks[c].get("c", 0))
                n += 1
                print("  뺌      %s → %s" % (g["name"], stocks[c]["n"]))
    if n:
        for kind in ("industry", "theme"):
            gs = (j.get("groups") or {}).get(kind, [])
            gs[:] = [g for g in gs if g["codes"]]
            gs.sort(key=lambda g: -g["sum"])
        with open(DATA, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    else:
        print("  그대로  %s  뺄 종목이 이미 없음" % DATA)


if __name__ == "__main__":
    apply_now(patch_py())
