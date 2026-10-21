#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비상장(정기보고서) '수집 기록 없음' 경고가 잘못 뜨는 것을 고친다.

  python3 fix_unlisted_health.py

원인: 비상장 수집은 매일 돌지만, 회사마다 7일에 한 번만 다시 받는다.
     28곳을 같은 날 받으면 그 뒤 6일 동안은 받을 회사가 없어 '받은 날'이 그대로이고,
     상태 점검은 그 날짜만 보고 '4일째 수집 기록 없음'이라고 한다.
고침: 1) collect_unlisted.py — 수집이 끝까지 돌면(받을 회사가 없어도) data/unlisted/_run.json 에
        돈 날짜를 남긴다. DART 키 문제 등으로 중간에 멈춘 날은 남기지 않는다.
     2) check_health.py — 비상장(정기보고서)은 _run.json 의 날짜를 먼저 본다.
두 번 돌려도 괜찮다.
"""
import sys

FIXES = [
    ("collect_unlisted.py", "_run.json",
     "    jsave(FAILED, failed, indent=1)\n",
     "    jsave(FAILED, failed, indent=1)\n"
     "    if not C.ABORT:                           # 끝까지 돈 날을 남긴다 (받을 회사가 없던 날도)\n"
     "        jsave(os.path.join(OUT, \"_run.json\"),\n"
     "              {\"updated\": today(), \"done\": len(done), \"calls\": C._call_count}, indent=1)\n"),
    ("check_health.py", "_run.json",
     '["data/unlisted/_checked.json"], 2, 4)',
     '["data/unlisted/_run.json", "data/unlisted/_checked.json"], 2, 4)'),
]


def main():
    bad = False
    for fn, mark, old, new in FIXES:
        try:
            s = open(fn, encoding="utf-8").read()
        except OSError:
            print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % fn)
            bad = True
            continue
        if mark in s:
            print("  그대로  %s  이미 고쳐짐" % fn)
            continue
        if s.count(old) != 1:
            print("!! %s 이 예상과 달라 고치지 않았습니다. 이 파일을 보내 주세요." % fn)
            bad = True
            continue
        open(fn, "w", encoding="utf-8").write(s.replace(old, new))
        print("  고침    %s" % fn)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
