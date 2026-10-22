#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비상장(감사보고서) 수집이 매일 돌게 한다.

  python3 fix_audit_daily.py

원인: 감사보고서 수집기(collect_audit.py)는 손으로 한 번(10.17) 돌렸고, 매일 도는 작업
     (비상장 실적 수집)에는 정기보고서 수집기만 들어 있었다. 그래서 302곳 중 6곳에서 멈춤.
고침: 1) .github/workflows/collect_unlisted.yml — 정기보고서 수집 다음에 감사보고서 수집을 붙인다.
        DART 한도는 둘이 1,500회를 나눠 쓴다 (정기 쪽이 쓰고 남은 만큼). 하루 70~100곳씩,
        나흘쯤이면 302곳이 다 찬다.
     2) collect_audit.py — 끝까지 돈 날을 data/unlisted/_audit_run.json 에 남긴다.
     3) check_health.py — 감사보고서 상태는 그 날짜를 먼저 본다 (받을 회사가 없던 날도 '정상').
이미 감사보고서 수집이 작업에 들어 있으면 1)은 건너뛰고 알려 준다. 두 번 돌려도 괜찮다.
"""
import glob
import os
import re
import sys

WF = ".github/workflows/collect_unlisted.yml"
STEP = """      - name: 감사보고서 회사 수집 (남은 예산으로)
        env:
          DART_API_KEY: ${{ secrets.DART_API_KEY }}
        run: python3 collect_audit.py --total 1500
"""
FIXES = [
    ("collect_audit.py", "_audit_run.json",
     "    U.jsave(FAILED, failed, indent=1)\n    sync_meta(load_list())\n",
     "    U.jsave(FAILED, failed, indent=1)\n"
     "    if not C.ABORT:                           # 끝까지 돈 날을 남긴다 (받을 회사가 없던 날도)\n"
     "        U.jsave(os.path.join(OUT, \"_audit_run.json\"),\n"
     "                {\"updated\": U.today(), \"done\": len(done), \"calls\": C._call_count}, indent=1)\n"
     "    sync_meta(load_list())\n"),
    ("check_health.py", "_audit_run.json",
     '["data/unlisted/_audit_checked.json"]',
     '["data/unlisted/_audit_run.json", "data/unlisted/_audit_checked.json"]'),
]


def fix_workflow():
    used = [f for f in glob.glob(".github/workflows/*.yml") if "collect_audit.py" in open(f, encoding="utf-8").read()]
    if used:
        print("  그대로  감사보고서 수집이 이미 작업에 있음: %s" % ", ".join(used))
        print("          → 그런데도 멈췄다면 Actions 탭에서 그 작업의 오류를 봐 주세요.")
        return True
    if not os.path.exists(WF):
        print("!! %s 가 없습니다" % WF)
        return False
    s = open(WF, encoding="utf-8").read()
    m = re.search(r"^ *run: python3 collect_unlisted\.py[^\n]*\n", s, re.M)
    if not m:
        print("!! %s 에서 정기보고서 수집 줄을 못 찾았습니다. 이 파일을 보내 주세요." % WF)
        return False
    s = s[:m.end()] + "\n" + STEP + s[m.end():]
    open(WF, "w", encoding="utf-8").write(s)
    print("  고침    %s  (감사보고서 수집 단계 추가)" % WF)
    return True


def main():
    ok = fix_workflow()
    for fn, mark, old, new in FIXES:
        if not os.path.exists(fn):
            print("!! %s 가 없습니다" % fn); ok = False; continue
        s = open(fn, encoding="utf-8").read()
        if mark in s:
            print("  그대로  %s" % fn); continue
        if s.count(old) != 1:
            print("!! %s 이 예상과 달라 고치지 않았습니다. 이 파일을 보내 주세요." % fn); ok = False; continue
        open(fn, "w", encoding="utf-8").write(s.replace(old, new))
        print("  고침    %s" % fn)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
