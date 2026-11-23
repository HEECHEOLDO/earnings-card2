# 시험용 — 자사주 취득 결정 상위 건을 DART 원문 문서의 '취득예정금액'과 대조
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import probe_audit as P
items = json.load(open("data/market/buyback.json"))["items"][:12]
for x in items:
    doc = P.fetch_doc(x["rcept"]) or ""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", doc))
    m = re.search(r"취득\s*예정\s*금액[^0-9]{0,80}([\d,]{5,})", t)
    print(x["name"], x["rcept"], "API", "{:,}".format(x["won"]), "| 원문", m.group(1) if m else "못찾음", "|", t[t.find("취득예정금액"):t.find("취득예정금액") + 160] if "취득예정금액" in t else "", flush=True)
