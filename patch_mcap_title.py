#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) — 긴 테마 이름 때문에 카드 제목이 잘리던 것을 고친다.

  python3 patch_mcap_title.py

  · 카드 제목에서는 괄호 안을 뺀다
      '화폐/금융자동화기기(디지털화폐 등)' → '화폐/금융자동화기기 시가총액 TOP 10'
  · 괄호 안은 버리지 않고 아래 줄로 옮긴다 (2차전지(전고체)와 2차전지가 구별되게)
      '테마 · 디지털화폐 등 ('26년 10월 19일 기준)'
  · 그래도 길면 제목 글자를 더 작게까지 줄인다 (최소 52 → 36)
목록(고르는 칸)에는 원래 이름이 그대로 나온다. 두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
REPL = [
    ("제목 — 괄호 뺀 이름",
     "      gname = gg ? gg.name + ' ' : '';",
     "      gname = gg ? gg.name.replace(/\\s*\\([^)]*\\)\\s*/g, ' ').trim() + ' ' : '';\n"
     "      var inner = gg ? (gg.name.match(/\\(([^)]*)\\)/) || [])[1] : '';\n"
     "      if (inner) gname += '\\u0000' + inner + '\\u0000';   // 아래 줄로 넘길 표시"),
    ("제목·아래 줄 나누기",
     "    document.getElementById('title').value = gname + '시가총액 TOP ' + Math.min(+n, cnt || +n);",
     "    var gpart = gname.split('\\u0000');      // [이름, 괄호 안, '']\n"
     "    document.getElementById('title').value = gpart[0] + '시가총액 TOP ' + Math.min(+n, cnt || +n);"),
    ("아래 줄 — 괄호 안 내용",
     "{ kospi: '코스피', kosdaq: '코스닥', all: '국내 주식', industry: '업종', theme: '테마' }[mk] + d;",
     "{ kospi: '코스피', kosdaq: '코스닥', all: '국내 주식', industry: '업종', theme: '테마' }[mk] +\n"
     "      (gpart && gpart[1] ? ' · ' + gpart[1] : '') + d;"),
    ("제목 글자 최소 크기",
     "var ns = fit(title, 900, 92, 52, W)",
     "var ns = fit(title, 900, 92, 36, W)"),
]


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if "gpart" in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if bad:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 못 찾은 자리:" % FN)
        for b in bad:
            print("   - " + b)
        print("   mcap.html 을 보내 주세요.")
        sys.exit(1)
    for _, a, b in REPL:
        s = s.replace(a, b)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  (%d군데) — 제목은 괄호 빼고, 괄호 안은 아래 줄로" % (FN, len(REPL)))


if __name__ == "__main__":
    main()
