#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 탭의 지난 해 미국 합계를 원화로 바꿀 '연말 환율'을 data/rank.json 에 넣는다.

  python3 fill_fx_history.py

여러 곳을 차례로 시도한다 (먼저 되는 곳):
  1) 미 연준 FRED  원/달러 일별 (1981년~)       — 해마다 마지막 값
  2) Frankfurter (유럽중앙은행 기준환율, 1999년~) — 해마다 12월 31일 이전 마지막 값
1)이 안 되면 2)로 1999년부터 채우고, 그 전 해(1996~1998)는 비워 둔다 (원화 환산만 빠진다).
끝에 해마다 환율을 보여 주니, 대충 맞는지 눈으로 확인하면 된다. 두 번 돌려도 괜찮다.
"""
import json
import os
import time
import urllib.request

OUT = os.path.join("data", "rank.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv,text/plain,application/json,*/*"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def fred():
    out = {}
    for url in ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXKOUS",
                "https://fred.stlouisfed.org/data/DEXKOUS.txt"):
        try:
            txt = get(url)
        except Exception as e:                     # noqa: BLE001
            print("  FRED 실패 (%s): %r" % (url.split("/")[-1], e))
            continue
        for line in txt.splitlines():
            p = line.replace(",", " ").split()
            if len(p) == 2 and len(p[0]) == 10 and p[0][4] == "-":
                try:
                    out[int(p[0][:4])] = round(float(p[1]), 2)   # 날짜 순 → 해마다 마지막 값이 남는다
                except ValueError:
                    pass
        if len(out) > 10:
            return out, "FRED"
    return {}, ""


def frankfurter(years):
    out = {}
    for y in years:
        try:
            j = json.loads(get("https://api.frankfurter.app/%d-12-31?from=USD&to=KRW" % y))
            v = (j.get("rates") or {}).get("KRW")
            if v:
                out[y] = round(float(v), 2)
        except Exception as e:                     # noqa: BLE001
            print("  Frankfurter %d 실패: %r" % (y, e))
        time.sleep(0.3)
    return out, "Frankfurter(ECB)"


def main():
    rk = json.load(open(OUT, encoding="utf-8"))
    years = sorted(int(k) for k in rk["cols"] if k.isdigit())
    fx, src = fred()
    if not fx:
        fx, src = frankfurter([y for y in years if y >= 1999])
    if not fx:
        raise SystemExit("!! 환율을 어디서도 받지 못했습니다. 이 화면을 보내 주세요.")
    n = 0
    for y in years:
        if y in fx:
            rk["cols"][str(y)]["usdkrw"] = fx[y]; n += 1
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rk, f, ensure_ascii=False, separators=(",", ":"))
    print("출처 %s · %d개 해에 연말 환율을 넣었습니다" % (src, n))
    print("  " + " · ".join("%d %s" % (y, format(fx[y], ",.0f")) for y in years if y in fx))
    miss = [y for y in years if y not in fx]
    if miss:
        print("  환율 없는 해: %s (그 해 미국 카드는 원화 환산만 빠짐)" % ", ".join(map(str, miss)))


if __name__ == "__main__":
    main()
