#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이미 받은 국내 실적 파일(data/*.json)에서 '누적값이 들어간 분기'를 지운다.

  python3 fix_quarters.py          무엇이 지워지는지만 보기
  python3 fix_quarters.py --fix    실제로 지우고 screen.json 다시 만들기

API 를 쓰지 않는다. 예전 collect.py 는 앞 분기 보고서가 없으면 빼지 않고 누적값을
그대로 넣었다 (2Q 자리에 6개월치, 3Q 자리에 9개월치, 4Q 자리에 1년치).
같은 해에 바로 앞 분기가 없는데 뒷 분기만 있으면 그 분기가 그런 경우다.
맨 앞 분기는 앞 분기가 10분기 창 밖에 있을 뿐이라 건드리지 않는다.
정리한 파일에는 q_method: strict 를 적어, 다시 돌려도 남은 분기(예: 앞 분기를
지운 뒤의 4Q — 연간에서 3분기 누적을 뺀 올바른 값)를 지우지 않는다.
고친 collect.py 는 이런 분기를 처음부터 만들지 않는다.
"""
import json
import os
import sys

import collect as C


def main():
    fix = "--fix" in sys.argv
    hit, removed = [], 0
    for fn in sorted(os.listdir(C.OUT_DIR)):
        if not (fn.endswith(".json") and fn[:-5].isdigit() and len(fn[:-5]) == 6):
            continue
        path = os.path.join(C.OUT_DIR, fn)
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:                     # noqa: BLE001
            continue
        if d.get("q_method") == "strict":
            continue                          # 고친 collect.py 로 받았거나 이미 정리한 파일
        qs = d.get("quarterly") or []
        have = {(q["y"], q["q"]) for q in qs}
        wrong = [q for q in qs[1:] if q["q"] > 1 and (q["y"], q["q"] - 1) not in have]
        if not wrong:
            continue
        hit.append((d.get("name", fn[:-5]), fn[:-5], wrong))
        removed += len(wrong)
        if fix:
            d["quarterly"] = [q for q in qs if q not in wrong]
            d["q_method"] = "strict"          # 다시 돌려도 남은 분기를 건드리지 않게
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)

    for name, code, wrong in hit:
        print("  %-14s %s  %s" % (name, code, ", ".join(
            "%d.%dQ(%s억)" % (q["y"], q["q"], format(round(q["rev"] or 0), ",")) for q in wrong)))
    print("\n누적값이 들어간 분기: %d곳 · %d개" % (len(hit), removed))
    if not fix:
        print("지우려면:  python3 fix_quarters.py --fix")
        return
    if hit:
        C.build_screen()
        print("지웠습니다. screen.json 도 다시 만들었습니다 (API 0회).")


if __name__ == "__main__":
    main()
