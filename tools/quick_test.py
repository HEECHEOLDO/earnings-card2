"""시험용 — 빠른 갱신(올해 분기만) 결과를 저장하지 않고 출력"""
import os, sys, json
sys.path.insert(0, os.getcwd())
import collect as C
C.API_KEY = C.get_key()
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "272210").split(","):
    old = json.load(open("data/%s.json" % code))
    n0 = C._call_count
    d = C.quick_update(code, cmap, 2026)
    if not d:
        print("NONE", code); continue
    C.clean_quarters(d["quarterly"])
    print("QUICK", code, d["name"], "calls", C._call_count - n0, [(r["y"], r["q"], r["rev"], r["op"], r["ni"]) for r in d["quarterly"] if r["y"] >= 2025], flush=True)
    same = [r for r in d["quarterly"] if r["y"] < 2026] == [r for r in old["quarterly"] if r["y"] < 2026]
    print("   지난 분기 그대로:", same, "연간 그대로:", d["annual"] == old["annual"], flush=True)
