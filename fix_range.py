#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 실적(index.html)·해외 실적(us.html)의 구간 기본값을 고친다.

  python3 fix_range.py

회사나 탭을 바꾸면 그 회사의 가장 긴 구간으로 연다. 전에는 앞 회사가 3년뿐이면
다음 회사도 3년으로 열렸다. 비상장 실적(unlisted.html)은 index.html 을 복사해
만들므로 make_unlisted_page.py 를 다시 돌리면 따라온다. 두 번 돌려도 괜찮다.
"""
OLD = "    var cur = Math.min(state.counts[state.period] || max, max);"
NEW = """    // 회사나 탭이 바뀌면 그 회사의 가장 긴 구간으로 연다. 앞 회사가 3년뿐이었다고
    // 다음 회사도 3년으로 열리지 않게. 사용자가 고른 구간은 같은 회사·탭 안에서만 유지.
    var c0 = state.company || {};
    var rkey = (c0.code || c0.ticker || c0.name) + '|' + state.period;
    if (state.rangeKey !== rkey) { state.rangeKey = rkey; state.counts[state.period] = max; }
""" + OLD

for fn in ("index.html", "us.html"):
    try:
        s = open(fn, encoding="utf-8").read()
    except OSError:
        print("  없음    %s" % fn)
        continue
    if "state.rangeKey" in s:
        print("  그대로  %s  이미 고쳐짐" % fn)
    elif s.count(OLD) == 1:
        open(fn, "w", encoding="utf-8").write(s.replace(OLD, NEW))
        print("  고침    %s" % fn)
    else:
        print("  !! %s 에서 고칠 자리를 못 찾음 (찾은 횟수 %d)" % (fn, s.count(OLD)))
