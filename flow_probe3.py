#!/usr/bin/env python3
"""1회용 점검: 매출 종류가 안 나오는 회사들 — 공시 원본에 어떤 부문 축이 있는지 (data/flow/_probe3/)"""
import json, os, re, sys, traceback
import collect as C
import collect_us as U
import xbrl_dims as XD
OUT = "data/flow/_probe3"
os.makedirs(OUT, exist_ok=True)
REVX = re.compile(r"Revenue|Sales|매출|수익", re.I)

def dump(text, labtext):
    ctx, facts = XD.parse(text)
    L = XD.labels(labtext) if labtext else {}
    g = {}
    for n, c, v in facts:
        if not REVX.search(n + L.get(n, "")):
            continue
        p = ctx[c]
        dims = [(a, m) for a, m in p["dims"] if "ConsolidatedAndSeparate" not in a]
        if len(dims) != 1 or not p.get("start"):
            continue
        a, m = dims[0]
        k = "%s | %s | %s~%s" % (L.get(a, a), n, p["start"], p["end"])
        g.setdefault(k, []).append([L.get(m, m), m, v])
    out = {k: v[:25] for k, v in g.items() if len(v) >= 2}
    return dict(sorted(out.items(), key=lambda kv: kv[0])[:120])

def kr(code, corp):
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20250101", "pblntf_ty": "A", "page_count": 30})
    rows = [r for r in (res or {}).get("list", []) if re.search(r"(분기|반기|사업)보고서", r.get("report_nm", ""))]
    rows.sort(key=lambda r: r["rcept_dt"], reverse=True)
    o = {"reports": [r["report_nm"] + " " + r["rcept_dt"] for r in rows[:4]]}
    for r0 in rows[:2]:
        nm = r0["report_nm"]
        rc = "11011" if "사업" in nm else "11012" if "반기" in nm else "11014" if ".09" in nm else "11013"
        blob = C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": rc}, raw=True)
        if not blob or blob[:2] != b"PK":
            o.setdefault("fail", []).append(nm + " no-zip " + repr((blob or b"")[:80]))
            continue
        files = XD.unzip(blob)
        inst = [n for n in files if n.endswith(".xbrl")]
        lab = [n for n in files if "lab-ko" in n]
        o[nm] = dump(files[inst[0]], files[lab[0]] if lab else "")
        break
    return o

def us(t, cik):
    sub = U.get_json(U.SEC_SUBMIT % str(cik).zfill(10))
    rc = sub["filings"]["recent"]
    o = {"recent": [rc["form"][i] + " " + rc["reportDate"][i] + " " + rc["accessionNumber"][i] for i in range(12)]}
    for i, f in enumerate(rc["form"]):
        if f not in ("10-Q", "10-K"):
            continue
        acc = rc["accessionNumber"][i]
        base = U.SEC_ARCH % (int(cik), acc.replace("-", ""))
        idx = U.get_json(base + "index.json")
        names = [x.get("name", "") for x in ((idx or {}).get("directory", {}).get("item", []))]
        o["files"] = names[:40]
        inst = [n for n in names if n.endswith("_htm.xml")]
        lab = [n for n in names if n.endswith("_lab.xml")]
        if inst:
            raw = U.get(base + inst[0]); lr = U.get(base + lab[0]) if lab else None
            o["dims"] = dump(raw.decode("utf-8", "replace"), lr.decode("utf-8", "replace") if lr else "")
        break
    return o

C.API_KEY = C.get_key()
cm = C.load_corp_map()
for code in ["035420", "068270", "373220", "000270", "012450", "010120", "005930"]:
    try:
        o = kr(code, cm[code]["corp_code"])
    except Exception:
        o = {"err": traceback.format_exc()[-800:]}
    json.dump(o, open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(code, list(o)[:4])
for t in ["META", "V", "MA", "ABBV", "KO", "PLTR", "PG", "ORCL", "COST", "CSCO"]:
    try:
        cik = json.load(open(os.path.join("data", "us", t + ".json"), encoding="utf-8")).get("cik")
        o = us(t, cik)
    except Exception:
        o = {"err": traceback.format_exc()[-800:]}
    json.dump(o, open(os.path.join(OUT, t + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(t, list(o)[:4])
