#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 실적(us.html) 검색 목록을 '티커 · 회사명' 으로 보이게 하고, 회사명으로도 찾게 한다.

  python3 fix_us_search.py

지금은 목록 오른쪽에 티커가 한 번 더 나와(AAPL · AAPL) 무슨 회사인지 모른다.
data/us/index.json 의 legal_name(SEC 정식 이름, 예: Apple Inc.)을 오른쪽에 보여주고,
'apple' 처럼 회사명으로 쳐도 나오게 한다. 연간 수익률 화면과 같은 모양.
두 번 돌려도 괜찮다.
"""
import sys

FN = "us.html"
REPL = [
    ("목록 오른쪽 — 티커 대신 회사명",
     "'</span><span class=\"code\">' + c.code + '</span></li>';",
     "'</span><span class=\"code\">' + (c.legal_name && c.legal_name !== c.name ? c.legal_name : c.code) + '</span></li>';"),
    ("검색 — 회사명으로도 (순위는 티커 다음)",
     "        else if (name.indexOf(s) >= 0) rank = 4;\n        if (rank >= 0) out.push({ c: c, r: rank });",
     "        else if (name.indexOf(s) >= 0) rank = 4;\n"
     "        else if ((c.legal_name || '').toLowerCase().indexOf(s) === 0) rank = 5;\n"
     "        else if ((c.legal_name || '').toLowerCase().indexOf(s) >= 0) rank = 6;\n"
     "        if (rank >= 0) out.push({ c: c, r: rank });"),
    ("엔터로 고를 때도 회사명으로",
     "        if (list[i].name.toLowerCase().indexOf(low) >= 0) return list[i];\n      }\n      return null;\n    },\n\n    search:",
     "        if (list[i].name.toLowerCase().indexOf(low) >= 0) return list[i];\n      }\n"
     "      for (i = 0; i < list.length; i++) {\n"
     "        if ((list[i].legal_name || '').toLowerCase().indexOf(low) >= 0) return list[i];\n      }\n"
     "      return null;\n    },\n\n    search:"),
]


def main():
    s = open(FN, encoding="utf-8").read()
    if "c.legal_name && c.legal_name !== c.name" in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if bad:
        print("!! %s 에서 고칠 자리를 못 찾았습니다: %s" % (FN, ", ".join(bad)))
        sys.exit(1)
    for _, a, b in REPL:
        s = s.replace(a, b)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  (%d군데)" % (FN, len(REPL)))


if __name__ == "__main__":
    main()
