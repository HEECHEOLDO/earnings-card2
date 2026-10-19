#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) 제목을 '반도체 시가총액' 처럼 바꾼다 (시안 C).

  python3 patch_mcap_c.py

  제목     대상 이름은 굵게·검정, '시가총액'은 보통 굵기·회색
           (TOP 20 은 빼고, 순위 칸은 그대로 개수만 고른다)
  둘째 줄  테마 괄호 안 내용이 있을 때만 (예: 디지털화폐 등), 없으면 줄 자체가 없다
  하단     왼쪽에 '2026년 10월 19일 기준' (괄호 없이), 오른쪽 @돈굴돈굴
두 번 돌려도 괜찮다.
"""
import re
import sys

FN = "mcap.html"
MARK = "MCAP_FOOT"

REPL = [
    ("제목 — TOP 빼고 '시가총액'",
     "'시가총액 TOP ' + Math.min(+n, cnt || +n);",
     "'시가총액';"),
    ("둘째 줄 — 괄호 안 내용만, 날짜는 하단으로",
     "document.getElementById('sub').value = ([lab, extra].filter(Boolean).join(' · ') + d).trim();",
     "document.getElementById('sub').value = extra;\n"
     "    window.MCAP_FOOT = a ? a[0] + '년 ' + (+a[1]) + '월 ' + (+a[2]) + '일 기준' : '';"),
    ("제목 그리기 — '시가총액'만 보통 굵기·회색",
     "ctx.font = font(900, ns); ctx.fillText(title, X0, y);",
     "var tm = title.match(/^(.*\\S)( 시가총액)$/);\n"
     "    if (tm) { ctx.font = font(900, ns); ctx.fillText(tm[1], X0, y);\n"
     "      var tw = ctx.measureText(tm[1]).width;\n"
     "      ctx.font = font(400, ns); ctx.fillStyle = T.inkSoft; ctx.fillText(tm[2], X0 + tw, y); ctx.fillStyle = T.ink; }\n"
     "    else { ctx.font = font(900, ns); ctx.fillText(title, X0, y); }"),
    ("둘째 줄 그리기 — 비었으면 건너뜀",
     "var ss = fit(sub, 700, 40, 26, W); y += ns * 0.22 + ss * 0.86;\n"
     "    ctx.fillStyle = T.inkSoft; ctx.font = font(700, ss); ctx.fillText(sub, X0, y);",
     "if (sub) { var ss = fit(sub, 700, 40, 26, W); y += ns * 0.22 + ss * 0.86;\n"
     "    ctx.fillStyle = T.inkSoft; ctx.font = font(700, ss); ctx.fillText(sub, X0, y); }"),
]

RIGHT = "ctx.textAlign = 'right'; ctx.fillText('@돈굴돈굴', CW - S.right, footY);"
LEFT_RE = re.compile(r"ctx\.fillText\((?:'[^']*'|window\.FOOTL \|\| '')\s*,\s*S\.left,\s*footY\);")
LEFT_NEW = "ctx.fillText(window.MCAP_FOOT || '', S.left, footY);"
# 옛 테스트 코드: 순위를 바꾸면 제목을 '시가총액 TOP n' 으로 덮어쓰던 줄
OLD_N = re.compile(r"\n[ \t]*if \(id === 'n'\) document\.getElementById\('title'\)\.value = '시가총액 TOP ' \+ this\.value;")


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if MARK in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if s.count(RIGHT) != 1:
        bad.append("하단 @돈굴돈굴 자리")
    if len(LEFT_RE.findall(s)) > 1:
        bad.append("하단 왼쪽 글자 자리")
    if bad:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 못 찾은 자리:" % FN)
        for b in bad:
            print("   - " + b)
        print("   mcap.html 을 보내 주세요.")
        sys.exit(1)
    for _, a, b in REPL:
        s = s.replace(a, b)
    if LEFT_RE.search(s):
        s = LEFT_RE.sub(LEFT_NEW, s)
    else:
        s = s.replace(RIGHT, "ctx.textAlign = 'left'; " + LEFT_NEW + "\n    " + RIGHT)
    s = OLD_N.sub("", s)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  — 제목 '○○ 시가총액', 날짜는 좌측 하단" % FN)


if __name__ == "__main__":
    main()
