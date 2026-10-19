#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""업종·테마마다 네이버 종목이 data/mcap.json 에 다 들어갔는지 검증한다.

  python3 verify_mcap_groups.py           (네이버 호출 약 350회 · 2~4분)

네이버 업종·테마 목록(종목 수 포함)과 각 업종·테마의 종목을 다시 받아,
우리 파일과 하나하나 맞춰 본다. 빠진 종목은 이유를 붙여 보여준다.
  우선주·스팩      이름으로 일부러 뺀 것 (정상)
  ETF·우선주·기타  국내 실적 목록에도, 실적 수집 실패 목록에도 없는 것 (ETF·우선주·리츠·외국주 등)
  시총 없음        네이버 시가총액 순위표에 없는 것 (거래정지·신규상장 등)
  60위 밖         다 들어갔지만 시총 61위 아래라 파일에 안 적은 것 (화면은 TOP 50 까지라 정상)
  누락            위 어디에도 해당하지 않는데 빠진 것 — 이게 있으면 고쳐야 한다
결과는 화면과 mcap_verify.txt 에 남는다.
"""
import json
import re

import collect_mcap as M


def main():
    j = json.load(open(M.OUT, encoding="utf-8"))
    stocks = j.get("stocks", {})
    try:
        listed = {c["code"] for c in json.load(open("data/index.json", encoding="utf-8")).get("companies", [])}
    except Exception:                         # noqa: BLE001
        listed = set()
    try:
        tried = set(json.load(open("data/_failed.json", encoding="utf-8")))
    except Exception:                         # noqa: BLE001
        tried = set()
    base = listed | tried
    bad = re.compile(r"(우|우B|\d우[BC]?|스팩\d*호?)$")

    log, total_missing, worst = [], 0, []
    for kind, key, label in (("upjong", "industry", "업종"), ("theme", "theme", "테마")):
        ours = {g["no"]: g for g in j.get("groups", {}).get(key, [])}
        naver = M.m_group_list(kind)
        log.append("\n[%s] 네이버 %d개 · 우리 파일 %d개" % (label, len(naver), len(ours)))
        reasons_all = {}
        for no, name in naver:
            mem = M.m_group_members(kind, no)
            g = ours.get(no)
            have = set(g["codes"]) if g else set()
            why = {}
            for c in mem:
                if c in have:
                    continue
                s = stocks.get(c)
                n = (s or {}).get("n", "")
                cut = g and g["n"] > len(g["codes"])
                low = min((stocks[x]["c"] for x in g["codes"] if x in stocks), default=0) if g else 0
                if c not in base:
                    r = "ETF·우선주·기타"
                elif s is not None and bad.search(n):
                    r = "우선주·스팩"
                elif cut and (s is None or s["c"] <= low):
                    r = "60위 밖"
                elif s is None:
                    r = "시총 없음"
                else:
                    r = "누락"
                why.setdefault(r, []).append(c)
            for r, cs in why.items():
                reasons_all[r] = reasons_all.get(r, 0) + len(cs)
            miss = why.get("누락", [])
            if miss:
                total_missing += len(miss)
                worst.append((label, name, miss))
            kept = len(have)
            note = " · ".join("%s %d" % (r, len(cs)) for r, cs in sorted(why.items()))
            log.append("  %-26s 네이버 %3d → 파일 %3d%s%s" % (name[:26], len(mem), kept,
                       ("  (빠짐: %s)" % note) if note else "", "  ← 확인 필요" if miss else ""))
        log.append("  빠진 이유 합계: " + (" · ".join("%s %d" % kv for kv in sorted(reasons_all.items())) or "없음"))

    log.append("\n" + "=" * 60)
    if total_missing:
        log.append("누락 %d건 — 아래 종목은 이유 없이 빠졌습니다:" % total_missing)
        for label, name, miss in worst[:30]:
            log.append("  %s %s: %s" % (label, name, ", ".join(miss[:10])))
    else:
        log.append("누락 0건 — 빠진 종목은 모두 이유가 있습니다 (ETF·우선주·60위 밖 등).")
    log.append("네이버 호출 %d회" % M.CALLS[0])
    text = "\n".join(log)
    print(text)
    open("mcap_verify.txt", "w", encoding="utf-8").write(text)
    print("\n저장: mcap_verify.txt")


if __name__ == "__main__":
    main()
