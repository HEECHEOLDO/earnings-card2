"""
배당 액면분할 환산을 새 규칙으로 다시 계산한다 (한 번만 돌리면 된다).

  python3 fix_splits.py

· data/{종목코드}.json 의 dps_adj(분할 반영 주당배당금)·split_adjusted 를 다시 채운다
· 그다음 data/screen.json 을 다시 만든다 (연속 배당 증가·배당 성장률이 바뀐다)
API 는 쓰지 않는다. 이후 매일 수집에서는 collect.py 가 같은 규칙으로 계산한다.
"""
import json
import os

import collect

n = 0
for fn in sorted(os.listdir(collect.OUT_DIR)):
    if not (fn.endswith(".json") and fn[:-5].isdigit()):
        continue
    path = os.path.join(collect.OUT_DIR, fn)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    a = d.get("annual")
    if not a:
        continue
    before = ([r.get("dps_adj") for r in a], bool(d.get("split_adjusted")))
    sp = collect.adjust_for_splits(a)
    if before != ([r.get("dps_adj") for r in a], sp):
        d["split_adjusted"] = sp
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        n += 1
print("주당배당금 환산을 고친 종목: %d곳" % n)
print("screen.json 다시 만듦: %d종목" % collect.build_screen())
