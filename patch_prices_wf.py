#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""매일 새벽 수익률 수집 워크플로가 해외 월말 종가·환율도 올리게 고친다.

  python3 patch_prices_wf.py --dry     바꿀 내용만 보여준다
  python3 patch_prices_wf.py           실제로 고친다

왜 필요한가
-----------
collect_prices.py 는 매일 해외 24종목을 받아 data/monthly_us.json 을
만든다. 그런데 워크플로가 커밋할 때 data/returns.json 만 올리고 있어서
monthly_us.json 은 버려졌다. 다음 날은 다시 옛 파일(ETF 28개)에서 출발해
같은 AAPL·ABBV… 를 또 받았다. 그래서 '그때 샀다면' 해외에 개별주가 안 생겼다.

또 환율(data/fx_usdkrw.json)을 갱신하는 단계가 없다. 11월이 되면 해외 탭은
10월 말 환율이 필요하므로, 매일 collect_fx.py 를 같이 돌린다.

하는 일
-------
1. git add 줄에 data/monthly_us.json, data/fx_usdkrw.json 을 더한다
2. '커밋 · 푸시' 단계 바로 앞에 '환율 수집' 단계를 넣는다
여러 번 돌려도 같은 결과다 (이미 들어가 있으면 건너뛴다).
"""
import glob
import os
import sys

ADD = ["data/monthly_us.json", "data/fx_usdkrw.json"]
FX_STEP = ["      - name: 환율 수집\n",
           "        run: python3 collect_fx.py || true\n",
           "\n"]


def find():
    """collect_prices.py 를 실행하는(주석이 아닌) 워크플로를 찾는다."""
    out = []
    for p in sorted(glob.glob(".github/workflows/*.y*ml")):
        for line in open(p, encoding="utf-8"):
            s = line.strip()
            if s.startswith("#"):
                continue
            if "collect_prices.py" in s and "--status" not in s and ("run:" in s or s.startswith("python")):
                out.append(p)
                break
    return out


def patch(path, dry):
    lines = open(path, encoding="utf-8").readlines()
    changed = []

    # 1) git add 줄
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("git add") and "data/returns.json" in s:
            miss = [a for a in ADD if a not in s]
            if miss:
                head, sep, tail = l.partition("data/returns.json")
                lines[i] = head + sep + "".join(" " + a for a in miss) + tail
                changed.append("git add 에 %s 추가" % ", ".join(miss))
            break
    else:
        print("!! %s 에서 'git add data/returns.json' 줄을 못 찾았습니다." % path)
        print("   cat %s 결과를 보여주세요." % path)
        return False

    # 2) 환율 수집 단계
    if not any("collect_fx.py" in l and not l.strip().startswith("#") for l in lines):
        at = next((i for i, l in enumerate(lines)
                   if l.strip().startswith("- name:") and ("커밋" in l or "commit" in l.lower())), None)
        if at is None:
            print("!! '커밋' 단계를 못 찾아 환율 단계를 넣지 못했습니다.")
            return False
        lines[at:at] = FX_STEP
        changed.append("'%s' 앞에 '환율 수집' 단계 추가" % lines[at + len(FX_STEP)].strip())

    if not changed:
        print("%s — 이미 고쳐져 있습니다." % path)
        return True
    for c in changed:
        print("  · " + c)
    if dry:
        print("\n(--dry 라 저장하지 않았습니다)")
    else:
        open(path, "w", encoding="utf-8").writelines(lines)
        print("\n저장했습니다: %s" % path)
    return True


def main():
    dry = "--dry" in sys.argv
    if not os.path.exists("collect_fx.py"):
        print("!! collect_fx.py 가 이 폴더에 없습니다. fincard 폴더에서 실행하세요.")
        return
    files = find()
    if not files:
        print("!! collect_prices.py 를 돌리는 워크플로를 못 찾았습니다.")
        print("   ls .github/workflows 결과를 보여주세요.")
        return
    for p in files:
        print(p)
        patch(p, dry)


if __name__ == "__main__":
    main()
