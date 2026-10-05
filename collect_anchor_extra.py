#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/anchor.json 에 은행·보험 종목을 보태 넣는다.

왜 필요한가
-----------
수집 순서가 이렇다.

  collect.py (DART 실적) -> data/index.json
      -> collect_prices.py -> data/returns.json
          -> collect_anchor.py -> data/anchor.json

맨 앞의 collect.py 가 금융업을 빼고 있다. 금융사는 매출액 대신 영업수익을
쓰는 등 계정 체계가 달라 실적 카드에 넣기 어렵기 때문이다. 그런데 그
제외가 끝까지 흘러내려와, '그때 샀다면' 카드에서 KB금융·삼성생명 같은
종목을 아예 고를 수 없게 됐다. 10년 수익률 카드에는 좋은 소재인데도.

주가만 필요한 일이라 실적 제외와 상관이 없다. 네이버는 호출 한도가
없으므로 이 종목들만 따로 받아 anchor.json 에 합쳐 넣는다.

쓰는 법
-------
  python3 collect_anchor.py          먼저 (anchor.json 을 새로 만든다)
  python3 collect_anchor_extra.py    그다음 (빠진 종목을 보탠다)

collect_anchor.py 가 매번 anchor.json 을 새로 쓰므로, 이 순서를 지켜야
한다. 자동 갱신에도 같은 순서로 한 줄 더 넣으면 된다.

  python3 collect_anchor_extra.py --list     무엇을 보탤지 보기만
  python3 collect_anchor_extra.py --force    분할 검사에 걸려도 저장
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
NAVER = ("https://api.finance.naver.com/siseJson.naver"
         "?symbol=%s&requestType=1&startTime=%s&endTime=%s&timeframe=%s")
ANCHOR = "data/anchor.json"

# 실적 수집에서 빠지는 은행·보험·일부 증권.
# 이름은 네이버가 주지 않으므로 여기 적어 둔다.
EXTRA = [
    # 은행·은행지주
    ("105560", "KB금융"),      ("055550", "신한지주"),
    ("086790", "하나금융지주"),  ("316140", "우리금융지주"),
    ("138930", "BNK금융지주"),  ("175330", "JB금융지주"),
    ("139130", "iM금융지주"),   ("024110", "기업은행"),
    # 보험
    ("032830", "삼성생명"),     ("000810", "삼성화재"),
    ("005830", "DB손해보험"),   ("001450", "현대해상"),
    ("085620", "미래에셋생명"),
    ("003690", "코리안리"),
    # 증권
    ("016360", "삼성증권"),     ("005940", "NH투자증권"),
]

# 한때 넣었다가 뺀 것들. 왜 뺐는지 남겨 두지 않으면 나중에 또 넣게 된다.
#   082640 동양생명    — 우리금융지주 인수로 상장폐지, 최근 시세 없음
#   010620 HD현대미포  — HD현대중공업에 흡수합병, 최근 시세 없음
# 다시 상장되거나 착오였다면 위 EXTRA 로 옮기면 된다.

SPLIT_TOL = 0.02          # 일별과 월말이 이보다 벌어지면 수정주가가 아니다
PAUSE = 0.15
_calls = [0]


def log(*a):
    print(*a)
    sys.stdout.flush()


def get_text(url, tries=3):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (fincard)",
        "Referer": "https://finance.naver.com/",
    })
    for i in range(tries):
        try:
            _calls[0] += 1
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace"), None
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            return None, "HTTP %d" % e.code
        except Exception as e:                # noqa: BLE001
            if i < tries - 1:
                time.sleep(1.0 * (i + 1))
                continue
            return None, type(e).__name__
    return None, "실패"


def naver_rows(code, start, end, frame):
    txt, why = get_text(NAVER % (code, start, end, frame))
    time.sleep(PAUSE)
    if not txt:
        return None, why
    try:
        rows = json.loads(txt.strip().replace("'", '"'))
    except Exception:                         # noqa: BLE001
        return None, "형식 오류"
    out = []
    for r in rows[1:]:
        try:
            v = float(r[4])
            if v > 0:
                out.append((str(r[0])[:8], v))
        except Exception:                     # noqa: BLE001
            continue
    out.sort()
    return (out, None) if out else (None, "값 없음")


def years_back(d, n):
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def month_span(d):
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first.strftime("%Y%m%d"), (nxt - timedelta(days=1)).strftime("%Y%m%d")


def on_or_before(rows, ymd):
    pick = None
    for d, v in rows:
        if d <= ymd:
            pick = (d, v)
        else:
            break
    return pick


def fmt(ymd):
    return "%s-%s-%s" % (ymd[:4], ymd[4:6], ymd[6:8])


