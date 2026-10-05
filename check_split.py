"""
네이버 일별 시세가 액면분할을 반영한 수정주가인지 직접 확인
- 액면분할한 대표 종목들의 '분할 이전 달' 일별 마지막 종가와 월봉 종가를 비교
- 같으면(1.00배) 일별도 수정주가 → collect_anchor 경고는 다른 원인

실행:  python3 check_split.py
"""
import ast
import urllib.request

URL = ("https://api.finance.naver.com/siseJson.naver?symbol={c}&requestType=1"
       "&startTime={s}&endTime={e}&timeframe={f}")
# (코드, 이름, 분할 이전 달, 분할 내용)
CASES = [
    ("005930", "삼성전자", "201610", "2018년 50:1 분할"),
    ("035420", "NAVER", "201610", "2018년 5:1 분할"),
    ("035720", "카카오", "201610", "2021년 5:1 분할"),
    ("002410", "범양건영", "201110", "경고 목록에 있던 종목"),
]


def closes(code, ym, frame):
    s, e = ym + "01", ym + "31"
    req = urllib.request.Request(URL.format(c=code, s=s, e=e, f=frame),
                                 headers={"User-Agent": "Mozilla/5.0",
                                          "Referer": "https://finance.naver.com/"})
    text = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    data = ast.literal_eval(text.strip())
    return [(str(r[0]).strip(), float(r[4])) for r in data[1:] if len(r) >= 5]


print("%-8s %-8s %-7s %12s %12s  %s" % ("코드", "이름", "달", "일별 마지막", "월봉 종가", "판정"))
for code, name, ym, note in CASES:
    try:
        d = closes(code, ym, "day")
        m = closes(code, ym, "month")
        dv, mv = d[-1][1], m[-1][1]
        r = dv / mv
        verdict = "같음 → 수정주가" if abs(r - 1) < 0.02 else "%.2f배 차이" % r
        print("%-8s %-8s %-7s %12.0f %12.0f  %s  (%s, 일별 마지막 %s)"
              % (code, name, ym, dv, mv, verdict, note, d[-1][0]))
    except Exception as ex:
        print("%-8s %-8s %-7s  조회 실패: %s" % (code, name, ym, ex))
