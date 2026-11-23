# 시험용 — collect_market 부분 실행 후 결과 확인 (저장소에 올리지 않음)
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_market as M
for part in (os.environ.get("CODES") or "ipo").split(","):
    M.PARTS[part]()
    if part == "ipo":
        j = json.load(open("data/market/ipo.json"))
        for r in j["items"]:
            if r["name"] in ("케이뱅크", "에임드바이오", "씨엠티엑스", "아크릴", "세미파이브", "마키나락스"): print("  ", r)
        print("   공모가 대비 오른 곳", sum(1 for r in j["items"] if r["now"] > r["prc"]), "/", len(j["items"]))
    if part == "insider":
        j = json.load(open("data/market/insider_us.json"))
        for r in j["buy"][:12]: print("   매수", r["t"], r["who"], r["title"], r["usd"], r["date"])
    if part == "investor":
        j = json.load(open("data/market/investor.json")); print("   ", j["KOSPI"][-3:])
