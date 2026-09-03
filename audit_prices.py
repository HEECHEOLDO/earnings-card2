#!/usr/bin/env python3
"""
data/returns.json 을 훑어 이상해 보이는 수익률을 찾아낸다.
네트워크를 쓰지 않고 이미 받아둔 파일만 읽는다.

사용법:
    python3 audit_prices.py                 # 전체 점검
    python3 audit_prices.py 035420 005930   # 특정 종목 값 출력
    python3 audit_prices.py --ref           # 알려진 값과 대조
"""

import json
import os
import sys

PATH = "data/returns.json"

# 액면분할이 반영 안 되면 수익률이 이런 값 근처로 떨어진다
RECENT_FROM = 2015          # 이 해부터만 이상을 따진다

# 네이버는 수정주가를 주므로 분할은 이미 반영돼 있다.
# 그래도 혹시 몰라 '정확히 딱 떨어지는' 하락만 본다.
# -50.8% 같은 값은 그냥 반토막 난 것이지 분할이 아니다.
SPLIT_HINTS = [(-50.0, "1:2"), (-66.7, "1:3"), (-75.0, "1:4"),
               (-80.0, "1:5"), (-90.0, "1:10"), (-95.0, "1:20")]

# 참고값 — 널리 알려진 연간 수익률(주가 기준, 배당 제외)
# 완전한 정답은 아니고 큰 차이를 잡아내기 위한 기준선이다.
# 참고값 — 실제 주가로 교차 확인한 것만 남긴다.
# 기억에 기대 적었던 값들은 오히려 틀려서 걷어냈다.
REF = {
    "005930": {  # 삼성전자 — 여러 경로로 확인됨
        "2016": 43.0, "2017": 41.4, "2018": -24.1, "2019": 44.2,
        "2020": 45.2, "2021": -3.3, "2022": -29.4, "2023": 42.0, "2024": -32.2},
    "035420": {  # NAVER — 2018년 1:5 분할 반영 기준
        "2018": -30.0, "2019": 52.9, "2020": 56.8,
        "2021": 29.4, "2022": -53.1},
    "035720": {  # 카카오 — 2021년 1:5 분할 반영 기준
        "2020": 153.8, "2021": 43.9, "2022": -52.8},
}
REF_NAMES = {"005930": "삼성전자", "035420": "NAVER", "035720": "카카오"}


def load():
    if not os.path.exists(PATH):
        sys.exit("%s 가 없습니다. 먼저 collect_prices.py 를 실행하세요." % PATH)
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def show(d, codes):
    for code in codes:
        it = d["items"].get(code)
        if not it:
            print("%s : 자료 없음" % code)
            continue
        ys = sorted(it["years"])
        print("\n%s (%s) · %d개 연도" % (it.get("name", code), code, len(ys)))
        for y in ys:
            v = it["years"][y]
            bar = "+" if v >= 0 else "-"
            print("  %s  %s%6.1f%%" % (y, bar, abs(v)))


def check_ref(d):
    print("=" * 66)
    print("알려진 값과 대조  (차이 3%p 넘으면 표시)")
    print("=" * 66)
    for code, ref in REF.items():
        it = d["items"].get(code)
        name = REF_NAMES.get(code, code)
        if not it:
            print("\n%-10s 자료 없음" % name)
            continue
        got = it["years"]
        rows, bad = [], 0
        for y in sorted(ref):
            if y not in got:
                rows.append("  %s  참고 %+6.1f%%   수집값 없음" % (y, ref[y]))
                continue
            diff = got[y] - ref[y]
            mark = "  ←" if abs(diff) > 3 else ""
            if mark:
                bad += 1
            rows.append("  %s  참고 %+6.1f%%   수집 %+6.1f%%   차이 %+5.1f%s"
                        % (y, ref[y], got[y], diff, mark))
        print("\n%-10s (%s)   %s" % (name, code, "이상 %d건" % bad if bad else "일치"))
        for r in rows:
            print(r)


