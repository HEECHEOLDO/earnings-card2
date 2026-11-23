# 시험용 — 비상장 후보 회사의 DART 회사코드와 최근 실적(감사보고서·사업보고서 원문)을 뽑아 본다 (저장 안 함)
# CODES 환경변수: 법인명을 쉼표로 (DART 법인명과 정확히 같아야 한다)
import os, sys, json, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect as C
import collect_audit as A
C.API_KEY = C.get_key()
C.load_corp_map()
root = ET.parse(os.path.join(C.CACHE_DIR, "corpCode.xml")).getroot()
by = {}
for n in root.iter("list"):
    nm = (n.findtext("corp_name") or "").strip()
    by.setdefault(nm.replace(" ", ""), []).append(((n.findtext("corp_code") or "").strip(), nm, (n.findtext("stock_code") or "").strip(), n.findtext("modify_date")))
A.BUDGET = 4000
for name in [x.strip() for x in os.environ.get("CODES", "").split(",") if x.strip()]:
    hits = [h for h in by.get(name.replace(" ", ""), []) if not h[2]]
    if not hits:
        cand = [k for k in by if name.replace(" ", "") in k][:6]
        print("##", name, "— 같은 이름 없음 · 비슷한 이름:", cand); continue
    best = None
    for code, nm, _, md in hits:
        try:
            data, notes = A.collect_one({"code": code, "codes": [code], "name": nm, "sector": "", "brand": ""}, None)
        except Exception as e:      # noqa: BLE001
            print("##", name, code, "예외", repr(e)[:80]); continue
        if not data:
            print("##", name, code, md, "없음", notes); continue
        an = data.get("annual", [])[-3:]
        print("##", name, code, md, data.get("basis") or data.get("cfs"), data.get("fy"), "|", "; ".join("%s rev %s op %s ni %s" % (a["p"], a.get("rev"), a.get("op"), a.get("ni")) for a in an), "|", (notes or "")[:120] if isinstance(notes, str) else notes)
print("호출", C._call_count)
