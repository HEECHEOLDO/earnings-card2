"""국내 분기 실적 계산 시험 — 회사 몇 곳의 최근 분기를 출력만 한다 (저장 안 함)"""
import os, sys
sys.path.insert(0, os.getcwd())
import collect as C
C.API_KEY = C.get_key()
cmap = C.load_corp_map()
for code in (os.environ.get("CODES") or "272210,120110,000880,084850,009440,005930").split(","):
    info = cmap.get(code)
    q = C.collect_quarterly(info["corp_code"], 2026)
    print("RESULT", code, info["name"], [(r["y"], r["q"], r["rev"], r["op"], r["ni"]) for r in q[-4:]], flush=True)
