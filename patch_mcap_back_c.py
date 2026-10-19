#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 제목의 '시가총액'을 다시 시안 C 로: 보통 굵기(400) + 진한 회색.

  python3 patch_mcap_back_c.py
patch_mcap_a.py 를 돌렸든 안 돌렸든 괜찮다. 두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
A = "ctx.font = font(900, ns); ctx.fillStyle = '#9AA0A8'; ctx.fillText(tm[2], X0 + tw, y);"
C = "ctx.font = font(400, ns); ctx.fillStyle = T.inkSoft; ctx.fillText(tm[2], X0 + tw, y);"

s = open(FN, encoding="utf-8").read()
if s.count(A) == 1:
    open(FN, "w", encoding="utf-8").write(s.replace(A, C))
    print("  고침    %s  — '시가총액' 보통 굵기·진한 회색 (시안 C)" % FN)
elif C in s:
    print("  그대로  %s  이미 시안 C" % FN)
else:
    print("!! %s 에서 고칠 자리를 못 찾았습니다. mcap.html 을 보내 주세요." % FN)
    sys.exit(1)
