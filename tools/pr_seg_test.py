# 시험용 — 실적 발표 자료에서 부문·제품별 매출을 읽는지 (저장하지 않고 출력만)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_flow as F
import collect_us as U
n_ok = 0; codes = (os.environ.get("CODES") or "NVDA").split(",")
for t in codes:
    try:
        cik = json.load(open("data/us/%s.json" % t)).get("cik"); cik = int(cik[0] if isinstance(cik, list) else cik)
        rc = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))["filings"]["recent"]
        v = F.us_pr(cik, rc, {"src": "x"})
        if not v or v == "SAME":
            print("==", t, "손익표 없음", F.FX.WHY); continue
        sg = v.get("segs") or []
        if sg: n_ok += 1
        print("==", t, v["end"], "매출", round(v["rev"] / 1e6, 1), "부문합", round(sum(x for _, x in sg) / 1e6, 1) if sg else "-", [[n, round(x / 1e6, 1)] for n, x in sg], flush=True)
    except Exception as e:                         # noqa: BLE001
        print("==", t, "오류", e)
print("부문 읽음 %d / %d" % (n_ok, len(codes)))
