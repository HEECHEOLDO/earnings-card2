#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 버블 안 숫자를 크기에 맞는 단위로 쓴다.

  python3 patch_mcap_unit.py

  100조 이상   1,234조
  1조 이상     12.3조
  1조 미만     8,500억   (예전엔 0조·0.1조로 뭉개졌다)
그리고 작은 회사의 시총이 0.00조로 잘려 원 크기가 틀어지지 않게 1억 단위까지 적는다.
두 번 돌려도 괜찮다.
"""
import re
import sys

FN = "mcap.html"
MARK = "MCAP_UNIT"
MONEY_RE = re.compile(r"function money\(v\) \{[^\n]*\}")
MONEY_NEW = ("function money(v) { // MCAP_UNIT\n"
             "    if (v >= 100) return Math.round(v).toLocaleString('ko-KR') + '조';\n"
             "    if (v >= 1) return v.toFixed(1).replace(/\\.0$/, '') + '조';\n"
             "    return Math.max(1, Math.round(v * 10000)).toLocaleString('ko-KR') + '억';\n"
             "  }")
PREC_OLD = "(r.cap / 10000).toFixed(2)"
PREC_NEW = "(r.cap / 10000).toFixed(4)"


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if MARK in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = []
    if len(MONEY_RE.findall(s)) != 1:
        bad.append("숫자 단위 함수(money)")
    if s.count(PREC_OLD) != 1:
        bad.append("시총 자릿수")
    if bad:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 못 찾은 자리: %s" % (FN, ", ".join(bad)))
        print("   mcap.html 을 보내 주세요.")
        sys.exit(1)
    s = MONEY_RE.sub(lambda m: MONEY_NEW, s).replace(PREC_OLD, PREC_NEW)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  — 1조 미만은 억 단위로 (예: 8,500억)" % FN)


if __name__ == "__main__":
    main()
