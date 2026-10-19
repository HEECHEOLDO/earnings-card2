#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) — 코스피·코스닥·국내주식도 업종·테마처럼 제목에 이름, 아래 줄엔 날짜만.

  python3 patch_mcap_market_title.py

  코스피 시가총액 TOP 20      코스닥 시가총액 TOP 20      국내주식 시가총액 TOP 20
  ('26년 10월 19일 기준)     ('26년 10월 19일 기준)     ('26년 10월 19일 기준)
patch_mcap_sub.py 를 먼저 돌린 mcap.html 에 쓴다. 두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
REPL = [
    ("제목 앞에 시장 이름",
     "    var gname = '';",
     "    var gname = { kospi: '코스피 ', kosdaq: '코스닥 ', all: '국내주식 ' }[mk] || '';"),
    ("아래 줄은 날짜만",
     "    var lab = { kospi: '코스피', kosdaq: '코스닥', all: '국내 주식' }[mk] || '';   // 업종·테마는 이름표 없이",
     "    var lab = '';                              // 시장·업종·테마 이름은 제목에, 아래 줄은 날짜만"),
]


def main():
    s = open(FN, encoding="utf-8").read()
    if "kospi: '코스피 '" in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if bad:
        print("!! %s 에서 못 찾은 자리: %s — patch_mcap_sub.py 를 먼저 돌렸는지 확인해 주세요." % (FN, ", ".join(bad)))
        sys.exit(1)
    for _, a, b in REPL:
        s = s.replace(a, b)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  — 코스피·코스닥·국내주식 제목 통일" % FN)


if __name__ == "__main__":
    main()
