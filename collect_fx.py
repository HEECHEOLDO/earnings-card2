#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""달러/원 환율 과거 시세를 모은다.  ->  data/fx_usdkrw.json

왜 필요한가
-----------
'10년 전 1억원 투자했다면' 을 해외 종목에 쓰려면 원화로 환산해야 한다.
2016년에 원화 1억을 달러로 바꿔 애플을 샀다가 2026년에 되팔아 원화로
돌아온 금액은, 달러 수익률만으로는 나오지 않는다. 환율이 10% 움직였으면
금액도 10% 어긋난다.

기존 data/fx.json 은 오늘 값 하나뿐이라(us.html 이 시가총액 환산에 쓴다)
과거 환율을 모른다. 그 파일은 건드리지 않고 따로 쌓는다.

출처
----
Frankfurter (api.frankfurter.dev) — 유럽중앙은행 기준환율. 키가 필요 없고
한도도 없다. 주말·유럽 공휴일은 값이 없으므로, 찾는 날짜가 비면 앞으로
며칠 물러선다.

주의: ECB 기준환율은 중앙유럽시간 16시 무렵 고시라, 한국 장 마감 시점의
매매기준율과는 조금 다르다. 10년 단위 카드에서는 무시할 만한 차이다.

쓰는 법
-------
  python3 collect_fx.py             없는 해만 채운다 (평소)
  python3 collect_fx.py --all       21년치를 처음부터 다시
  python3 collect_fx.py --check     2016-10-05 하루만 불러 확인
  python3 collect_fx.py --status    지금 파일에 뭐가 들었는지
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
API = "https://api.frankfurter.dev/v1/%s..%s?base=USD&symbols=KRW"
API_ONE = "https://api.frankfurter.dev/v1/%s?base=USD&symbols=KRW"
OUT = "data/fx_usdkrw.json"
YEARS_BACK = 21          # 20년 카드 + 여유 1년
BACKFILL = 10            # 그날 값이 없으면 며칠까지 물러설지


def log(*a):
    print(*a)
    sys.stdout.flush()


def get_json(url, tries=3):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "fincard/1.0"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            return None, "HTTP %d" % e.code
        except Exception as e:                # noqa: BLE001
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            return None, type(e).__name__
    return None, "실패"


def pull(a, b):
    """[a, b] 구간의 {날짜: 환율}. Frankfurter 는 영업일만 준다."""
    j, why = get_json(API % (a, b))
    if not j:
        return None, why
    out = {}
    for d, r in (j.get("rates") or {}).items():
        v = r.get("KRW") if isinstance(r, dict) else r
        if isinstance(v, (int, float)) and v > 0:
            out[d] = round(float(v), 2)
    return out, None


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            j = json.load(f)
        return j.get("rates") or {}
    except Exception:                         # noqa: BLE001
        return {}


def save(rates):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ks = sorted(rates)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(KST).strftime("%Y-%m-%d"),
            "source": "Frankfurter · 유럽중앙은행 기준환율",
            "pair": "USD/KRW",
            "note": "영업일만 있다. 비는 날은 앞으로 물러서서 쓴다.",
            "from": ks[0] if ks else "",
            "to": ks[-1] if ks else "",
            "count": len(ks),
            "rates": {k: rates[k] for k in ks},
        }, f, ensure_ascii=False, separators=(",", ":"))


def on_or_before(rates, ymd, back=BACKFILL):
    """그날 값이 없으면 앞으로 물러선다. (주말·공휴일)"""
    d = date(*map(int, ymd.split("-")))
    for _ in range(back + 1):
        k = d.strftime("%Y-%m-%d")
        if k in rates:
            return k, rates[k]
        d -= timedelta(days=1)
    return None, None


def status():
    try:
        with open(OUT, encoding="utf-8") as f:
            j = json.load(f)
    except Exception:                         # noqa: BLE001
        log("%s 가 아직 없습니다." % OUT)
        return
    r = j.get("rates") or {}
    log("갱신 %s · %s ~ %s · %d일치 · %.0fKB"
        % (j.get("updated"), j.get("from"), j.get("to"), len(r),
           os.path.getsize(OUT) / 1024))
    today = datetime.now(KST).date()
    log("\n카드에 쓰이는 날짜들")
    for n in (1, 2, 3, 5, 10, 15, 20):
        try:
            t = today.replace(year=today.year - n)
        except ValueError:
            t = today.replace(year=today.year - n, day=28)
        k, v = on_or_before(r, t.strftime("%Y-%m-%d"))
        log("  %2d년 전 %s → %s  1달러 = %s원"
            % (n, t, k or "없음", "{:,.2f}".format(v) if v else "-"))
    k, v = on_or_before(r, today.strftime("%Y-%m-%d"))
    log("  오늘      %s → %s  1달러 = %s원"
        % (today, k or "없음", "{:,.2f}".format(v) if v else "-"))


def main():
    argv = sys.argv[1:]
    if "--status" in argv:
        status()
        return

    if "--check" in argv:
        j, why = get_json(API_ONE % "2016-10-05")
        if not j:
            log("!! 불러오지 못했습니다: %s" % why)
            return
        log("응답 원문:")
        log("  " + json.dumps(j, ensure_ascii=False)[:300])
        v = (j.get("rates") or {}).get("KRW")
        log("\n2016-10-05  1달러 = %s원" % v)
        log("정상입니다." if v else "!! KRW 가 없습니다. 주소나 변수 이름이 바뀐 듯합니다.")
        return

    rates = {} if "--all" in argv else load()
    today = datetime.now(KST).date()
    y0 = today.year - YEARS_BACK

    # 해마다 끊어서 받는다. 한 번에 21년을 달라고 하면 잘릴 수 있고,
    # 끊어 받으면 중간에 실패해도 받은 데까지는 남는다.
    got = 0
    for y in range(y0, today.year + 1):
        # 이미 그해가 충분히 차 있으면 건너뛴다 (올해는 늘 다시 받는다)
        have = sum(1 for k in rates if k[:4] == str(y))
        if y < today.year and have >= 240:
            continue
        a = "%d-01-01" % y
        b = min(date(y, 12, 31), today).strftime("%Y-%m-%d")
        chunk, why = pull(a, b)
        if chunk is None:
            log("  %d년 실패 — %s" % (y, why))
            continue
        before = len(rates)
        rates.update(chunk)
        got += len(rates) - before
        log("  %d년  %d일치 (누적 %d)" % (y, len(chunk), len(rates)))
        time.sleep(0.4)

    if not rates:
        log("\n!! 받은 자료가 없어 저장하지 않습니다.")
        return

    # 카드가 실제로 쓰는 날짜가 다 채워졌는지 확인하고 저장한다
    miss = []
    for n in (1, 2, 3, 5, 10, 15, 20):
        try:
            t = today.replace(year=today.year - n)
        except ValueError:
            t = today.replace(year=today.year - n, day=28)
        k, _ = on_or_before(rates, t.strftime("%Y-%m-%d"))
        if not k:
            miss.append("%d년 전(%s)" % (n, t))
    if miss:
        log("\n! 다음 기준일에 환율이 없습니다: %s" % ", ".join(miss))
        log("  그 기간 해외 카드는 만들 수 없습니다.")

    save(rates)
    log("\n저장 %s · %d일치 · %.0fKB (새로 %d일)"
        % (OUT, len(rates), os.path.getsize(OUT) / 1024, got))


if __name__ == "__main__":
    main()
