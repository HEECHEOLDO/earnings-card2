#!/usr/bin/env python3
"""
data/us/*.json 을 훑어 이상해 보이는 배당 데이터를 찾아낸다.
SEC 호출 없이 이미 받아둔 파일만 읽는다.

사용법:
    python3 audit_us.py              # 전체 점검
    python3 audit_us.py --all        # 정상 종목까지 모두 출력
    python3 audit_us.py NVDA AAPL    # 특정 종목만
"""

import json
import os
import sys

DIR = "data/us"
CLEAN = [2, 3, 4, 5, 7, 10, 20, 40, 50]


def load(code):
    with open(os.path.join(DIR, code + ".json"), encoding="utf-8") as f:
        return json.load(f)


def dps_of(a):
    v = a.get("dps_adj")
    return v if v is not None else a.get("dps")


def check(d):
    """이상 징후 목록을 돌려준다.

    핵심 아이디어:
      배당성향은 '지급액 ÷ 순이익' 이라 액면분할과 무관하다.
      그래서 배당성향이 알려주는 배당 증감과 주당배당금의 증감이
      어긋나면, 주당배당금 쪽 기준이 깨진 것이다.
      실제로 배당을 깎았다면 둘 다 똑같이 줄어든다.
    """
    issues = []
    ann = d.get("annual", [])

    # 배당 지급액을 되살린다: 배당성향 × 순이익
    paid = {}
    for a in ann:
        po, ni = a.get("payout"), a.get("ni")
        if po and ni and po > 0 and ni > 0:
            paid[a["p"]] = po / 100.0 * ni

    rows = [a for a in ann if dps_of(a)]
    for i in range(1, len(rows)):
        py, cy = rows[i - 1]["p"], rows[i]["p"]
        pv, cv = dps_of(rows[i - 1]), dps_of(rows[i])
        if py not in paid or cy not in paid or not pv or not cv:
            continue
        if pv <= 0 or cv <= 0 or paid[py] <= 0:
            continue
        dps_ratio = cv / pv
        paid_ratio = paid[cy] / paid[py]
        if paid_ratio <= 0:
            continue
        gap = dps_ratio / paid_ratio          # 1 이면 둘이 일치
        for cand in CLEAN:
            for direction in (cand, 1.0 / cand):
                if 0.9 <= gap / direction <= 1.1:
                    issues.append(
                        "FY%d→FY%d 주당배당금은 %.2f배인데 실제 배당 지급은 %.2f배 "
                        "(%d배 어긋남)" % (py, cy, dps_ratio, paid_ratio, cand))
                    break
            else:
                continue
            break

    if d.get("restated_from"):
        issues.append("FY%d 부터 실적 기준 변경" % d["restated_from"])

    return issues


def main():
    args = [a.upper() for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv

    if not os.path.isdir(DIR):
        sys.exit("%s 폴더가 없습니다. 먼저 collect_us.py 를 실행하세요." % DIR)

    codes = args or sorted(
        f[:-5] for f in os.listdir(DIR)
        if f.endswith(".json") and not f.startswith("_") and f != "index.json")

    flagged, noted, split_ok, nodiv, clean = [], [], [], 0, 0
    for code in codes:
        try:
            d = load(code)
        except Exception:                 # noqa: BLE001
            continue
        if not any(dps_of(a) for a in d.get("annual", [])):
            nodiv += 1
            continue
        iss = check(d)
        # 기준 변경만 걸린 경우는 '오류'가 아니라 '참고'다
        if iss and all("기준 변경" in m for m in iss):
            noted.append((code, d, iss))
        elif iss:
            flagged.append((code, d, iss))
        else:
            clean += 1
            if d.get("split_adjusted"):
                split_ok.append(code)

    print("=" * 70)
    print("배당 데이터 점검  |  총 %d종목" % len(codes))
    print("=" * 70)
    print("  무배당(점검 제외) %3d" % nodiv)
    print("  이상 없음        %3d   (이 중 분할 보정된 종목 %d개)"
          % (clean, len(split_ok)))
    print("  확인 필요        %3d" % len(flagged))
    print("  참고(기준 변경)   %3d" % len(noted))

    if split_ok:
        print("\n분할 보정이 적용되고 결과도 매끄러운 종목")
        for i in range(0, len(split_ok), 12):
            print("  " + " ".join(split_ok[i:i + 12]))

    if flagged:
        print("\n" + "-" * 70)
        print("확인이 필요한 종목")
        print("-" * 70)
        for code, d, iss in flagged:
            print("\n%s  (분할보정 %s)" % (code, "O" if d.get("split_adjusted") else "X"))
            for m in iss:
                print("   · " + m)
            vals = [(a["p"], dps_of(a)) for a in d.get("annual", []) if dps_of(a)]
            print("   DPS: " + " ".join("%d:$%.3f" % v for v in vals[-8:]))

    if noted:
        print("\n" + "-" * 70)
        print("참고 — 사업 분할 등으로 실적 기준이 바뀐 종목 (오류 아님)")
        print("-" * 70)
        for code, d, iss in noted:
            print("  %-7s %s" % (code, iss[0]))

    if show_all:
        print("\n" + "-" * 70)
        print("전체 배당 종목 DPS")
        print("-" * 70)
        for code in codes:
            try:
                d = load(code)
            except Exception:             # noqa: BLE001
                continue
            vals = [(a["p"], dps_of(a)) for a in d.get("annual", []) if dps_of(a)]
            if vals:
                print("%-7s %s" % (code, " ".join("$%.3f" % v[1] for v in vals[-8:])))

    print("\n끝. 확인이 필요한 종목은 다음으로 자세히 보세요.")
    print("   python3 collect_us.py --debug 티커")


if __name__ == "__main__":
    main()
