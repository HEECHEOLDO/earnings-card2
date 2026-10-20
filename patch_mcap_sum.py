#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 카드 둘째 줄에 합계를 넣는다.

  python3 patch_mcap_sum.py

  코스피 TOP 20              상위 20개 합계 3,412조
  종목이 TOP 수보다 적으면   7개 합계 2.3조
  괄호 있는 테마             디지털화폐 등 · 7개 합계 2.3조
합계는 카드에 그려진 원들(같은 숫자)을 그대로 더한다. TOP 10/20/30/50 을 바꾸면 다시 계산.
단위는 원 안 숫자와 같다 (100조 이상 1,234조 · 1조 이상 12.3조 · 1조 미만 850억).
두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
MARK = "MCAP_SUM"
OLD = "    document.getElementById('sub').value = extra;"
NEW = """    // 합계 (MCAP_SUM) — 원으로 그려지는 것과 같은 줄·같은 순서로 더한다
    var vals = document.getElementById('data').value.split('\\n').map(function (l) {
      var p = l.trim().split(/\\s+/); return p.length < 3 ? 0 : parseFloat(p[2].replace(/,/g, ''));
    }).filter(function (v) { return v > 0; }).sort(function (a, b) { return b - a; });
    var k = Math.min(+n, vals.length), tot = 0;
    for (var i = 0; i < k; i++) tot += vals[i];
    var won = tot >= 100 ? Math.round(tot).toLocaleString('ko-KR') + '조'
            : tot >= 1 ? tot.toFixed(1).replace(/\\.0$/, '') + '조'
            : Math.max(1, Math.round(tot * 10000)).toLocaleString('ko-KR') + '억';
    var sumTxt = k ? (k < +n ? k + '개' : '상위 ' + k + '개') + ' 합계 ' + won : '';
    document.getElementById('sub').value = [extra, sumTxt].filter(Boolean).join(' · ');"""


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if MARK in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    if s.count(OLD) != 1:
        print("!! %s 이 예상과 달라 고치지 않았습니다 (둘째 줄 자리). mcap.html 을 보내 주세요." % FN)
        sys.exit(1)
    open(FN, "w", encoding="utf-8").write(s.replace(OLD, NEW))
    print("  고침    %s  — 둘째 줄에 '상위 N개 합계'" % FN)


if __name__ == "__main__":
    main()
