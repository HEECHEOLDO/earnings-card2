#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 제목의 '시가총액'을 시안 A 로: 대상 이름과 같은 굵기(900) + 연한 회색.

  python3 patch_mcap_a.py      (patch_mcap_c.py 를 먼저 돌린 mcap.html 에)
두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
OLD = "ctx.font = font(400, ns); ctx.fillStyle = T.inkSoft; ctx.fillText(tm[2], X0 + tw, y);"
NEW = "ctx.font = font(900, ns); ctx.fillStyle = '#9AA0A8'; ctx.fillText(tm[2], X0 + tw, y);"

s = open(FN, encoding="utf-8").read()
if NEW in s:
    print("  그대로  %s  이미 고쳐짐" % FN)
elif s.count(OLD) != 1:
    print("!! %s 에서 고칠 자리를 못 찾았습니다. patch_mcap_c.py 를 먼저 돌렸는지 확인하세요." % FN)
    sys.exit(1)
else:
    open(FN, "w", encoding="utf-8").write(s.replace(OLD, NEW))
    print("  고침    %s  — '시가총액' 굵게·연한 회색 (시안 A)" % FN)
