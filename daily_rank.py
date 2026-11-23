"""주가 탭 '역대 상승폭·하락폭 순위'(하루 등락률)용 — 일별 종가로 기간별 상위 10일을 미리 뽑아 둔다 (2026-11)

차트 파일의 "d" 는 최근 약 400일 일별뿐이라 2~10년은 화면에서 셀 수 없다. 그래서 모으는 쪽에서
긴 일별 종가로 계산해 "r" 로 붙인다:
  "r": {"2y": {"up": [[YYYYMMDD, 등락률%], ...10], "dn": [...5]}, "3y": {...}, … "10y": {...}, "end": YYYYMMDD}
등락률 = 그날 종가 ÷ 직전 거래일 종가 − 1 (수정주가 기준).
"""
from datetime import date

SPANS = tuple(range(2, 11))          # 2·3·…·10년 (1년 이하는 화면이 일별 종가로 센다)


def _d(n):
    n = int(n)
    return date(n // 10000, n // 100 % 100, n % 100)


def rank(rows, skip=None, top=10):
    """rows: [(YYYYMMDD, 종가)] 날짜순 일별. skip(직전, 오늘, 비율) 가 True 면 그날은 뺀다(분할 미반영 등).
    돌려주는 값: {"3y": {...}, ..., "end": 마지막 날} — 기간을 다 채우지 못하는(상장이 더 늦은) 기간은 상장 뒤만 센다"""
    rows = [(int(a), float(b)) for a, b in rows if b and float(b) > 0]
    if len(rows) < 30:
        return None
    end = _d(rows[-1][0])
    ch = []
    for i in range(1, len(rows)):
        p, c = rows[i - 1][1], rows[i][1]
        r = c / p
        if skip and skip(p, c, r):
            continue
        ch.append((rows[i][0], round((r - 1) * 100, 2)))
    out = {"end": rows[-1][0]}
    first = rows[0][0]
    for n in SPANS:
        try:
            st = end.replace(year=end.year - n)
        except ValueError:                        # 2월 29일
            st = end.replace(year=end.year - n, day=28)
        s0 = int(st.strftime("%Y%m%d"))
        xs = [x for x in ch if x[0] > s0]
        up = sorted([x for x in xs if x[1] > 0], key=lambda x: -x[1])[:top]
        dn = sorted([x for x in xs if x[1] < 0], key=lambda x: x[1])[:top]
        out["%dy" % n] = {"up": [list(x) for x in up], "dn": [list(x) for x in dn], "all": first > s0}       # all: 상장이 기간 시작보다 늦다 (상장 뒤만 셈)
    return out
