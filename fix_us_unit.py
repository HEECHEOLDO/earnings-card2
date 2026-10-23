#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 실적 카드(us.html) 범례 오른쪽 단위 글자를 '환율 1,325원 기준' 하나로 줄인다.

  python3 fix_us_unit.py

지금: '단위 조원 · 배당 $ · 액면분할 반영 · 1,325원 기준' — 길어서 범례(주당배당금)와 겹친다.
바꾼 뒤: '환율 1,325원 기준' (환율은 지금처럼 매일 바뀐다). 환율 글자가 없는 카드는 빈칸.
두 번 돌려도 괜찮다.
"""
import sys

FN = "us.html"
MARK = "US_UNIT_FX"
OLD = "    ctx.fillText(unitText, CX + CWID, legendY - 2);"
NEW = ("    var fxm = String(unitText).match(/([\\d,]+원)\\s*기준/);   // US_UNIT_FX — 환율만 남긴다\n"
       "    unitText = fxm ? '환율 ' + fxm[1] + ' 기준' : '';\n" + OLD)

s = open(FN, encoding="utf-8").read()
if MARK in s:
    print("  그대로  %s  이미 고쳐짐" % FN)
elif s.count(OLD) != 1:
    print("!! %s 에서 고칠 자리를 못 찾았습니다 (%d곳). us.html 을 보내 주세요." % (FN, s.count(OLD)))
    sys.exit(1)
else:
    open(FN, "w", encoding="utf-8").write(s.replace(OLD, NEW))
    print("  고침    %s  — 범례 오른쪽은 '환율 0,000원 기준'만" % FN)
