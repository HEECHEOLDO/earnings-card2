# 시험용 — XBRL 없는 최신 보고서를 API 카드로 (저장 안 함)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import collect_flow as F
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "012450").split(","):
    corp = cm[code]["corp_code"]
    F.FX.WHY = ""
    v = F.kr_xbrl(corp, None)
    if isinstance(v, dict):
        d = F.scaled(v, 1e8)
        print("==", code, cm[code]["name"], {k: d.get(k) for k in ("rev", "cogs", "gross", "sga", "op", "tax", "ni", "cum_rev", "period", "report", "from_api", "seg_from", "seg_note")})
        print("   segs", d.get("segs"), "items", d.get("items"))
        t = json.load(open("data/%s.json" % code))
        print("   탭", [r for r in t["quarterly"] if r["y"] == 2026])
    else:
        print("==", code, v, F.FX.WHY)
