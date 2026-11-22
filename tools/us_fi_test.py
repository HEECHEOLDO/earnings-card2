# 시험용 — 최근 10-Q/10-K XBRL 로 카드를 다시 만들면 어떻게 나오는지 (저장 안 함), 지금 카드와 비교
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
import flow_xbrl as FX
for t in (os.environ.get("CODES") or "ODFL").split(","):
    try:
        old = json.load(open("data/flow/%s.json" % t))
        cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
        rc = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))["filings"]["recent"]
        i = next(i for i, f in enumerate(rc["form"]) if f in ("10-Q", "10-K"))
        got = F._us_files(cik, rc["accessionNumber"][i])
        FX.WHY = ""
        v = FX.from_instance(got[0], got[1], us=True, caltext=got[2])
        if not v:
            print("==", t, "실패", FX.WHY); continue
        v = F.scaled(v, 1e6)
        print("==", t, v["start"], v["end"], "매출 %s 영업 %s 순 %s" % (v["rev"], v["op"], v["ni"]), "| 지금 카드", old.get("period"), old["rev"], old["op"], old["ni"])
        print("     부문", v.get("segs"), v.get("seg_kind") or "", v.get("seg_note") or "", "합", round(sum(x for _, x in v.get("segs") or []), 1))
        print("     비용", v.get("items"))
    except Exception as e:                       # noqa: BLE001
        print("==", t, "오류", repr(e))
