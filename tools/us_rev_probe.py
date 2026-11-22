# 시험용 — '매출 기간 없음' 회사: 최근 10-Q/10-K XBRL 의 차원 없는 매출 후보 사실과 기간
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
import xbrl_dims as XD
for t in (os.environ.get("CODES") or "ODFL").split(","):
    try:
        cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
        rc = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))["filings"]["recent"]
        i = next(i for i, f in enumerate(rc["form"]) if f in ("10-Q", "10-K"))
        got = F._us_files(cik, rc["accessionNumber"][i])
        ctx, facts = XD.parse(got[0])
        print("==", t, rc["form"][i], rc["reportDate"][i], rc["accessionNumber"][i], "facts", len(facts), "ctx", len(ctx), flush=True)
        seen = set()
        for n, c, v in facts:
            p = ctx.get(c) or {}
            if len(p.get("dims") or []) <= 1 and re.search(r"Revenue|Sales", n) and not re.search(r"Cost|Deferred|Receivable|IncomeTax|Percentage|Remaining|Unbilled|Liability|Asset", n) and p.get("start"):
                k = (n, p["start"], p["end"])
                if k in seen: continue
                seen.add(k)
                if p["end"] >= rc["reportDate"][i][:7]:
                    print("   ", n, p["start"], p["end"], round(v / 1e6, 1), p.get("dims"))
    except Exception as e:                       # noqa: BLE001
        print("==", t, "오류", repr(e))
