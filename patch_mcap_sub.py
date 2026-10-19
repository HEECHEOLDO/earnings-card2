#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) — 업종·테마 카드 아래 줄에서 '업종' '테마' 글자를 뺀다.

  python3 patch_mcap_sub.py

  전: 업종 ('26년 10월 19일 기준)        → 후: ('26년 10월 19일 기준)
  전: 테마 · 디지털화폐 등 ('26년 …)      → 후: 디지털화폐 등 ('26년 …)
코스피·코스닥·국내 주식은 지금처럼 앞에 붙는다. 두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
OLD = ("    document.getElementById('sub').value = { kospi: '코스피', kosdaq: '코스닥', all: '국내 주식', industry: '업종', theme: '테마' }[mk] +\n"
       "      (gpart && gpart[1] ? ' · ' + gpart[1] : '') + d;")
NEW = ("    var lab = { kospi: '코스피', kosdaq: '코스닥', all: '국내 주식' }[mk] || '';   // 업종·테마는 이름표 없이\n"
       "    var extra = gpart && gpart[1] ? gpart[1] : '';\n"
       "    document.getElementById('sub').value = ([lab, extra].filter(Boolean).join(' · ') + d).trim();")


def main():
    s = open(FN, encoding="utf-8").read()
    if NEW in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    if s.count(OLD) != 1:
        print("!! %s 에서 고칠 자리를 못 찾았습니다. mcap.html 을 보내 주세요." % FN)
        sys.exit(1)
    open(FN, "w", encoding="utf-8").write(s.replace(OLD, NEW))
    print("  고침    %s  — 업종·테마 아래 줄에서 '업종' '테마' 뺌" % FN)


if __name__ == "__main__":
    main()
