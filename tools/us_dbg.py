# 시험용 — 미국 종목 수집 과정 보기 (저장 안 함). CODES=티커(쉼표)
import os, sys, subprocess
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tk = [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]
import shutil, json
shutil.copytree("data/us", "/tmp/us_bak", dirs_exist_ok=True)
before = {}
for t in tk:
    try: before[t] = {(q["y"], q["q"]): q.get("rev") for q in json.load(open("data/us/%s.json" % t)).get("quarterly", [])}
    except Exception: before[t] = {}
r = subprocess.run([sys.executable, "collect_us.py", "--debug"] + tk, capture_output=True, text=True, timeout=900)
out = r.stdout + r.stderr
import re
print("\n".join(l for l in out.splitlines() if "보충" in l or "인스턴스" in l or "못 받음" in l))
import json
for t in tk:
    try:
        j = json.load(open("data/us/%s.json" % t)); now = {(q["y"], q["q"]): q.get("rev") for q in j.get("quarterly", [])}
        diff = [(k, before[t].get(k), now.get(k)) for k in sorted(set(now) | set(before[t])) if before[t].get(k) != now.get(k)]
        print("##", t, "마지막", sorted(now)[-1] if now else None, "바뀐 칸", diff[:8])
    except Exception as e:
        print("##", t, e)
