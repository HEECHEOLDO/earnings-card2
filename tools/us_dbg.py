# 시험용 — 미국 종목 수집 과정 보기 (저장 안 함). CODES=티커(쉼표)
import os, sys, subprocess
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tk = [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]
import shutil
shutil.copytree("data/us", "/tmp/us_bak", dirs_exist_ok=True)
r = subprocess.run([sys.executable, "collect_us.py", "--debug"] + tk, capture_output=True, text=True, timeout=900)
out = r.stdout + r.stderr
import re
print(out[-6000:])
import json
for t in tk:
    try:
        j = json.load(open("data/us/%s.json" % t)); print("##", t, [(q["y"], q["q"], q.get("rev")) for q in j.get("quarterly", [])[-3:]])
    except Exception as e:
        print("##", t, e)