def one(code, base, spans):
    """한 종목의 기준점.

    돌려주는 값: (결과, 분할경고, 실패사유)
    분할경고와 실패사유를 꼭 나눠야 한다. 섞으면 상장폐지 종목 하나 때문에
    멀쩡한 종목들까지 저장이 막힌다 — 실제로 그랬다.
    """
    # 월봉 한 번 — 액면분할 검사에 쓴다
    s = years_back(base, max(spans) + 1).strftime("%Y%m%d")
    mrows, _ = naver_rows(code, s, base.strftime("%Y%m%d"), "month")
    months = {}
    for d, v in (mrows or []):
        months[d[:6]] = v

    out, warn = {}, []
    for n in spans:
        tgt = years_back(base, n)
        a, b = month_span(tgt)
        rows, _ = naver_rows(code, a, b, "day")
        if not rows:
            continue                          # 상장 전이면 그 기간은 비운다
        hit = on_or_before(rows, tgt.strftime("%Y%m%d"))
        if not hit:
            continue
        mk = tgt.strftime("%Y%m")
        if months.get(mk):
            gap = abs(rows[-1][1] / months[mk] - 1)
            if gap > SPLIT_TOL:
                warn.append("%s %s: 일별 %.0f vs 월말 %.0f (%.2f배)"
                            % (code, mk, rows[-1][1], months[mk], rows[-1][1] / months[mk]))
        out[str(n)] = {"d": fmt(hit[0]), "v": hit[1]}

    if not out:
        return None, warn, "기준점 없음 (상장 1년 미만 또는 시세 없음)"

    st = (base - timedelta(days=14)).strftime("%Y%m%d")
    rows, _ = naver_rows(code, st, base.strftime("%Y%m%d"), "day")
    if not rows:
        return None, warn, "최근 종가 없음 (상장폐지·합병 추정)"
    out["now"] = {"d": fmt(rows[-1][0]), "v": rows[-1][1]}
    return out, warn, None


def main():
    argv = sys.argv[1:]
    try:
        with open(ANCHOR, encoding="utf-8") as f:
            j = json.load(f)
    except Exception:                         # noqa: BLE001
        log("!! %s 를 읽지 못했습니다. collect_anchor.py 를 먼저 돌리세요." % ANCHOR)
        return

    kr = j.get("kr") or {}
    items = kr.get("items") or {}
    ex = kr.get("excluded") or {}
    spans = j.get("spans") or [1, 2, 3, 5, 10, 15, 20]
    todo = [(c, n) for c, n in EXTRA if c not in items]

    log("anchor.json: 국내 %d종목 · 보탤 후보 %d개 · 이미 있음 %d개"
        % (len(items), len(todo), len(EXTRA) - len(todo)))
    if "--list" in argv:
        for c, n in todo:
            log("  %s  %s" % (c, n))
        return
    if not todo:
        log("보탤 것이 없습니다.")
        return

    # 기준일은 이미 들어 있는 종목들이 쓰는 날짜에 맞춘다.
    # 오늘 날짜로 잡으면 휴장일에 하루 어긋난다.
    base = datetime.now(KST).date()
    log("기준일 %s · 기간 %s\n" % (base, spans))

    got, warns, fail = {}, [], []
    for i, (code, name) in enumerate(todo, 1):
        r, w, why = one(code, base, spans)
        if w:
            warns.extend(w)
        if r:
            r["name"] = name
            got[code] = r
            have = [s for s in spans if str(s) in r]
            log("  %-8s %-14s 기간 %s · 현재 %s %s"
                % (code, name, ",".join(map(str, have)), r["now"]["d"],
                   "{:,.0f}".format(r["now"]["v"])))
        else:
            fail.append((code, name, why))
            log("  %-8s %-14s 건너뜀 — %s" % (code, name, why))

    if warns:
        log("\n" + "!" * 52)
        log("일별 종가와 월말 종가가 어긋납니다 (%d건)." % len(warns))
        log("수정주가가 아니라는 뜻이라 그대로 두면 수익률이 틀립니다.")
        log("저장하지 않고 멈춥니다. --force 로 넘길 수 있지만 권하지 않습니다.\n")
        for x in warns[:10]:
            log("  " + x)
        if "--force" not in argv:
            return

    if not got:
        log("\n받아온 것이 없어 저장하지 않습니다.")
        return

    items.update(got)
    for c in got:
        ex.pop(c, None)                       # 제외 목록에 있었다면 푼다
    kr["items"] = items
    kr["excluded"] = ex
    j["kr"] = kr
    j["extra_added"] = sorted(got)            # 무엇을 보탰는지 남긴다

    with open(ANCHOR, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, separators=(",", ":"))

    log("\n보탬 %d종목 → 국내 %d종목 · %.2fMB · 호출 %d회"
        % (len(got), len(items), os.path.getsize(ANCHOR) / 1024 / 1024, _calls[0]))
    if fail:
        log("건너뛴 %d종목:" % len(fail))
        for c, n, why in fail:
            log("  %-8s %-14s %s" % (c, n, why))


if __name__ == "__main__":
    main()