def coverage(d):
    """수집 목록과 대조해 빠진 종목 수를 센다."""
    try:
        with open("data/index.json", encoding="utf-8") as f:
            all_kr = {c["code"]: c.get("name", c["code"])
                      for c in json.load(f).get("companies", [])}
    except Exception:                         # noqa: BLE001
        return
    have = set(d.get("items", {}))
    miss = [(c, n) for c, n in all_kr.items() if c not in have]
    print("\n국내 수집 범위  %d / %d종목" % (len(all_kr) - len(miss), len(all_kr)))
    if miss:
        print("  빠진 %d종목 — 상장폐지·신규상장·거래정지 등일 수 있습니다" % len(miss))
        for c, n in miss[:12]:
            print("    %-8s %s" % (c, n))
        if len(miss) > 12:
            print("    … 외 %d종목" % (len(miss) - 12))


def audit(d):
    items = d.get("items", {})
    n_split, n_wild, n_gap = [], [], []

    for code, it in items.items():
        ys = sorted(it.get("years", {}))
        if not ys:
            continue
        name = it.get("name", code)
        vals = [it["years"][y] for y in ys]
        # 평소 변동 폭 — 원래 출렁이는 종목은 -50% 가 이상하지 않다
        swing = sorted(abs(v) for v in vals)[len(vals)//2]

        # 연도 끊김
        gaps = [y for i, y in enumerate(ys[1:], 1) if int(y) != int(ys[i-1]) + 1]
        if gaps:
            n_gap.append((code, name, ", ".join(gaps)))

        for y in ys:
            v = it["years"][y]
            # 액면분할 흔적 — 최근 연도이고, 평소 얌전하던 종목일 때만 본다
            if int(y) >= RECENT_FROM and swing < 30:
                for target, ratio in SPLIT_HINTS:
                    if abs(v - target) <= 0.06:
                        n_split.append((code, name, y, v, ratio))
                        break
            # 터무니없는 값 — 오래된 해는 실제로 이런 일이 흔했다
            if int(y) >= RECENT_FROM and (v > 900 or v < -95):
                n_wild.append((code, name, y, v))

    print("\n" + "=" * 66)
    print("전체 점검  |  %d종목 · 갱신 %s" % (len(items), d.get("updated", "?")))
    print("=" * 66)
    print("  (%d년 이후만 · 소형주는 실제로 반토막·급등이 잦아 기준을 높게 잡았습니다)"
          % RECENT_FROM)
    print("  액면분할 의심  %3d건" % len(n_split))
    print("  극단값        %3d건" % len(n_wild))
    print("  연도 끊김      %3d종목" % len(n_gap))

    def dump(title, rows, fmt):
        if not rows:
            return
        print("\n" + "-" * 66)
        print(title)
        print("-" * 66)
        for r in rows[:30]:
            print(fmt(r))
        if len(rows) > 30:
            print("  … 외 %d건" % (len(rows) - 30))

    dump("액면분할이 반영 안 됐을 수 있는 해",
         n_split,
         lambda r: "  %-8s %-14s %s  %+6.1f%%  (%s 분할 크기)"
                   % (r[0], r[1][:14], r[2], r[3], r[4]))
    dump("극단값 (+900% 초과 또는 -95% 미만) — 확인해볼 만한 수준",
         n_wild,
         lambda r: "  %-8s %-14s %s  %+8.1f%%" % (r[0], r[1][:14], r[2], r[3]))
    dump("연도가 끊긴 종목",
         n_gap,
         lambda r: "  %-8s %-14s 끊긴 해 %s" % (r[0], r[1][:14], r[2]))

    coverage(d)

    print("\n특정 종목을 보려면:  python3 audit_prices.py 005930 035420")
    print("알려진 값과 대조:     python3 audit_prices.py --ref")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = load()
    if args:
        show(d, args)
        return
    if "--ref" in sys.argv:
        check_ref(d)
        return
    audit(d)


if __name__ == "__main__":
    main()
