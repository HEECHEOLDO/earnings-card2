# 시험용 — 카드의 10-Q XBRL 원문에서 이 기간 순이익·매출 후보 (차원 없는 값만)
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import xbrl_dims as XD
for t in (os.environ.get("CODES") or "REG").split(","):
    d = json.load(open("data/flow/%s.json" % t))
    cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
    got = F._us_files(cik, d["src"])
    ctx, facts = XD.parse(got[0])
    print("==", t, d["start"], d["end"], "카드", d["rev"], d["op"], d["ni"])
    for n, c, v in facts:
        p = ctx.get(c) or {}
        if p.get("start") == d["start"] and p.get("end") == d["end"] and not p.get("dims") and re.search(r"NetIncome|ProfitLoss|Revenue|OperatingIncome|IncomeLoss", n):
            print("   ", n, round(v / 1e6, 1))
