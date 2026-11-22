# 시험용 — 누적 빼기가 안 되는 이유 (이번·앞 보고서 누적 부문 이름과 값)
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
C.API_KEY = C.get_key()
import collect_flow as F
import xbrl_dims as XD
cm = C.load_corp_map()
for code in (os.environ.get("CODES") or "006400").split(","):
    corp = cm[code]["corp_code"]
    res = C.api_get("list.json", {"corp_code": corp, "bgn_de": "20250101", "pblntf_ty": "A", "page_count": 30})
    rows = sorted([r for r in res["list"] if re.search(r"(분기|반기|사업)보고서", r["report_nm"])], key=lambda r: r["rcept_dt"], reverse=True)
    for r0, rc in ((rows[0], "11014"), (next(r for r in rows if ".06" in r["report_nm"]), "11012")):
        files = XD.unzip(C.api_get("fnlttXbrl.xml", {"rcept_no": r0["rcept_no"], "reprt_code": rc}, raw=True))
        inst = [n for n in files if n.endswith(".xbrl")]; lab = [n for n in files if "lab-ko" in n]
        v = F.FX.from_instance(files[inst[0]], files[lab[0]] if lab else "", us=False)
        g = lambda L: [[n, round(x / 1e8, 1)] for n, x in (L or [])]   # noqa: E731
        print("==", code, r0["report_nm"], "rev", round(v["rev"] / 1e8, 1), "segs", g(v.get("segs")), v.get("seg_note"), v.get("seg_kind"))
        print("   cum", g(v.get("cum_segs")), "| geo", g(v.get("cum_segs_geo")), "cum_rev", round((v.get("cum_rev") or 0) / 1e8, 1))
