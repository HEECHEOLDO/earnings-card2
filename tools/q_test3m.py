"""국내 분기 실적 계산 시험 — 수정본(collect_3m)과 지금(collect)을 나란히 출력만 한다 (저장 안 함)"""
import os, sys
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import collect as C0
import collect_3m as C
C.API_KEY = C.get_key(); C0.API_KEY = C.API_KEY
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "272210,120110").split(","):
    info = cmap.get(code)
    q = C.collect_quarterly(info["corp_code"], 2026)
    q0 = C0.collect_quarterly(info["corp_code"], 2026)
    print("NEW", code, info["name"], [(r["y"], r["q"], r["rev"], r["op"], r["ni"]) for r in q[-4:]], flush=True)
    print("OLD", code, info["name"], [(r["y"], r["q"], r["rev"], r["op"], r["ni"]) for r in q0[-4:]], flush=True)
