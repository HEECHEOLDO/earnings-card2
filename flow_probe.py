#!/usr/bin/env python3
"""돈의 흐름 — 부문별 매출·판관비 세부가 XBRL 원본에 어떻게 들어 있는지 살펴보는 1회용 점검 (data/flow/_probe/)"""
import json, os, re, sys
import collect as C
import collect_us as U
import xbrl_dims as XD

OUT = "data/flow/_probe"
os.makedirs(OUT, exist_ok=True)


def kr(code):
    C.API_KEY = C.API_KEY or C.get_key()
    cm = C.load_corp_map()
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20260101", "pblntf_ty": "A", "page_count": 20})
    rows = (res or {}).get("list", [])
    rows = [r for r in rows if re.search(r"(분기|반기|사업)보고서", r.get("report_nm", "")) and "기재정정" not in r.get("report_nm", "")]
    rows.sort(key=lambda r: r["rcept_dt"], reverse=True)
    r0 = rows[0]
    rc = "11014" if "분기" in r0["report_nm"] and ".09" in r0["report_nm"] else "11013" if ".03" in r0["report_nm"] else "11012" if "반기" in r0["report_nm"] else "11011"
    blob = C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": rc}, raw=True)
    out = {"report": r0["report_nm"], "rcept": r0["rcept_no"], "rc": rc, "size": len(blob or b"")}
    if not blob or blob[:2] != b"PK":
        out["err"] = (blob or b"")[:200].decode("utf-8", "replace")
        return out
    files = XD.unzip(blob)
    out["files"] = list(files)
    inst = [n for n in files if n.endswith(".xbrl")]
    lab = [n for n in files if "lab-ko" in n or n.endswith("_lab-ko.xml")]
    ctx, facts = XD.parse(files[inst[0]])
    L = XD.labels(files[lab[0]]) if lab else {}
    out["n_ctx"], out["n_facts"] = len(ctx), len(facts)
    per = {}
    for n, c, v in facts:
        p = ctx[c]; per[(p["start"], p["end"])] = per.get((p["start"], p["end"]), 0) + 1
    out["periods"] = sorted([[a, b, k] for (a, b), k in per.items()], key=lambda x: -x[2])[:12]
    # 차원 있는 매출
    out["seg_rev"] = [[n, L.get(n, ""), ctx[c]["start"], ctx[c]["end"], [(a, b, L.get(b, "")) for a, b in ctx[c]["dims"]], v]
                      for n, c, v in facts if ctx[c]["dims"] and re.search(r"Revenue|Sales", n)][:120]
    # 차원 없는 비용 계열
    out["exp"] = [[n, L.get(n, ""), ctx[c]["start"], ctx[c]["end"], v] for n, c, v in facts
                  if not ctx[c]["dims"] and (re.search(r"Expense|Cost|Salar|Wage|Depreci|Amorti|Commission|Advert|Rent", n))][:400]
    return out


def us(t):
    cik = json.load(open("data/us/%s.json" % t))["cik"]
    sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))
    rc = sub["filings"]["recent"]
    i = [k for k, f in enumerate(rc["form"]) if f in ("10-Q", "10-K")][0]
    acc = rc["accessionNumber"][i]
    base = U.SEC_ARCH % (int(cik), acc.replace("-", ""))
    idx = U.get_json(base + "index.json")
    names = [x.get("name", "") for x in idx["directory"]["item"]]
    inst = [n for n in names if n.endswith("_htm.xml")]
    labn = [n for n in names if n.endswith("_lab.xml")]
    text = U.get(base + inst[0]).decode("utf-8", "replace")
    ctx, facts = XD.parse(text)
    L = XD.labels(U.get(base + labn[0]).decode("utf-8", "replace")) if labn else {}
    out = {"form": rc["form"][i], "report": rc["reportDate"][i], "inst": inst, "lab": labn}
    out["seg_rev"] = [[n, ctx[c]["start"], ctx[c]["end"], [(a, b, L.get(b, "")) for a, b in ctx[c]["dims"]], v]
                      for n, c, v in facts if ctx[c]["dims"] and re.search(r"Revenue", n)][:150]
    out["exp"] = [[n, ctx[c]["start"], ctx[c]["end"], v] for n, c, v in facts if not ctx[c]["dims"] and re.search(r"Expense|Cost", n)][:150]
    return out


for code in sys.argv[1:] or ["005930", "035420", "005380", "AAPL", "NVDA", "TSLA"]:
    try:
        o = us(code) if code.isalpha() else kr(code)
    except Exception as e:                       # noqa: BLE001
        import traceback
        o = {"err": traceback.format_exc()[-800:]}
    json.dump(o, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(code, "done")
