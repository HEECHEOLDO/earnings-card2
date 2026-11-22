# 시험용 — 미국 카드 10-Q XBRL 의 매출 사실 중 차원이 하나인 것 (축별 합 vs 매출)
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import flow_xbrl as FX
import xbrl_dims as XD
for t in (os.environ.get("CODES") or "NFLX").split(","):
    try:
        d = json.load(open("data/flow/%s.json" % t))
        cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
        got = F._us_files(cik, d["src"])
        ctx, facts = XD.parse(got[0])
        print("==", t, d["start"], d["end"], "매출", d["rev"], flush=True)
        ax = {}
        for n, c, v in facts:
            p = ctx.get(c) or {}
            if p.get("start") == d["start"] and p.get("end") == d["end"] and len(p.get("dims") or []) == 1 and re.search(r"Revenue|Sales", n) and not re.search(r"Cost|Expense|Deferred|Receivable|Tax", n):
                a, m = p["dims"][0]
                ax.setdefault((n, a), {})[m] = round(v / 1e6, 1)
        for (n, a), g in ax.items():
            print("   ", n.split(":")[-1][:50], a.split(":")[-1][:45], "합", round(sum(g.values()), 1), "|", "; ".join("%s=%s" % (m.split(":")[-1][:30], x) for m, x in list(g.items())[:9]))
    except Exception as e:                       # noqa: BLE001
        print("==", t, "오류", e)
