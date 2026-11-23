# 시험용 — 최근 1년 새로 상장한 종목 (거래소 종가 파일에 처음 나온 날) + DART 증권신고서 공모가 → 공모가 대비 첫날·지금
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
cm = C.load_corp_map()
fs = sorted(glob.glob("data/krx/2*.json")); seen = set(); first = {}; closes = {}
for f in fs:
    d = int(os.path.basename(f)[:8]); c = json.load(open(f))["c"]
    for k, v in c.items():
        if k not in seen:
            seen.add(k)
            if d >= 20251120 and d > 20250305: first[k] = (d, v)
        closes[k] = (d, v)
res = []
for k, (d0, v0) in sorted(first.items(), key=lambda x: x[1][0]):
    m = cm.get(k)
    if not m: print("  매핑 없음", k); continue
    nm = m.get("name") or m.get("corp_name") or ""
    if "스팩" in nm or "기업인수목적" in nm or "리츠" in nm: continue
    r = C.api_get("estkRs.json", {"corp_code": m["corp_code"], "bgn_de": str(d0 - 20000), "end_de": str(d0)})
    prc = None
    for g in r.get("group") or []:
        if g["title"] == "증권의종류":
            for x in g["list"]:
                if x.get("stksen") in ("보통주", "기명식보통주", "기명식 보통주") and x.get("slprc") not in (None, "-", ""):
                    prc = int(str(x["slprc"]).replace(",", ""))
    res.append({"code": k, "name": nm, "list": d0, "d1": v0, "now": closes[k][1], "now_d": closes[k][0], "prc": prc})
    print("  ", k, nm, d0, prc, v0, closes[k][1], flush=True)
print("@@ipo", json.dumps(res, ensure_ascii=False))
