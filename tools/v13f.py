# 시험용 — 포트폴리오 탭(13F) 전체를 SEC 원본과 따로 대조 (저장하지 않고 결과만 출력)
#   ① 그 운용사의 가장 최근 13F-HR 을 쓰고 있는지 ② 전체 금액(옵션 제외) ③ 상위 종목 비중
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collect_13f as K

D = json.load(open("data/13f.json"))["funds"]
FUND = {f[0]: f for f in K.FUNDS}
bad = 0
for key, f in D.items():
    ciks = FUND.get(key, (0, 0, 0, f.get("cik")))[3]
    ciks = ciks if isinstance(ciks, (list, tuple)) else [ciks]
    tot, grp, accs, notes = 0.0, {}, [], []
    for cik in ciks:
        j, why = K.get("https://data.sec.gov/submissions/CIK%010d.json" % int(cik))
        if not j:
            notes.append("제출목록 %s" % why); continue
        rc = j["filings"]["recent"]
        i = next((i for i, x in enumerate(rc["form"]) if x == "13F-HR"), None)
        if i is None:
            notes.append("13F 없음"); continue
        acc, per = rc["accessionNumber"][i].replace("-", ""), rc["reportDate"][i]
        accs.append((acc, per, j.get("name")))
        base = "https://www.sec.gov/Archives/edgar/data/%d/%s/" % (int(cik), acc)
        idx, _ = K.get(base + "index.json")
        xs = sorted([x["name"] for x in (idx or {}).get("directory", {}).get("item", []) if x["name"].lower().endswith(".xml") and "primary" not in x["name"].lower()])
        for fn in xs:
            txt, _ = K.get(base + fn, is_json=False)
            if not txt or "infoTable" not in txt and "infotable" not in txt.lower():
                continue
            for blk in re.findall(r"<(?:\w+:)?infoTable>(.*?)</(?:\w+:)?infoTable>", txt, re.S | re.I):
                g = lambda t: html.unescape(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", (re.search(r"<(?:\w+:)?%s>(.*?)</" % t, blk, re.S | re.I) or [None, ""])[1], flags=re.S)).strip()   # noqa: E731
                if g("putCall"):
                    continue
                v = float(g("value") or 0)
                if v <= 0:
                    continue
                tot += v
                k = g("cusip") if re.search(r"ISHARES|VANGUARD|SPDR|SELECT SECTOR|INVESCO|STATE STREET|JPMORGAN .*ETF|JPMORGAN SMALL", g("nameOfIssuer"), re.I) else g("cusip")[:6]
                n0 = grp.get(k, [g("nameOfIssuer"), 0])
                n0[1] += v
                grp[k] = n0
            break
    mine = f.get("acc"), f.get("period")
    prob = []
    if accs and len(ciks) == 1 and (accs[0][0] != mine[0]):
        prob.append("최신 13F 다름: 원본 %s(%s) vs 탭 %s(%s)" % (accs[0][0], accs[0][1], mine[0], mine[1]))
    if tot and f.get("total_value") and abs(tot - f["total_value"]) > tot * 0.002 and abs(tot * 1000 - f["total_value"]) > tot * 2:   # 천 달러 단위로 낸 곳은 탭이 1000배로 맞춘다
        prob.append("전체금액 원본 %.0f vs 탭 %.0f" % (tot, f["total_value"]))
    top = sorted(grp.values(), key=lambda x: -x[1])[:5]
    tab = {h.get("raw", "").upper(): h["weight"] for h in f.get("holdings", [])}
    for n, v in top:
        w = 100 * v / tot
        tw = tab.get(n.upper())
        if tw is None:
            tw = next((x for r, x in tab.items() if r[:12] == n.upper()[:12]), None)
        if tw is None and re.search(r"ISHARES|VANGUARD|SPDR|SELECT SECTOR|INVESCO|STATE STREET|JPMORGAN", n, re.I):
            tw = next((h["weight"] for h in f.get("holdings", []) if abs(h["weight"] - w) <= 0.15), None)   # ETF 는 탭 이름이 펀드별로 나뉜다
        if tw is None or abs(tw - w) > 0.15:
            prob.append("%s 원본 %.2f%% vs 탭 %s" % (n, w, tw))
    if prob or notes:
        bad += 1
        print("BAD", key, f.get("title"), f.get("entity"), f.get("period"), "|", "; ".join(prob + notes))
    else:
        print("ok ", key, f.get("title"), "[%s]" % (accs[0][2] if accs else ""), f.get("period"), "상위:", ", ".join("%s %.1f%%" % (n[:18], 100 * v / tot) for n, v in top[:3]))
print("=== %d곳 중 문제 %d" % (len(D), bad))
