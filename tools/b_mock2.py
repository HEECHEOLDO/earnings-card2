# 시험용 2 — 투자자별 순매수(시장 일별, 네이버 → 거래소 값) 1년 · KIND 메뉴 주소 목록에서 사이드카 찾기 · 예탁금 후보
import os, sys, re, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import urllib.request
from datetime import date, timedelta
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r: return r.status, r.read().decode("utf-8", "replace")
    except Exception as e: return "ERR", repr(e)[:200]
st, t = get("https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain")
mp = re.findall(r'"(ULD[A-Z0-9]+)"\s*:\s*"([^"]+)"', t)
print("== KIND 메뉴 주소", len(mp))
for k, u in mp:
    if re.search(r"market|measure|halt|side|circuit|trade", u, re.I): print("   ", k, u)
nm = re.findall(r'menuId\s*==\s*"(ULD[A-Z0-9]+)"[^}]{0,200}', t)
for m in re.findall(r"(사이드카|서킷브레이커|시장조치)[^<\"']{0,60}", t)[:20]: print("   글자", m)
# 투자자별 순매수 (코스피·코스닥) 최근 1년 — 거래일만 값이 온다
res = {"KOSPI": [], "KOSDAQ": []}
d = date(2026, 11, 20); n = 0
while d >= date(2025, 11, 20):
    if d.weekday() < 5:
        for ix in ("KOSPI", "KOSDAQ"):
            st, t = get("https://m.stock.naver.com/api/index/%s/trend?bizdate=%s" % (ix, d.strftime("%Y%m%d")))
            try:
                j = json.loads(t)
                if j.get("bizdate") == d.strftime("%Y%m%d"):
                    f = lambda s: int(str(s).replace(",", "").replace("+", ""))
                    res[ix].append([int(j["bizdate"]), f(j["personalValue"]), f(j["foreignValue"]), f(j["institutionalValue"])])
            except Exception:
                pass
            time.sleep(0.05)
    d -= timedelta(days=1)
for ix in res: res[ix].sort()
print("@@investor", json.dumps(res))
print("== investor", {k: (len(v), v[-1] if v else None) for k, v in res.items()})
