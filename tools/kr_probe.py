# 시험용 — 국내 카드가 왜 최신 분기보고서를 못 쓰는지 (보고서별로 XBRL 읽기 결과)
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import collect_flow as F
import xbrl_dims as XD
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "012450").split(","):
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20250101", "pblntf_ty": "A", "page_count": 30})
    rows = [r for r in (res or {}).get("list", []) if re.search(r"(분기|반기|사업)보고서", r.get("report_nm", ""))]
    rows.sort(key=lambda r: r["rcept_dt"], reverse=True)
    print("==", code, cm[code]["name"], [(r["report_nm"], r["rcept_no"]) for r in rows[:3]])
    for r0 in rows[:2]:
        nm = r0["report_nm"]
        rc = "11011" if "사업" in nm else "11012" if "반기" in nm else "11014" if ".09" in nm else "11013"
        blob = C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": rc}, raw=True)
        print("   ", nm, rc, "blob", (blob or b"")[:2], len(blob or b""))
        if blob and blob[:2] == b"PK":
            files = XD.unzip(blob)
            inst = [n for n in files if n.endswith(".xbrl")]
            lab = [n for n in files if "lab-ko" in n]
            F.FX.WHY = ""
            v = F.FX.from_instance(files[inst[0]], files[lab[0]] if lab else "", us=False) if inst else None
            print("     inst", inst[:1], "→", (v and {k: v[k] for k in ("rev", "op", "ni", "start", "end") if k in v}), "WHY", F.FX.WHY)
        else:
            print("     응답", (blob or b"")[:200])
