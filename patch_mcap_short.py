#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) — 업종 카드 제목에 짧은 이름을 쓴다.

  python3 patch_mcap_short.py

data/mcap.json 의 업종에 short(짧은 이름)가 있으면 카드 제목에 그걸 쓴다.
  고르는 목록: 다각화된 통신 서비스 · 3
  카드 제목:   통신 서비스 시가총액 TOP 3
짧은 이름은 collect_mcap.py 의 UPJONG_SHORT 에서 고친다. 두 번 돌려도 괜찮다.
(patch_mcap_title.py 를 먼저 돌린 mcap.html 에 쓴다)
"""
import sys

FN = "mcap.html"
OLD = "      gname = gg ? gg.name.replace(/\\s*\\([^)]*\\)\\s*/g, ' ').trim() + ' ' : '';"
NEW = "      gname = gg ? (gg.short || gg.name).replace(/\\s*\\([^)]*\\)\\s*/g, ' ').trim() + ' ' : '';"


def main():
    s = open(FN, encoding="utf-8").read()
    if NEW in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    if s.count(OLD) != 1:
        print("!! %s 에서 고칠 자리를 못 찾았습니다. patch_mcap_title.py 를 먼저 돌렸는지 확인하고, 안 되면 mcap.html 을 보내 주세요." % FN)
        sys.exit(1)
    open(FN, "w", encoding="utf-8").write(s.replace(OLD, NEW))
    print("  고침    %s  — 업종 카드 제목에 짧은 이름" % FN)


if __name__ == "__main__":
    main()
