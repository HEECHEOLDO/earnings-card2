#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시총 순위 탭(rank.html)용 — 해마다 연말 시가총액 순위를 모은다.

  python3 collect_rank.py            빠진 연도 채우기 + '현재' 갱신
  python3 collect_rank.py --force    연말 자료도 전부 다시 받기
  python3 collect_rank.py --show     받아 둔 것 보기 (호출 0회)

출처: 공공데이터포털 '금융위원회_주식시세정보' (2020년 말부터, 날짜 하나에 전 종목 시가총액)
키:   환경변수 DATA_GO_KEY (GitHub 비밀값) 또는 datago_key.txt — Encoding·Decoding 키 다 된다.
결과: data/rank.json
  cols  { "2020": {...}, "2021": {...}, ..., "now": {...} }
        각 칸: date(그 해 마지막 거래일), kospi·kosdaq·all = [[코드, 이름, 시총(억)], ...] 상위 30
연말 자료는 한 번 받으면 다시 받지 않는다(바뀌지 않으니까). 매일은 '현재' 한 칸만 받는다.
1월이 되면 지난해 연말이 저절로 한 칸 늘어난다.
2010~2019(KRX)·1990년대(CSV)는 나중에 같은 파일에 칸을 더한다 (src 로 구분).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "rank.json")
START = 2020            # 공공데이터포털 자료가 있는 첫 해
TOP = 50                # 칸마다 몇 위까지 적을지 (시가총액 탭 과거 연도 TOP 50 까지)
URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
# 시가총액 탭과 같은 기준 — 우선주·스팩은 뺀다
BAD = re.compile(r"(우|우B|\d우[BC]?|우\(전환\)|스팩\d*호?|MF)$|기업인수목적|우선$|\(\d?우[A-C]?\)|\d신$|뮤추얼")


def ordinary(code):
    """보통주만 — 우선주·신주는 코드 끝자리가 0이 아니다 (005935 삼성전자우, 005931 삼성전자1신)"""
    return code[-1:] == "0"


def tidy(name):
    """'데 이 콤' · '유    공' 처럼 글자마다 띄운 옛 이름을 붙인다"""
    t = name.split()
    return "".join(t) if len(t) > 1 and all(len(x) == 1 for x in t) else " ".join(t)
CALLS = [0]


def log(*a):
    print(*a, flush=True)


def get_key():
    k = os.environ.get("DATA_GO_KEY", "").strip()
    if not k and os.path.exists("datago_key.txt"):
        k = open("datago_key.txt", encoding="utf-8").read().strip()
    if not k:
        sys.exit("!! 공공데이터포털 키가 없습니다 (DATA_GO_KEY 또는 datago_key.txt)")
    return urllib.parse.unquote(k)


def day_rows(key, d):
    """그날 전 종목 [(코드, 이름, 시장, 시총원)] — 장이 안 열린 날이면 []"""
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": key, "resultType": "json", "basDt": d.strftime("%Y%m%d"),
                                    "numOfRows": 1000, "pageNo": page})
        for t in range(3):
            try:
                CALLS[0] += 1
                raw = urllib.request.urlopen(URL + "?" + q, timeout=40).read().decode("utf-8", "replace")
                j = json.loads(raw)
                break
            except Exception as e:             # noqa: BLE001
                if t == 2:
                    raise RuntimeError("공공데이터포털 응답 이상: %r" % e)
                time.sleep(2 + 3 * t)
        body = j.get("response", {}).get("body", {})
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        for r in items:
            out.append((r.get("srtnCd", ""), r.get("itmsNm", ""), r.get("mrktCtg", ""),
                        int(r.get("mrktTotAmt") or 0)))
        total = int(body.get("totalCount") or 0)
        if not items or len(out) >= total:
            return out
        page += 1
        time.sleep(0.3)


def last_trading(key, d, back=10):
    """d 부터 거꾸로, 자료가 있는 첫 날"""
    for _ in range(back):
        rows = day_rows(key, d)
        if rows:
            return d, rows
        d -= timedelta(days=1)
        time.sleep(0.3)
    return None, []


def column(d, rows):
    keep = [(c, tidy(n), m, cap) for c, n, m, cap in rows
            if m in ("KOSPI", "KOSDAQ") and cap > 0 and ordinary(c) and not BAD.search(n)]

    def top(ms):
        rs = sorted((r for r in keep if r[2] in ms), key=lambda r: -r[3])[:TOP]
        return [[c, n, round(cap / 1e8)] for c, n, _, cap in rs]
    return {"date": d.isoformat(), "src": "datago",
            "kospi": top(("KOSPI",)), "kosdaq": top(("KOSDAQ",)), "all": top(("KOSPI", "KOSDAQ"))}


def show(j):
    log("받은 날 %s · 칸 %d개" % (j.get("updated"), len(j.get("cols", {}))))
    for k in sorted(j.get("cols", {}), key=lambda k: (k == "now", k)):
        c = j["cols"][k]
        log("  %-5s %s  코스피 1~3위: %s" % (k, c["date"], " · ".join(r[1] for r in c["kospi"][:3])))


def main():
    try:
        j = json.load(open(OUT, encoding="utf-8"))
    except Exception:                          # noqa: BLE001
        j = {"cols": {}}
    if "--show" in sys.argv:
        return show(j)
    key, force = get_key(), "--force" in sys.argv
    cols = j.setdefault("cols", {})
    today = datetime.now(KST).date()

    for y in range(START, today.year):         # 지난 해들의 연말
        if str(y) in cols and not force:
            continue
        d, rows = last_trading(key, date(y, 12, 31))
        if not rows:
            log("  ! %d 연말 자료를 못 찾았습니다" % y)
            continue
        cols[str(y)] = column(d, rows)
        log("  %d  %s  코스피 1위 %s" % (y, d, cols[str(y)]["kospi"][0][1]))

    # 현재 — 공공데이터포털은 하루 늦게 올라온다. 어제부터 거꾸로 찾는다.
    d, rows = last_trading(key, today - timedelta(days=1))
    if rows:
        keep = {k: v for k, v in (cols.get("now") or {}).items() if k.startswith("us")}   # 미국 칸은 collect_us_mcap.py 몫
        cols["now"] = column(d, rows)
        cols["now"].update(keep)
        log("  현재 %s  코스피 1위 %s" % (d, cols["now"]["kospi"][0][1]))
    else:
        log("  ! 최근 자료를 못 찾아 '현재'는 그대로 둡니다")

    j.update({"updated": today.isoformat(), "unit": "억원",
              "source": "공공데이터포털 금융위원회_주식시세정보", "top": TOP})
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    log("저장 %s · 칸 %d개 · 호출 %d회" % (OUT, len(cols), CALLS[0]))


if __name__ == "__main__":
    main()
