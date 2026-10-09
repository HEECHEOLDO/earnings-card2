#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'그때 샀다면' 해외 탭을 열 수 있는지 본다.

  python3 us_status.py

collect_prices.py --status 는 전체 548종목 기준이라 '20일 남았다' 고 한다.
하지만 카드에 필요한 건 CARD_US 122종목뿐이다. 그게 얼마나 찼는지,
언제쯤 열 수 있는지만 본다.
"""

import datetime
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_card_list():
    p = os.path.join(HERE, "collect_prices.py")
    if not os.path.exists(p):
        print("!! collect_prices.py 를 찾지 못했습니다 (fincard 폴더에서 실행하세요)")
        return None
    spec = importlib.util.spec_from_file_location("cp", p)
    m = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["x"]                          # import 중 인자를 읽지 않게
    try:
        spec.loader.exec_module(m)            # main() 은 __main__ 가드로 안 돈다
    finally:
        sys.argv = old
    return getattr(m, "CARD_US", None)


def main():
    card = load_card_list()
    if not card:
        print("!! CARD_US 목록이 없습니다. collect_prices.py 가 최신인지 확인하세요.")
        return

    try:
        mon = json.load(open("data/monthly_us.json", encoding="utf-8"))["items"]
    except Exception as e:                    # noqa: BLE001
        print("!! data/monthly_us.json 을 못 읽었습니다 (%s)" % e)
        return

    have = sorted(c for c in card if c in mon)
    miss = sorted(set(card) - set(mon))
    pct = 100.0 * len(have) / len(card)

    print("월말 종가 전체      %d종목" % len(mon))
    print("카드용 확보        %d / %d  (%.0f%%)" % (len(have), len(card), pct))
    bar = int(pct / 2.5)
    print("                   [%s%s]" % ("■" * bar, "·" * (40 - bar)))

    # 기간별로 실제 몇 종목이 카드에 쓸 수 있는지 (21년치가 다 있는 건 아니다)
    print("\n기간별로 쓸 수 있는 카드용 종목")
    for n in (1, 3, 5, 10, 15, 20):
        ok = 0
        for c in have:
            v = mon[c].get("v") or []
            # 끝에서부터 값이 있는 칸을 찾고, 거기서 n*12 달 앞이 있는지
            e = len(v) - 1
            while e >= 0 and v[e] is None:
                e -= 1
            j = e - n * 12
            if j >= 0 and v[j] is not None:
                ok += 1
        print("  %2d년  %3d종목" % (n, ok))

    if miss:
        print("\n아직 안 받은 카드용 %d종목" % len(miss))
        print("  " + " ".join(miss[:30]) + (" …" if len(miss) > 30 else ""))
        days = -(-len(miss) // 24)            # 하루 24종목 (주별 보정 1회 제외)
        when = datetime.date.today() + datetime.timedelta(days=days)
        print("\n하루 24종목이면 %d일 — %s 쯤 다 찹니다" % (days, when.strftime("%m월 %d일")))
    else:
        print("\n카드용 종목을 모두 받았습니다. 해외 탭을 열 수 있습니다.")

    print("\n" + "─" * 46)
    if pct >= 80:
        print("80%% 를 넘었습니다. 지금 해외 탭을 만들어도 됩니다.")
    elif pct >= 40:
        print("절반쯤 왔습니다. 조금만 더 기다리는 편이 낫습니다.")
    else:
        print("아직 이릅니다. 고른 종목이 자주 '자료 없음' 으로 나올 겁니다.")


if __name__ == "__main__":
    main()
